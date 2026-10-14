"""Explicit human/rights gates and source-level split validation for the new study."""
from copy import deepcopy
import re

from ..core.contract import finite, validate_decision, validate_evidence

SCENES = ("food_drink", "organizing", "craft_assembly")
SOURCE_FIELDS = {"source_id", "sha256", "origin_id", "session_id", "scenario_group", "split", "scene", "duration_ms", "training_allowed", "evaluation_allowed", "license_evidence", "pilot"}


def validate_manifest(sources):
    if not isinstance(sources, list) or not sources:
        raise ValueError("Nonempty source manifest required")
    identifiers = set()
    splits = {key: {} for key in ("sha256", "origin_id", "session_id", "scenario_group")}
    for row in sources:
        if not isinstance(row, dict) or set(row) != SOURCE_FIELDS:
            raise ValueError("Unexpected/missing source fields")
        for key in ("source_id", "origin_id", "session_id", "scenario_group", "license_evidence"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError(f"Missing {key}")
        if row["source_id"] in identifiers:
            raise ValueError("Duplicate source ID")
        identifiers.add(row["source_id"])
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid source SHA-256")
        if row["split"] not in ("train", "dev", "test") or row["scene"] not in SCENES:
            raise ValueError("Unknown split/scene")
        finite(row["duration_ms"], "duration")
        if not 30000 <= row["duration_ms"] <= 60000:
            raise ValueError("Selected segment must be 30–60 seconds")
        for key in ("training_allowed", "evaluation_allowed", "pilot"):
            if type(row[key]) is not bool:
                raise ValueError(f"{key} must be boolean")
        if row["split"] == "train" and not row["training_allowed"]:
            raise ValueError("Source not cleared for training")
        if not row["evaluation_allowed"]:
            raise ValueError("Source not cleared for study evaluation")
        if row["pilot"] and row["split"] == "test":
            raise ValueError("Pilot must not enter final test")
        for key, seen in splits.items():
            if row[key] in seen and seen[row[key]] != row["split"]:
                raise ValueError(f"Cross-split leakage: {key}")
            seen[row[key]] = row["split"]


def _context(context):
    if not isinstance(context, dict) or set(context) != {"cutoff_ms", "evidence", "memory", "active_events", "frames"}:
        raise ValueError("Only explicit input fields are allowed")
    cutoff, registry = context["cutoff_ms"], context["evidence"]
    validate_evidence(registry, cutoff)
    if not isinstance(context["frames"], list) or not context["frames"]:
        raise ValueError("Frame references required")
    last = -1
    for frame in context["frames"]:
        if not isinstance(frame, dict) or set(frame) != {"evidence_id", "media_ms", "path"}:
            raise ValueError("Invalid frame reference")
        finite(frame["media_ms"], "frame timestamp")
        if registry.get(frame["evidence_id"]) != frame["media_ms"] or frame["media_ms"] <= last:
            raise ValueError("Frame timestamps must match ordered registry")
        if not isinstance(frame["path"], str) or not frame["path"]:
            raise ValueError("Frame path required")
        last = frame["media_ms"]
    if not isinstance(context["memory"], list) or not isinstance(context["active_events"], list):
        raise ValueError("Memory and active events must be lists")
    for entry in context["memory"]:
        if not isinstance(entry, dict) or set(entry) != {"text", "evidence"} or not isinstance(entry["text"], str) or not entry["text"].strip():
            raise ValueError("Invalid memory entry")
        validate_evidence(entry["evidence"], cutoff)
        if not entry["evidence"] or any(ref not in registry or registry[ref] != timestamp for ref, timestamp in entry["evidence"].items()):
            raise ValueError("Memory evidence must match registry")
    seen = set()
    for event in context["active_events"]:
        if not isinstance(event, dict) or set(event) != {"record_id", "text", "start_ms", "end_ms", "event_status", "evidence_refs"}:
            raise ValueError("Invalid active event")
        if not isinstance(event["record_id"], str) or not event["record_id"] or event["record_id"] in seen:
            raise ValueError("Invalid/duplicate active record ID")
        seen.add(event["record_id"])
        candidate = {k: v for k, v in event.items() if k != "record_id"}
        validate_decision(dict(candidate, action="EMIT", previous_record_id=None), cutoff, registry)


def training_examples(sources, annotations, split="train"):
    validate_manifest(sources)
    if split not in ("train", "dev"):
        raise ValueError("Final test cannot be exported for training/model selection")
    if not isinstance(annotations, list) or not annotations:
        raise ValueError("Human-accepted annotations required")
    source_map = {row["source_id"]: row for row in sources}
    exported = []
    for row in annotations:
        if not isinstance(row, dict) or set(row) != {"source_id", "verified_by_human", "annotator", "context", "target"}:
            raise ValueError("Invalid annotation fields")
        if row["verified_by_human"] is not True or not isinstance(row["annotator"], str) or not row["annotator"].strip():
            raise ValueError("Human acceptance required; AI drafts are insufficient")
        source = source_map.get(row["source_id"])
        if source is None or source["split"] != split:
            raise ValueError("Unknown source or incorrect split")
        _context(row["context"])
        if row["context"]["cutoff_ms"] > source["duration_ms"]:
            raise ValueError("Prefix exceeds selected segment")
        validate_decision(row["target"], row["context"]["cutoff_ms"], row["context"]["evidence"])
        if row["target"]["action"] in ("REVISE", "WITHDRAW"):
            old = next((e for e in row["context"]["active_events"] if e["record_id"] == row["target"]["previous_record_id"]), None)
            if old is None:
                raise ValueError("Target must reference supplied active state")
            if row["target"]["action"] == "WITHDRAW" and any(old[k] != row["target"][k] for k in ("start_ms", "end_ms", "event_status")):
                raise ValueError("Withdrawal must preserve interval/status")
        exported.append(dict(source_id=row["source_id"], input=deepcopy(row["context"]), target=deepcopy(row["target"])))
    return exported
