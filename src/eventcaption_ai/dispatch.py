"""Coordinator Sequential Prefix Dispatcher.

Core dispatch engine implementing the event-caption/1 causal annotation workflow.
Maintains append-only durability, transactional integrity, media immutability,
deterministic state replay, and strict causal handoff isolation.
"""

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from eventcaption_ai.contract import (
    ACTIONS,
    validate_decision,
    validate_evidence,
    validate_transition,
)

SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
SHA256_HEX_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 digest of a local file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class DispatchError(Exception):
    """Base exception for dispatch and protocol violations."""
    pass


class LockError(DispatchError):
    """Exception raised when session lock cannot be acquired."""
    pass


class SessionLock:
    """OS-level cooperative file lock for session directory.

    Uses kernel-level advisory byte locking (msvcrt on Windows, fcntl on Unix).
    Locks are bound to the living process handle: when the holding process terminates
    abruptly (os._exit, crash, SIGKILL, power loss), the kernel automatically releases
    the lock, preventing unrecoverable stale locks while strictly barring concurrent
    access by living processes.
    """

    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.fd: Optional[int] = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def acquire(self):
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(str(self.lock_file), os.O_RDWR | os.O_CREAT)
            if sys.platform == "win32":
                import msvcrt
                os.lseek(self.fd, 0, os.SEEK_SET)
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError) as e:
            if self.fd is not None:
                try:
                    os.close(self.fd)
                except OSError:
                    pass
                self.fd = None
            raise LockError(
                f"Session is currently locked by another active process: {self.lock_file}. "
                "Concurrent operations on the same session are prohibited."
            ) from e

    def release(self):
        if self.fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None


def validate_queue_structure(queue_data: Any, queue_base_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Validate queue structure and invariants."""
    if not isinstance(queue_data, list) or not queue_data:
        raise DispatchError("Queue must be a non-empty list of assignments.")

    assignments: Dict[str, Dict[str, Any]] = {}
    for item in queue_data:
        if not isinstance(item, dict):
            raise DispatchError("Each assignment in queue must be an object.")

        aid = item.get("assignment_id")
        if not aid or not isinstance(aid, str) or not SAFE_ID_PATTERN.match(aid):
            raise DispatchError(f"Invalid assignment ID: {aid}")
        if aid in assignments:
            raise DispatchError(f"Duplicate assignment ID in queue: {aid}")

        duration_ms = item.get("clip_duration_ms")
        if type(duration_ms) not in (int, float) or duration_ms <= 0:
            raise DispatchError(f"Assignment '{aid}' has invalid clip_duration_ms: {duration_ms}")

        checkpoints = item.get("prefix_checkpoints")
        if not isinstance(checkpoints, list) or not checkpoints:
            raise DispatchError(f"Assignment '{aid}' has no prefix_checkpoints.")

        prev_cutoff = -1
        for i, cp in enumerate(checkpoints):
            cutoff = cp.get("cutoff_ms")
            if type(cutoff) not in (int, float) or cutoff <= 0:
                raise DispatchError(f"Assignment '{aid}' checkpoint {i} has invalid cutoff_ms: {cutoff}")
            if cutoff <= prev_cutoff:
                raise DispatchError(
                    f"Assignment '{aid}' checkpoint cutoffs must be strictly increasing. "
                    f"Found {cutoff} <= {prev_cutoff} at index {i}."
                )
            if cutoff > duration_ms:
                raise DispatchError(
                    f"Assignment '{aid}' checkpoint cutoff {cutoff}ms exceeds duration {duration_ms}ms."
                )
            prev_cutoff = cutoff

            sha = cp.get("sha256")
            if not isinstance(sha, str) or not SHA256_HEX_PATTERN.match(sha):
                raise DispatchError(f"Assignment '{aid}' checkpoint {i} has invalid sha256 hex string: {sha}")

            ref = cp.get("media_prefix_ref")
            if not isinstance(ref, str) or not ref:
                raise DispatchError(f"Assignment '{aid}' checkpoint {i} missing media_prefix_ref.")

            media_path = (queue_base_dir / ref).resolve()
            try:
                media_path.relative_to(queue_base_dir.resolve())
            except ValueError:
                raise DispatchError(f"Path traversal detected in media_prefix_ref: {ref}")

        assignments[aid] = item

    return assignments


def apply_decisions_transition(
    assignment_id: str,
    cutoff_ms: int | float,
    current_active_events: Dict[str, Any],
    decisions_list: List[Dict[str, Any]],
    evidence_registry: Dict[str, Any],
    event_counter_start: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], int]:
    """Pure state transition function applying a list of decisions at a cutoff.

    Used identically by submit_decision and _read_and_verify_log to guarantee
    deterministic, verifiable state transitions without relying on caption text matching.
    """
    validate_evidence(evidence_registry, cutoff_ms)

    if not isinstance(decisions_list, list) or not decisions_list:
        raise DispatchError("decisions_list must be a non-empty list.")

    has_wait = any(d.get("action") == "WAIT" for d in decisions_list)
    if has_wait:
        if len(decisions_list) > 1:
            raise DispatchError(
                "WAIT indicates no event updates or emissions at this cutoff. "
                "Cannot combine WAIT with other event actions at the same checkpoint."
            )
        wait_dec = decisions_list[0]
        validate_decision(wait_dec, cutoff_ms, evidence_registry)
        operations = [{
            "action": "WAIT",
            "evidence_cutoff_ms": cutoff_ms,
        }]
        return operations, dict(current_active_events), event_counter_start

    operations = []
    active_events = dict(current_active_events)
    counter = event_counter_start

    for op in decisions_list:
        action = op.get("action")
        if action not in ACTIONS:
            raise DispatchError(f"Invalid action: '{action}'. Must be one of {ACTIONS}")

        validate_decision(op, cutoff_ms, evidence_registry)

        if action == "EMIT":
            counter += 1
            event_id = f"ev_{assignment_id}_{counter:03d}_{cutoff_ms}"
            record_id = f"rec_{event_id}_v1"
            new_record = {
                "event_id": event_id,
                "record_id": record_id,
                "previous_record_id": None,
                "version": 1,
                "action": "EMIT",
                "operation": "create",
                "text": op["text"],
                "start_ms": op["start_ms"],
                "end_ms": op["end_ms"],
                "event_status": op["event_status"],
                "evidence_refs": op["evidence_refs"],
                "evidence_cutoff_ms": cutoff_ms,
            }
            validate_transition(None, new_record)
            if event_id in active_events:
                raise DispatchError(f"Duplicate event ID generated: '{event_id}'.")
            active_events[event_id] = new_record
            operations.append(new_record)

        elif action in ("REVISE", "WITHDRAW"):
            prev_id = op["previous_record_id"]
            target_event_id = None
            target_old_record = None
            for eid, ev in active_events.items():
                if ev.get("record_id") == prev_id:
                    target_event_id = eid
                    target_old_record = ev
                    break

            if target_old_record is None:
                raise DispatchError(
                    f"Target record ID '{prev_id}' not found in active events for revision/withdrawal."
                )

            new_version = target_old_record["version"] + 1
            record_id = f"rec_{target_event_id}_v{new_version}"
            operation = "revise" if action == "REVISE" else "withdraw"
            new_record = {
                "event_id": target_event_id,
                "record_id": record_id,
                "previous_record_id": prev_id,
                "version": new_version,
                "action": action,
                "operation": operation,
                "text": op["text"],
                "start_ms": op["start_ms"],
                "end_ms": op["end_ms"],
                "event_status": op["event_status"],
                "evidence_refs": op["evidence_refs"],
                "evidence_cutoff_ms": cutoff_ms,
            }
            validate_transition(target_old_record, new_record)
            active_events[target_event_id] = new_record
            operations.append(new_record)

    return operations, active_events, counter


class CoordinatorDispatcher:
    """Coordinator sequential prefix dispatcher managing causal annotation state."""

    def __init__(self, coordinator_dir: Path, queue_file: Path):
        self.coordinator_dir = coordinator_dir.resolve()
        self.coordinator_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = queue_file.resolve()
        if not self.queue_file.exists():
            raise DispatchError(f"Queue file not found: {self.queue_file}")

        self.queue_base_dir = self.queue_file.parent.resolve()
        self.queue_sha256 = compute_sha256(self.queue_file)
        self.queue_data = json.loads(self.queue_file.read_text(encoding="utf-8"))
        self.assignments = validate_queue_structure(self.queue_data, self.queue_base_dir)

    def _verify_queue_integrity(self, expected_sha256: str) -> None:
        """Verify the queue file has not been altered since session creation."""
        current_sha = compute_sha256(self.queue_file)
        if current_sha != expected_sha256:
            raise DispatchError(
                f"Queue file integrity violation: current SHA-256 ({current_sha}) "
                f"does not match session locked SHA-256 ({expected_sha256})."
            )

    def _session_file(self, session_id: str) -> Path:
        return self.coordinator_dir / f"session_{session_id}.json"

    def _log_file(self, session_id: str) -> Path:
        return self.coordinator_dir / f"decisions_{session_id}.jsonl"

    def _lock_file(self, session_id: str) -> Path:
        return self.coordinator_dir / f"session_{session_id}.lock"

    def _verify_handoff_isolation(self, handoff_dir: Path, session_id: str, assignment_id: str) -> Path:
        """Verify handoff directory does not overlap repository or coordinator and verify ownership."""
        handoff = handoff_dir.resolve()
        coord = self.coordinator_dir
        queue_base = self.queue_base_dir

        if handoff == coord or handoff in coord.parents or coord in handoff.parents:
            raise DispatchError(
                f"Handoff directory {handoff} overlaps with coordinator directory {coord}. "
                "Handoff must be strictly isolated."
            )
        if handoff == queue_base or handoff in queue_base.parents or queue_base in handoff.parents:
            raise DispatchError(
                f"Handoff directory {handoff} overlaps with queue/media repository {queue_base}. "
                "Handoff must be strictly isolated."
            )

        handoff.mkdir(parents=True, exist_ok=True)

        marker_file = handoff / ".session_handoff.json"
        if marker_file.exists():
            try:
                marker = json.loads(marker_file.read_text(encoding="utf-8"))
                if marker.get("session_id") != session_id:
                    raise DispatchError(
                        f"Handoff directory ownership mismatch: owned by session '{marker.get('session_id')}', "
                        f"cannot use for session '{session_id}'."
                    )
            except Exception as e:
                if isinstance(e, DispatchError):
                    raise
                raise DispatchError(f"Corrupted handoff marker in {handoff}: {e}")
        else:
            existing_files = list(handoff.iterdir())
            if existing_files:
                raise DispatchError(
                    f"Handoff directory {handoff} is not empty and lacks ownership marker for session '{session_id}'. "
                    "Cannot use an uninitialized or foreign directory for handoff."
                )
            marker_data = {
                "session_id": session_id,
                "assignment_id": assignment_id,
                "initialized_at": datetime.now(timezone.utc).isoformat(),
            }
            marker_file.write_text(json.dumps(marker_data, indent=2), encoding="utf-8")

        return handoff

    def init_session(
        self,
        session_id: str,
        assignment_id: str,
        annotator_id: str,
        handoff_dir: Path,
        supersedes_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initialize a new session. Force-cleaning/truncating past logs is strictly forbidden."""
        if not SAFE_ID_PATTERN.match(session_id):
            raise DispatchError(f"Invalid session ID '{session_id}'. Must match [a-zA-Z0-9_-]+.")
        if not SAFE_ID_PATTERN.match(annotator_id):
            raise DispatchError(f"Invalid annotator ID '{annotator_id}'. Must match [a-zA-Z0-9_-]+.")

        session_file = self._session_file(session_id)
        log_file = self._log_file(session_id)

        if session_file.exists() or log_file.exists():
            raise DispatchError(
                f"Session '{session_id}' or its decision log already exists. "
                "Destructive resets and truncating decision history are strictly prohibited. "
                "Use 'resume' to continue, or choose a new session ID."
            )

        if assignment_id not in self.assignments:
            alt = f"QUEUE_{assignment_id}"
            if alt in self.assignments:
                assignment_id = alt
            else:
                raise DispatchError(f"Assignment '{assignment_id}' not found in queue.")

        assignment = self.assignments[assignment_id]
        checkpoints = assignment["prefix_checkpoints"]

        for cp in checkpoints:
            p_path = self.queue_base_dir / cp["media_prefix_ref"]
            if not p_path.exists():
                raise DispatchError(f"Prefix media file missing on disk: {p_path}")
            actual_sha = compute_sha256(p_path)
            if actual_sha != cp["sha256"]:
                raise DispatchError(
                    f"Digest mismatch in prefix media {p_path}: "
                    f"actual={actual_sha}, declared={cp['sha256']}"
                )

        validated_handoff = self._verify_handoff_isolation(handoff_dir, session_id, assignment_id)

        session_data = {
            "session_id": session_id,
            "assignment_id": assignment_id,
            "annotator_id": annotator_id,
            "queue_file": str(self.queue_file),
            "queue_sha256": self.queue_sha256,
            "clip_duration_ms": assignment.get("clip_duration_ms"),
            "total_checkpoints": len(checkpoints),
            "checkpoints": checkpoints,
            "current_step_index": 0,
            "event_counter": 0,
            "status": "in_progress",
            "active_events": {},
            "supersedes_session_id": supersedes_session_id,
            "verified_by_human": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

        with SessionLock(self._lock_file(session_id)):
            log_file.touch(exist_ok=False)
            self._save_session_atomic(session_data)
            self._deliver_prefix(session_data, validated_handoff)

        return session_data

    def _deliver_prefix(self, session: Dict[str, Any], handoff_dir: Path) -> Path:
        """Deliver strictly the current prefix video to handoff via an independent, read-only copy."""
        idx = session["current_step_index"]
        session_id = session["session_id"]
        assignment_id = session["assignment_id"]

        for f in handoff_dir.glob(f"prefix_{session_id}_*.mp4"):
            try:
                os.chmod(f, 0o666)
                f.unlink()
            except OSError as e:
                raise DispatchError(f"Failed to remove previous prefix in handoff: {e}")

        if idx >= session["total_checkpoints"]:
            done_notice = {
                "session_id": session_id,
                "assignment_id": assignment_id,
                "status": "completed",
                "completed_at": session.get("completed_at"),
                "message": "All prefix checkpoints for this assignment are completed. Awaiting Pass 2 instructions.",
            }
            (handoff_dir / "current_checkpoint.json").write_text(
                json.dumps(done_notice, indent=2), encoding="utf-8"
            )
            return handoff_dir

        cp = session["checkpoints"][idx]
        src_path = self.queue_base_dir / cp["media_prefix_ref"]

        if not src_path.exists():
            raise DispatchError(f"Source prefix file missing: {src_path}")

        src_sha = compute_sha256(src_path)
        if src_sha != cp["sha256"]:
            raise DispatchError(f"Source media corrupted: hash mismatch on {src_path}")

        dest_filename = f"prefix_{session_id}_cutoff_{cp['cutoff_ms']}ms.mp4"
        dest_path = handoff_dir / dest_filename
        temp_dest = handoff_dir / f".tmp_{dest_filename}"

        shutil.copy2(src_path, temp_dest)

        copied_sha = compute_sha256(temp_dest)
        if copied_sha != src_sha:
            temp_dest.unlink(missing_ok=True)
            raise DispatchError("Copied file digest mismatch during delivery.")

        try:
            os.chmod(temp_dest, 0o444)
        except OSError:
            pass

        temp_dest.replace(dest_path)

        active_summary = []
        for eid, ev in session.get("active_events", {}).items():
            active_summary.append({
                "event_id": eid,
                "record_id": ev.get("record_id"),
                "version": ev.get("version"),
                "start_ms": ev.get("start_ms"),
                "end_ms": ev.get("end_ms"),
                "event_status": ev.get("event_status"),
                "text": ev.get("text"),
            })

        checkpoint_info = {
            "session_id": session_id,
            "assignment_id": assignment_id,
            "step_index": idx,
            "cutoff_ms": cp["cutoff_ms"],
            "prefix_video": dest_filename,
            "video_sha256": copied_sha,
            "frames_count": cp.get("frames_count"),
            "max_media_ms": cp.get("max_media_ms"),
            "active_events": active_summary,
            "instructions": (
                f"Evaluate observed actions up to cutoff {cp['cutoff_ms']}ms. "
                "Actions: 'WAIT' (if no updates), 'EMIT' (new event), 'REVISE' (update active event), "
                "or 'WITHDRAW' (revoke unsupported event). "
                "Submit decision via coordinator CLI before the next prefix is released."
            ),
        }
        (handoff_dir / "current_checkpoint.json").write_text(
            json.dumps(checkpoint_info, indent=2), encoding="utf-8"
        )
        return dest_path

    def _save_session_atomic(self, session: Dict[str, Any]) -> None:
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        session_file = self._session_file(session["session_id"])
        temp_file = session_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_file.replace(session_file)

    def _read_and_verify_log(self, session: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], int]:
        """Read, strictly verify and replay log against queue checkpoints, envelope, and contract rules.

        Recomputes operations from payload using apply_decisions_transition and checks FULL content equality.
        Fail-closed: Any mismatch in session metadata, checkpoint hash, cutoff, evidence registry,
        or contract transitions will raise DispatchError.
        """
        session_id = session["session_id"]
        assignment_id = session["assignment_id"]
        annotator_id = session["annotator_id"]
        checkpoints = session["checkpoints"]
        total_cps = len(checkpoints)

        log_file = self._log_file(session_id)
        if not log_file.exists():
            raise DispatchError(f"Decision log file missing for session '{session_id}': {log_file}")

        entries: List[Dict[str, Any]] = []
        raw_text = log_file.read_text(encoding="utf-8")
        lines = raw_text.splitlines()

        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                raise DispatchError(
                    f"Corrupted or partial JSON line in decision log at line {lineno}: {e}. "
                    "Fail-closed: Uncommitted/partial log lines must be resolved before proceeding."
                )
            entries.append(entry)

        if len(entries) > total_cps:
            raise DispatchError(
                f"Log integrity error in {log_file}: contains {len(entries)} entries, "
                f"which exceeds total checkpoints ({total_cps})."
            )

        active_events: Dict[str, Any] = {}
        event_counter = 0

        for i, entry in enumerate(entries):
            if entry.get("step_index") != i:
                raise DispatchError(
                    f"Log integrity error at entry {i}: step_index is {entry.get('step_index')}, expected {i}."
                )

            if entry.get("session_id") != session_id:
                raise DispatchError(
                    f"Log entry {i} session_id mismatch: '{entry.get('session_id')}' != '{session_id}'."
                )
            if entry.get("assignment_id") != assignment_id:
                raise DispatchError(
                    f"Log entry {i} assignment_id mismatch: '{entry.get('assignment_id')}' != '{assignment_id}'."
                )
            if entry.get("annotator_id") != annotator_id:
                raise DispatchError(
                    f"Log entry {i} annotator_id mismatch: '{entry.get('annotator_id')}' != '{annotator_id}'."
                )

            expected_cp = checkpoints[i]
            if entry.get("cutoff_ms") != expected_cp["cutoff_ms"]:
                raise DispatchError(
                    f"Log entry {i} cutoff mismatch: {entry.get('cutoff_ms')} != expected {expected_cp['cutoff_ms']}."
                )
            if entry.get("checkpoint_sha256") != expected_cp["sha256"]:
                raise DispatchError(
                    f"Log entry {i} checkpoint hash mismatch: '{entry.get('checkpoint_sha256')}' != expected '{expected_cp['sha256']}'."
                )

            payload = entry.get("submission_payload")
            if not isinstance(payload, dict):
                raise DispatchError(f"Log entry {i} missing valid 'submission_payload' dict.")
            if payload.get("cutoff_ms") != expected_cp["cutoff_ms"]:
                raise DispatchError(f"Log entry {i} submission payload cutoff mismatch.")
            if "assignment_id" in payload and payload["assignment_id"] != assignment_id:
                raise DispatchError(f"Log entry {i} submission payload assignment_id mismatch.")

            evidence_registry = entry.get("evidence_registry")
            if not isinstance(evidence_registry, dict):
                raise DispatchError(f"Log entry {i} missing valid 'evidence_registry' dict.")
            if evidence_registry != payload.get("evidence_registry", {}):
                raise DispatchError(
                    f"Log entry {i} evidence_registry mismatch between log entry and submission payload."
                )

            # Extract decisions from payload
            if "decisions" in payload:
                decisions_list = payload["decisions"]
            elif "decision" in payload:
                decisions_list = [payload["decision"]]
            elif "action" in payload:
                decisions_list = [payload]
            else:
                raise DispatchError(f"Log entry {i} payload missing decisions specification.")

            # Recompute operations using pure state transition function
            recomputed_ops, active_events, event_counter = apply_decisions_transition(
                assignment_id=assignment_id,
                cutoff_ms=expected_cp["cutoff_ms"],
                current_active_events=active_events,
                decisions_list=decisions_list,
                evidence_registry=evidence_registry,
                event_counter_start=event_counter,
            )

            # Compare logged operations FULLY with recomputed operations
            logged_ops = entry.get("operations")
            if logged_ops != recomputed_ops:
                raise DispatchError(
                    f"Log entry {i} operations content mismatch with recomputed operations from payload. "
                    f"Logged: {logged_ops}, Recomputed: {recomputed_ops}"
                )

            # Compare active events snapshot
            if entry.get("active_events_snapshot") != active_events:
                raise DispatchError(
                    f"Log entry {i} active_events_snapshot mismatch with recomputed active state."
                )

        return entries, active_events, event_counter

    def load_session(self, session_id: str) -> Dict[str, Any]:
        """Load session metadata, reconciled against log as ground truth."""
        session_file = self._session_file(session_id)
        if not session_file.exists():
            raise DispatchError(f"Session '{session_id}' not found.")

        session = json.loads(session_file.read_text(encoding="utf-8"))
        self._verify_queue_integrity(session["queue_sha256"])

        log_entries, replayed_events, replayed_counter = self._read_and_verify_log(session)
        actual_steps = len(log_entries)

        if (
            session.get("current_step_index") != actual_steps
            or session.get("active_events") != replayed_events
            or session.get("event_counter") != replayed_counter
        ):
            session["current_step_index"] = actual_steps
            session["active_events"] = replayed_events
            session["event_counter"] = replayed_counter
            if actual_steps >= session["total_checkpoints"]:
                session["status"] = "completed"
            self._save_session_atomic(session)

        return session

    def submit_decision(
        self,
        session_id: str,
        decision_payload: Dict[str, Any],
        handoff_dir: Path,
    ) -> Dict[str, Any]:
        """Validate, persist decision to append-only log with idempotent crash recovery."""
        with SessionLock(self._lock_file(session_id)):
            session = self.load_session(session_id)
            validated_handoff = self._verify_handoff_isolation(handoff_dir, session_id, session["assignment_id"])

            curr_idx = session["current_step_index"]
            total_steps = session["total_checkpoints"]

            # 1. Structural check of submission
            submitted_cutoff = decision_payload.get("cutoff_ms")
            if submitted_cutoff is None:
                raise DispatchError("Submission missing 'cutoff_ms'.")

            # 2. Check for idempotent retry BEFORE checking completed status
            log_entries, active_events, event_counter = self._read_and_verify_log(session)
            if log_entries:
                last_entry = log_entries[-1]
                last_cutoff = last_entry["cutoff_ms"]
                if submitted_cutoff == last_cutoff:
                    logged_input = last_entry.get("submission_payload")
                    if logged_input and logged_input == decision_payload:
                        # Idempotent retry of crashed post-commit step (including final checkpoint)
                        self._deliver_prefix(session, validated_handoff)
                        return {
                            "status": "success",
                            "idempotent_retry": True,
                            "step_index": last_entry["step_index"],
                            "cutoff_ms": submitted_cutoff,
                            "next_step_index": session["current_step_index"],
                            "session_status": session["status"],
                        }
                    else:
                        raise DispatchError(
                            f"Out-of-order submission: submitted cutoff {submitted_cutoff}ms has already "
                            f"been processed with a different payload. Past decisions are immutable."
                        )

            # Check if session is already completed
            if curr_idx >= total_steps:
                if session["status"] != "completed":
                    session["status"] = "completed"
                    session["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self._save_session_atomic(session)
                raise DispatchError(
                    f"Session '{session_id}' is already completed. No further decisions accepted."
                )

            current_cp = session["checkpoints"][curr_idx]
            expected_cutoff = current_cp["cutoff_ms"]

            if submitted_cutoff < expected_cutoff:
                raise DispatchError(
                    f"Out-of-order submission: submitted cutoff {submitted_cutoff}ms has already "
                    f"been processed (expected current cutoff: {expected_cutoff}ms). "
                    "Past decisions are immutable and cannot be rewritten."
                )

            if submitted_cutoff > expected_cutoff:
                raise DispatchError(
                    f"Out-of-order submission: submitted cutoff {submitted_cutoff}ms skips ahead "
                    f"of current checkpoint (expected current cutoff: {expected_cutoff}ms). "
                    "Skipping checkpoints is strictly prohibited."
                )

            if "assignment_id" in decision_payload and decision_payload["assignment_id"] != session["assignment_id"]:
                raise DispatchError(
                    f"Assignment ID mismatch: expected '{session['assignment_id']}', got '{decision_payload['assignment_id']}'"
                )

            # Extract decisions list
            if "decisions" in decision_payload:
                decisions_list = decision_payload["decisions"]
            elif "decision" in decision_payload:
                decisions_list = [decision_payload["decision"]]
            elif "action" in decision_payload:
                decisions_list = [decision_payload]
            else:
                raise DispatchError("Submission must contain 'decisions', 'decision', or 'action'.")

            evidence_registry = decision_payload.get("evidence_registry", {})
            if not isinstance(evidence_registry, dict):
                raise DispatchError("'evidence_registry' must be a dict mapping ref -> timestamp.")

            # Compute transition using pure shared function
            processed_ops, active_events, new_counter = apply_decisions_transition(
                assignment_id=session["assignment_id"],
                cutoff_ms=expected_cutoff,
                current_active_events=active_events,
                decisions_list=decisions_list,
                evidence_registry=evidence_registry,
                event_counter_start=session.get("event_counter", 0),
            )

            # Atomic append to append-only log with evidence registry & metadata
            log_file = self._log_file(session_id)
            log_entry = {
                "session_id": session_id,
                "assignment_id": session["assignment_id"],
                "annotator_id": session["annotator_id"],
                "step_index": curr_idx,
                "cutoff_ms": expected_cutoff,
                "checkpoint_sha256": current_cp["sha256"],
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "evidence_registry": evidence_registry,
                "submission_payload": decision_payload,
                "operations": processed_ops,
                "active_events_snapshot": active_events,
                "verified_by_human": False,
            }
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                lf.flush()
                os.fsync(lf.fileno())

            # Advance session state
            session["current_step_index"] += 1
            session["active_events"] = active_events
            session["event_counter"] = new_counter
            if session["current_step_index"] >= total_steps:
                session["status"] = "completed"
                session["completed_at"] = datetime.now(timezone.utc).isoformat()

            self._save_session_atomic(session)

            # Deliver next prefix
            self._deliver_prefix(session, validated_handoff)

            return {
                "status": "success",
                "idempotent_retry": False,
                "step_index": curr_idx,
                "cutoff_ms": expected_cutoff,
                "operations_count": len(processed_ops),
                "next_step_index": session["current_step_index"],
                "session_status": session["status"],
            }

    def resume_session(self, session_id: str, handoff_dir: Path) -> Dict[str, Any]:
        """Reconstruct state from log, synchronize handoff without skipping."""
        with SessionLock(self._lock_file(session_id)):
            session = self.load_session(session_id)
            validated_handoff = self._verify_handoff_isolation(handoff_dir, session_id, session["assignment_id"])

            self._deliver_prefix(session, validated_handoff)

            return {
                "session_id": session_id,
                "assignment_id": session["assignment_id"],
                "current_step_index": session["current_step_index"],
                "total_checkpoints": session["total_checkpoints"],
                "status": session["status"],
                "active_events_count": len(session["active_events"]),
            }

    def get_status(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return status for one or all sessions."""
        if session_id:
            s = self.load_session(session_id)
            return [s]
        results = []
        for sf in self.coordinator_dir.glob("session_*.json"):
            sid = sf.stem.removeprefix("session_")
            try:
                results.append(self.load_session(sid))
            except Exception:
                pass
        return results
