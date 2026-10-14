"""Tests for coordinator prefix dispatcher with OS-level locking, log replay verification, and fault injection."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from eventcaption_ai.dispatch import (
    CoordinatorDispatcher,
    DispatchError,
    LockError,
    SessionLock,
    compute_sha256,
)


@pytest.fixture
def test_env(tmp_path):
    pkg_dir = tmp_path / "labeling-package"
    media_dir = pkg_dir / "media/prefixes"
    media_dir.mkdir(parents=True)
    handoff_dir = tmp_path / "handoff"
    handoff_dir.mkdir(parents=True)
    coord_dir = tmp_path / "coordinator-sessions"
    coord_dir.mkdir(parents=True)

    p1 = media_dir / "SYNTH_cutoff_1000ms.mp4"
    p2 = media_dir / "SYNTH_cutoff_2000ms.mp4"
    p3 = media_dir / "SYNTH_cutoff_3000ms.mp4"
    p1.write_bytes(b"SYNTH_MP4_1000MS_DATA_FOR_UNIT_TEST")
    p2.write_bytes(b"SYNTH_MP4_2000MS_DATA_FOR_UNIT_TEST")
    p3.write_bytes(b"SYNTH_MP4_3000MS_DATA_FOR_UNIT_TEST")

    sha1 = compute_sha256(p1)
    sha2 = compute_sha256(p2)
    sha3 = compute_sha256(p3)

    queue_data = [
        {
            "assignment_id": "QUEUE_SYNTH",
            "scenario_group": "synthetic_test",
            "clip_duration_s": 3.0,
            "clip_duration_ms": 3000,
            "prefix_checkpoints": [
                {
                    "cutoff_ms": 1000,
                    "media_prefix_ref": "media/prefixes/SYNTH_cutoff_1000ms.mp4",
                    "sha256": sha1,
                    "frames_count": 25,
                    "max_media_ms": 966,
                },
                {
                    "cutoff_ms": 2000,
                    "media_prefix_ref": "media/prefixes/SYNTH_cutoff_2000ms.mp4",
                    "sha256": sha2,
                    "frames_count": 50,
                    "max_media_ms": 1966,
                },
                {
                    "cutoff_ms": 3000,
                    "media_prefix_ref": "media/prefixes/SYNTH_cutoff_3000ms.mp4",
                    "sha256": sha3,
                    "frames_count": 75,
                    "max_media_ms": 2966,
                },
            ],
        }
    ]
    queue_file = pkg_dir / "neutral-prefix-queue.json"
    queue_file.write_text(json.dumps(queue_data, indent=2), encoding="utf-8")

    return {
        "queue_file": queue_file,
        "handoff_dir": handoff_dir,
        "coord_dir": coord_dir,
        "p1": p1,
        "sha1": sha1,
        "p2": p2,
        "sha2": sha2,
        "p3": p3,
        "sha3": sha3,
    }


def test_dispatcher_happy_path_and_final_checkpoint_idempotency(test_env):
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )

    session = dispatcher.init_session(
        session_id="sess_happy_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )
    assert session["current_step_index"] == 0
    assert session["status"] == "in_progress"

    # Step 0: EMIT
    emit_payload = {
        "cutoff_ms": 1000,
        "evidence_registry": {"ev1": 500},
        "decisions": [
            {
                "action": "EMIT",
                "previous_record_id": None,
                "text": "Chopping vegetable on board",
                "start_ms": 200,
                "end_ms": None,
                "event_status": "ongoing",
                "evidence_refs": ["ev1"],
            }
        ],
    }
    res0 = dispatcher.submit_decision("sess_happy_01", emit_payload, test_env["handoff_dir"])
    assert res0["status"] == "success"
    assert res0["next_step_index"] == 1

    log_file = test_env["coord_dir"] / "decisions_sess_happy_01.jsonl"
    entry0 = json.loads(log_file.read_text(encoding="utf-8").strip().splitlines()[0])
    rec0_id = entry0["operations"][0]["record_id"]

    # Step 1: REVISE
    revise_payload = {
        "cutoff_ms": 2000,
        "evidence_registry": {"ev1": 500, "ev2": 1500},
        "decisions": [
            {
                "action": "REVISE",
                "previous_record_id": rec0_id,
                "text": "Chopping onion on board",
                "start_ms": 200,
                "end_ms": 1800,
                "event_status": "ended",
                "evidence_refs": ["ev1", "ev2"],
            }
        ],
    }
    res1 = dispatcher.submit_decision("sess_happy_01", revise_payload, test_env["handoff_dir"])
    assert res1["next_step_index"] == 2

    # Step 2: WAIT (final checkpoint)
    wait_payload = {
        "cutoff_ms": 3000,
        "decisions": [{"action": "WAIT"}],
    }
    res2 = dispatcher.submit_decision("sess_happy_01", wait_payload, test_env["handoff_dir"])
    assert res2["session_status"] == "completed"
    assert res2["next_step_index"] == 3

    # IDEMPOTENT RETRY AT FINAL CHECKPOINT
    res_retry_final = dispatcher.submit_decision("sess_happy_01", wait_payload, test_env["handoff_dir"])
    assert res_retry_final["status"] == "success"
    assert res_retry_final["idempotent_retry"] is True
    assert res_retry_final["session_status"] == "completed"

    # Conflicting payload at final cutoff must be rejected
    conflicting_final = {
        "cutoff_ms": 3000,
        "decisions": [{"action": "EMIT", "previous_record_id": None, "text": "Wrong", "start_ms": 2500, "end_ms": None, "event_status": "ongoing", "evidence_refs": ["ev1"]}],
        "evidence_registry": {"ev1": 2500}
    }
    with pytest.raises(DispatchError, match="different payload|already been processed"):
        dispatcher.submit_decision("sess_happy_01", conflicting_final, test_env["handoff_dir"])


def test_multiple_emits_with_identical_caption_succeed_and_resume_cleanly(test_env):
    """Repro 1: Multiple EMITs with the same caption text at the same checkpoint.
    Submit must assign distinct event IDs, and resume must succeed without false duplicate ID errors.
    """
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_same_text_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    same_caption_payload = {
        "cutoff_ms": 1000,
        "evidence_registry": {"ev_a": 500},
        "decisions": [
            {
                "action": "EMIT",
                "previous_record_id": None,
                "text": "A hand moves a cup",
                "start_ms": 100,
                "end_ms": None,
                "event_status": "ongoing",
                "evidence_refs": ["ev_a"],
            },
            {
                "action": "EMIT",
                "previous_record_id": None,
                "text": "A hand moves a cup",
                "start_ms": 200,
                "end_ms": None,
                "event_status": "ongoing",
                "evidence_refs": ["ev_a"],
            },
        ],
    }

    # Submit must succeed and create 2 distinct events
    res_sub = dispatcher.submit_decision("sess_same_text_01", same_caption_payload, test_env["handoff_dir"])
    assert res_sub["status"] == "success"
    assert res_sub["operations_count"] == 2

    # Verify log entries
    log_file = test_env["coord_dir"] / "decisions_sess_same_text_01.jsonl"
    entry0 = json.loads(log_file.read_text(encoding="utf-8").strip().splitlines()[0])
    ops = entry0["operations"]
    assert len(ops) == 2
    assert ops[0]["event_id"] != ops[1]["event_id"]
    assert ops[0]["text"] == ops[1]["text"] == "A hand moves a cup"

    # Resume MUST succeed cleanly without "duplicate event ID" error!
    res_resume = dispatcher.resume_session("sess_same_text_01", test_env["handoff_dir"])
    assert res_resume["current_step_index"] == 1
    assert res_resume["active_events_count"] == 2


def test_replay_divergence_between_payload_and_operation_fails_closed(test_env):
    """Repro 2: When payload and operations diverge (e.g. start_ms modified in payload),
    replay must fail closed rather than accepting mismatch.
    """
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_diverge_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    emit_payload = {
        "cutoff_ms": 1000,
        "evidence_registry": {"ev1": 500},
        "decisions": [
            {
                "action": "EMIT",
                "previous_record_id": None,
                "text": "Chopping vegetable on board",
                "start_ms": 100,
                "end_ms": None,
                "event_status": "ongoing",
                "evidence_refs": ["ev1"],
            }
        ],
    }
    dispatcher.submit_decision("sess_diverge_01", emit_payload, test_env["handoff_dir"])

    log_file = test_env["coord_dir"] / "decisions_sess_diverge_01.jsonl"
    orig_text = log_file.read_text(encoding="utf-8")
    entry = json.loads(orig_text.strip())

    # Case A: Alter start_ms in submission_payload to 300, while operation keeps 100
    tampered_entry_a = json.loads(json.dumps(entry))
    tampered_entry_a["submission_payload"]["decisions"][0]["start_ms"] = 300
    log_file.write_text(json.dumps(tampered_entry_a) + "\n", encoding="utf-8")

    with pytest.raises(DispatchError, match="operations content mismatch with recomputed operations"):
        dispatcher.load_session("sess_diverge_01")

    # Case B: Alter text in submission_payload, while operation keeps old text
    tampered_entry_b = json.loads(json.dumps(entry))
    tampered_entry_b["submission_payload"]["decisions"][0]["text"] = "Different action text"
    log_file.write_text(json.dumps(tampered_entry_b) + "\n", encoding="utf-8")

    with pytest.raises(DispatchError, match="operations content mismatch with recomputed operations"):
        dispatcher.load_session("sess_diverge_01")

    # Case C: Divergence between entry evidence_registry and payload evidence_registry
    tampered_entry_c = json.loads(json.dumps(entry))
    tampered_entry_c["evidence_registry"] = {"ev1": 500, "ev2": 800}
    log_file.write_text(json.dumps(tampered_entry_c) + "\n", encoding="utf-8")

    with pytest.raises(DispatchError, match="evidence_registry mismatch"):
        dispatcher.load_session("sess_diverge_01")


def test_lock_released_on_hard_crash_os_exit(test_env):
    """Child process acquires lock then abruptly dies via os._exit(23).
    Parent must be able to acquire lock and resume immediately without LockError.
    """
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_hard_crash_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    lock_file = test_env["coord_dir"] / "session_sess_hard_crash_01.lock"

    child_code = f"""
import sys, os
from pathlib import Path
from eventcaption_ai.dispatch import SessionLock

lock = SessionLock(Path(r"{lock_file}"))
lock.acquire()
sys.stdout.write("locked\\n")
sys.stdout.flush()
os._exit(23)
"""
    p = subprocess.Popen([sys.executable, "-c", child_code], stdout=subprocess.PIPE, text=True)
    line = p.stdout.readline()
    assert "locked" in line
    p.wait()
    assert p.returncode == 23

    res = dispatcher.resume_session("sess_hard_crash_01", test_env["handoff_dir"])
    assert res["status"] == "in_progress"
    assert res["current_step_index"] == 0


def test_concurrent_access_by_living_process_blocked(test_env):
    """Living child process holding lock must cause parent to get LockError."""
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_live_block_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    lock_file = test_env["coord_dir"] / "session_sess_live_block_01.lock"

    child_code = f"""
import sys, os, time
from pathlib import Path
from eventcaption_ai.dispatch import SessionLock

lock = SessionLock(Path(r"{lock_file}"))
lock.acquire()
sys.stdout.write("locked\\n")
sys.stdout.flush()
time.sleep(2.0)
lock.release()
"""
    p = subprocess.Popen([sys.executable, "-c", child_code], stdout=subprocess.PIPE, text=True)
    line = p.stdout.readline()
    assert "locked" in line

    with pytest.raises(LockError, match="currently locked"):
        dispatcher.resume_session("sess_live_block_01", test_env["handoff_dir"])

    p.wait()


def test_replay_verifies_tampered_metadata_fails_closed(test_env):
    """Tampering assignment_id, cutoff, or hash in log MUST cause resume to fail closed."""
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_tamper_log_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    dispatcher.submit_decision(
        "sess_tamper_log_01",
        {"cutoff_ms": 1000, "decisions": [{"action": "WAIT"}]},
        test_env["handoff_dir"],
    )

    log_file = test_env["coord_dir"] / "decisions_sess_tamper_log_01.jsonl"
    orig_text = log_file.read_text(encoding="utf-8")
    entry = json.loads(orig_text.strip())

    # Case A: Tamper assignment_id
    tampered_aid = dict(entry, assignment_id="WRONG_ASSIGNMENT")
    log_file.write_text(json.dumps(tampered_aid) + "\n", encoding="utf-8")
    with pytest.raises(DispatchError, match="assignment_id mismatch"):
        dispatcher.load_session("sess_tamper_log_01")

    # Case B: Tamper cutoff_ms
    tampered_cutoff = dict(entry, cutoff_ms=999999)
    log_file.write_text(json.dumps(tampered_cutoff) + "\n", encoding="utf-8")
    with pytest.raises(DispatchError, match="cutoff mismatch"):
        dispatcher.load_session("sess_tamper_log_01")

    # Case C: Tamper checkpoint_sha256
    tampered_hash = dict(entry, checkpoint_sha256="0" * 64)
    log_file.write_text(json.dumps(tampered_hash) + "\n", encoding="utf-8")
    with pytest.raises(DispatchError, match="checkpoint hash mismatch"):
        dispatcher.load_session("sess_tamper_log_01")

    # Case D: Corrupted trailing line
    log_file.write_text(orig_text + '{"incomplete_json": \n', encoding="utf-8")
    with pytest.raises(DispatchError, match="Corrupted or partial JSON line"):
        dispatcher.load_session("sess_tamper_log_01")


def test_failure_media_immutability_no_hardlink(test_env):
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_immutable_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    handoff_mp4 = list(test_env["handoff_dir"].glob("prefix_sess_immutable_01_*.mp4"))[0]
    os.chmod(handoff_mp4, 0o666)
    handoff_mp4.write_bytes(b"TAMPERED_IN_HANDOFF_DIR")

    source_p1 = test_env["p1"]
    assert compute_sha256(source_p1) == test_env["sha1"]
    assert source_p1.read_bytes() == b"SYNTH_MP4_1000MS_DATA_FOR_UNIT_TEST"


def test_failure_destructive_reset_forbidden(test_env):
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_destruct_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    with pytest.raises(DispatchError, match="already exists"):
        dispatcher.init_session(
            session_id="sess_destruct_01",
            assignment_id="QUEUE_SYNTH",
            annotator_id="annotator_test",
            handoff_dir=test_env["handoff_dir"],
        )


def test_failure_handoff_path_overlap_rejected(test_env):
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    with pytest.raises(DispatchError, match="overlaps with coordinator"):
        dispatcher.init_session(
            session_id="sess_overlap_01",
            assignment_id="QUEUE_SYNTH",
            annotator_id="annotator_test",
            handoff_dir=test_env["coord_dir"],
        )


def test_failure_queue_tampering_detected(test_env):
    dispatcher = CoordinatorDispatcher(
        coordinator_dir=test_env["coord_dir"],
        queue_file=test_env["queue_file"],
    )
    dispatcher.init_session(
        session_id="sess_tamper_01",
        assignment_id="QUEUE_SYNTH",
        annotator_id="annotator_test",
        handoff_dir=test_env["handoff_dir"],
    )

    test_env["queue_file"].write_text("{}", encoding="utf-8")

    with pytest.raises(DispatchError, match="Queue file integrity violation"):
        dispatcher.submit_decision(
            "sess_tamper_01",
            {"cutoff_ms": 1000, "decisions": [{"action": "WAIT"}]},
            test_env["handoff_dir"],
        )
