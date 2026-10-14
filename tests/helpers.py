"""Shared synthetic fixtures for CPU-only tests."""
from eventcaption_ai.streaming.stream import Frame, Snapshot


def snapshot(t=4000, index=None, value=0):
    stamp = min(t, 4000) if index is None else t
    return Snapshot((Frame(0 if index is None else index, stamp, stamp, (1, 1, 3), bytes([value] * 3)),), t)

def decision(action="EMIT", previous=None, **changes):
    result = dict(action=action, previous_record_id=previous,
                  text="The person picks up a cup.", start_ms=2000, end_ms=None,
                  event_status="ongoing", evidence_refs=["frame:0"])
    result.update(changes)
    return result

def source(i, split="train", **changes):
    row = dict(source_id=f"v{i}", sha256=str(i) * 64, origin_id=f"origin{i}",
               session_id=f"session{i}", scenario_group=f"scenario{i}", split=split,
               scene="food_drink", duration_ms=30000, training_allowed=True,
               evaluation_allowed=True, license_evidence="self-recorded consent record", pilot=False)
    row.update(changes)
    return row

