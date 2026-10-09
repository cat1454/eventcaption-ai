"""Strict structural checks; no keyword rules or semantic repair."""
import json
import math
from importlib.resources import files

from jsonschema import Draft202012Validator

SCHEMA = json.loads(files("eventcaption_ai").joinpath("contracts/event-caption-v1.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
CONTENT = {"text", "start_ms", "end_ms", "event_status", "evidence_refs"}
ACTIONS = ("WAIT", "EMIT", "REVISE", "WITHDRAW")


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite, nonnegative and non-boolean")


def validate_evidence(evidence, cutoff):
    finite(cutoff, "cutoff")
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a timestamp registry")
    for ref, timestamp in evidence.items():
        if not isinstance(ref, str) or not ref:
            raise ValueError("Invalid evidence ID")
        finite(timestamp, "evidence timestamp")
        if timestamp > cutoff:
            raise ValueError("Future evidence")


def _content(value, cutoff, evidence):
    finite(cutoff, "cutoff")
    finite(value["start_ms"], "start")
    if value["start_ms"] > cutoff:
        raise ValueError("Future event start")
    if not isinstance(value["text"], str) or not value["text"].strip() or len(value["text"]) > 500:
        raise ValueError("Caption must be nonempty and at most 500 characters")
    if value["event_status"] not in ("ongoing", "ended"):
        raise ValueError("Unknown event status")
    if value["event_status"] == "ongoing":
        if value["end_ms"] is not None:
            raise ValueError("Ongoing event has no known end")
    else:
        finite(value["end_ms"], "end")
        if not value["start_ms"] <= value["end_ms"] <= cutoff:
            raise ValueError("Invalid event interval")
    refs = value["evidence_refs"]
    if not isinstance(refs, list) or not 1 <= len(refs) <= 32 or any(not isinstance(r, str) or not r for r in refs):
        raise ValueError("Invalid evidence references")
    if len(set(refs)) != len(refs):
        raise ValueError("Duplicate evidence references")
    for ref in refs:
        if ref not in evidence:
            raise ValueError("Unknown evidence reference")
        finite(evidence[ref], "evidence timestamp")
        if evidence[ref] > cutoff:
            raise ValueError("Future evidence reference")


def validate_decision(value, cutoff, evidence):
    finite(cutoff, "cutoff")
    if not isinstance(value, dict) or value.get("action") not in ACTIONS:
        raise ValueError("Invalid decision/action")
    if value["action"] == "WAIT":
        if set(value) != {"action"}:
            raise ValueError("WAIT must not emit content")
        return
    if set(value) != CONTENT | {"action", "previous_record_id"}:
        raise ValueError("Unexpected or missing decision fields")
    previous = value["previous_record_id"]
    if value["action"] == "EMIT":
        if previous is not None:
            raise ValueError("EMIT cannot target an existing record")
    elif not isinstance(previous, str) or not previous:
        raise ValueError("Update requires previous record ID")
    _content(value, cutoff, evidence)


def validate_record(record):
    errors = list(VALIDATOR.iter_errors(record))
    if errors:
        raise ValueError(errors[0].message)
    try:
        json.dumps(record, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("Record must be finite JSON") from exc
    for key in ("sequence_no", "version"):
        if type(record[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    finite(record["emitted_elapsed_ms"], "emission clock")
    validate_evidence(record["evidence_timestamps"], record["evidence_cutoff_ms"])
    if set(record["evidence_timestamps"]) != set(record["evidence_refs"]):
        raise ValueError("Evidence registry must match cited references")
    _content(record, record["evidence_cutoff_ms"], record["evidence_timestamps"])


def validate_transition(old, new):
    if new["operation"] == "create":
        if old is not None:
            raise ValueError("Event already exists")
        return
    if old is None or old["operation"] == "withdraw" or new["previous_record_id"] != old["record_id"] or new["version"] != old["version"] + 1:
        raise ValueError("Missing, stale or withdrawn target")
    if new["event_id"] != old["event_id"] or new["evidence_cutoff_ms"] < old["evidence_cutoff_ms"]:
        raise ValueError("Event/cutoff mismatch")
    if new["operation"] == "withdraw" and any(new[k] != old[k] for k in ("start_ms", "end_ms", "event_status")):
        raise ValueError("Withdrawal must retain the previous interval/status")
