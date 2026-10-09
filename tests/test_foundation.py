import copy
import json
import sqlite3
import subprocess
import sys

import pytest

from eventcaption_ai.stream import Frame, Snapshot
from eventcaption_ai.contract import validate_decision, validate_record
from eventcaption_ai.ledger import Ledger, Consumer
from eventcaption_ai.engine import Engine
from eventcaption_ai.data import validate_manifest, training_examples
from eventcaption_ai.evaluation import compare
from eventcaption_ai.budget import Budget


def snapshot(t=4000, index=None, value=0):
    stamp = min(t, 4000) if index is None else t
    return Snapshot((Frame(0 if index is None else index, stamp, stamp, (1, 1, 3), bytes([value] * 3)),), t)


def decision(action="EMIT", previous=None, **changes):
    result = dict(action=action, previous_record_id=previous,
                  text="The person picks up a cup.", start_ms=2000, end_ms=None,
                  event_status="ongoing", evidence_refs=["frame:0"])
    result.update(changes)
    return result


def test_lifecycle_wait_reopen_and_consumer(tmp_path):
    path = tmp_path / "ledger.db"
    with Ledger(path, "s") as ledger:
        assert ledger.submit({"action": "WAIT"}, snapshot(), 4000, {}) is None
        a = ledger.submit(decision(), snapshot(), 4100, {})
        b = ledger.submit(decision("REVISE", a["record_id"], end_ms=5000, event_status="ended"), snapshot(6000), 6100, {})
        c = ledger.submit(decision("WITHDRAW", b["record_id"], text="Earlier object identification was unsupported.", end_ms=5000, event_status="ended"), snapshot(7000), 7100, {})
        assert [r["operation"] for r in ledger.read_after()] == ["create", "revise", "withdraw"]
        assert len(ledger.decisions()) == 4
        assert a["end_ms"] is None
        assert c["event_id"] == a["event_id"]
        assert c["previous_record_id"] == b["record_id"]
        with pytest.raises(sqlite3.IntegrityError):
            ledger.db.execute("DELETE FROM records")
    with Ledger(path, "s") as ledger:
        consumer = Consumer()
        for record in ledger.read_after():
            assert consumer.apply(record)
        assert not consumer.apply(c)
        assert consumer.current(c["event_id"])["operation"] == "withdraw"
        with pytest.raises(ValueError):
            ledger.submit(decision("REVISE", c["record_id"]), snapshot(8000), 8000, {})
    with pytest.raises(ValueError):
        Ledger(path, "another-session")


@pytest.mark.parametrize("changes", [
    {"start_ms": 5000}, {"end_ms": 5000, "event_status": "ended"},
    {"end_ms": 1000, "event_status": "ended"}, {"start_ms": True},
    {"start_ms": float("nan")}, {"text": ""}, {"text": "   "},
    {"event_status": "ended"}, {"evidence_refs": []},
    {"evidence_refs": ["future"]}, {"evidence_refs": ["frame:0", "frame:0"]},
    {"commit_probability": .99}, {"action": "FORECAST"},
    {"previous_record_id": "host-must-assign"},
])
def test_reject_bad_decisions(changes):
    with pytest.raises(ValueError):
        validate_decision(decision(**changes), 4000, {"frame:0": 4000, "future": 5000})


@pytest.mark.parametrize("bad", [None, [], 1, "EMIT", {"action": "WAIT", "text": "leak"}])
def test_wrong_types(bad):
    with pytest.raises(ValueError):
        validate_decision(bad, 4000, {})


def test_atomic_rejection_stale_target_and_clocks(tmp_path):
    with Ledger(tmp_path / "a.db", "s") as ledger:
        a = ledger.submit(decision(), snapshot(), 4000, {})
        b = ledger.submit(decision("REVISE", a["record_id"]), snapshot(5000), 5000, {})
        for candidate, snap, clock in [
            (decision("REVISE", a["record_id"]), snapshot(6000), 6000),
            (decision("REVISE", "unknown"), snapshot(6000), 6000),
            (decision(), snapshot(6000), 4999),
            ({"action": "WAIT"}, snapshot(4999), 6000),
            (decision("WITHDRAW", b["record_id"], start_ms=1000), snapshot(6000), 6000),
        ]:
            with pytest.raises(ValueError):
                ledger.submit(candidate, snap, clock, {})
        assert len(ledger.decisions()) == 2
        assert len(ledger.read_after()) == 2


def test_consumer_rejects_tampering_gaps_and_invalid_interval(tmp_path):
    with Ledger(tmp_path / "a.db", "s") as ledger:
        a = ledger.submit(decision(), snapshot(), 4000, {})
        b = ledger.submit(decision("REVISE", a["record_id"]), snapshot(6000), 6000, {})
    consumer = Consumer()
    with pytest.raises(ValueError):
        consumer.apply(b)
    consumer.apply(a)
    for edits in [{"text": "tampered"}, {"end_ms": 5000}, {"session_id": "other"}]:
        bad = dict(a, **edits)
        with pytest.raises(ValueError):
            consumer.apply(bad)
    bad = dict(b, previous_record_id="wrong")
    with pytest.raises(ValueError):
        consumer.apply(bad)
    assert consumer.cursor == 1
    consumer.apply(b)
    with pytest.raises(ValueError):
        validate_record(dict(b, evidence_cutoff_ms=1000))


def test_prefix_isolation_bounded_memory_and_external_mutation(tmp_path):
    calls = []
    def policy(context):
        calls.append(copy.deepcopy(context))
        candidate = decision(start_ms=context["cutoff_ms"], evidence_refs=list(context["evidence"]))
        context["memory"].clear()
        return candidate
    with Ledger(tmp_path / "a.db", "s") as ledger:
        engine = Engine(ledger, policy, max_events=2, max_bytes=16384)
        for i in range(4):
            engine.step(snapshot(4000 + i * 1000, i), 4000 + i * 1000)
        assert len(engine.memory()) == 2
        assert len(calls[-1]["memory"]) == 2
        assert all(t <= c["cutoff_ms"] for c in calls for t in c["evidence"].values())
    def replay(future):
        seen = []
        with Ledger(tmp_path / f"{future}.db", "s") as ledger:
            engine = Engine(ledger, lambda ctx: seen.append(ctx) or {"action": "WAIT"})
            engine.step(snapshot(), 4000)
            first = copy.deepcopy(seen[0])
            engine.step(snapshot(6000, 1, future), 6000)
            return first
    assert replay(0) == replay(255)


def source(i, split="train", **changes):
    row = dict(source_id=f"v{i}", sha256=str(i) * 64, origin_id=f"origin{i}",
               session_id=f"session{i}", scenario_group=f"scenario{i}", split=split,
               scene="food_drink", duration_ms=30000, training_allowed=True,
               evaluation_allowed=True, license_evidence="self-recorded consent record", pilot=False)
    row.update(changes)
    return row


def test_manifest_no_split_leakage_or_license_repurposing():
    validate_manifest([source(1), source(2, "test")])
    for key in ["source_id", "sha256", "origin_id", "session_id", "scenario_group"]:
        with pytest.raises(ValueError):
            validate_manifest([source(1), source(2, "test", **{key: source(1)[key]})])
    for row in [source(1, training_allowed=False), source(1, "test", pilot=True), source(1, "test", evaluation_allowed=False)]:
        with pytest.raises(ValueError):
            validate_manifest([row])


def test_training_gates_and_target_separation():
    context = dict(cutoff_ms=4000, evidence={"frame:0": 4000}, memory=[], active_events=[],
                   frames=[dict(evidence_id="frame:0", media_ms=4000, path="frame.png")])
    example = dict(source_id="v1", verified_by_human=True, annotator="reviewer-1",
                   context=context, target=decision())
    result = training_examples([source(1)], [example])
    assert "target" not in result[0]["input"]
    assert result[0]["target"] == decision()
    for edits in [{"verified_by_human": False}, {"source_id": "missing"}, {"annotator": ""}]:
        with pytest.raises(ValueError):
            training_examples([source(1)], [dict(example, **edits)])
    for edits in [{"expected": "leak"}, {"memory": [{"evidence": {"future": 5000}}]},
                  {"frames": [dict(evidence_id="frame:0", media_ms=5000, path="frame.png")]}]:
        with pytest.raises(ValueError):
            training_examples([source(1)], [dict(example, context=dict(context, **edits))])
    with pytest.raises(ValueError):
        training_examples([source(1, "test")], [example])


def test_quality_gate_does_not_erase_errors_or_hide_misses():
    baseline = dict(captions=10, unsupported=5, events=10, covered=9)
    candidate = dict(captions=10, unsupported=4, events=10, covered=8)
    report = compare(baseline, candidate, [2000, 4000], device="iPhone 16 Pro", complete_latency=False)
    assert report["relative_error_reduction"] == pytest.approx(.2)
    assert not report["accepted"]  # coverage drop and incomplete latency evidence
    candidate["covered"] = 9
    assert compare(baseline, candidate, [4000] * 9, device="iPhone 16 Pro", complete_latency=True)["accepted"]
    assert not compare(baseline, candidate, [6000] * 9, device="iPhone 16 Pro", complete_latency=True)["accepted"]
    baseline["unsupported"] = 0
    assert compare(baseline, candidate, [], device="GPU", complete_latency=False)["relative_error_reduction"] is None


def test_budget_reserves_crashed_runs_and_stage_limits(tmp_path):
    path = tmp_path / "budget.db"
    with Budget(path) as budget:
        run = budget.reserve("feasibility", 7200)
        with pytest.raises(ValueError):
            budget.reserve("feasibility", 7201)
    with Budget(path) as budget:
        assert budget.used("feasibility") == 7200
        budget.finish(run, 100, "completed")
        assert budget.used("feasibility") == 100
        with pytest.raises(ValueError):
            budget.finish(run, 100, "completed")
        for stage, seconds in [("A", 14401), ("unknown", 1), ("A", 0)]:
            with pytest.raises(ValueError):
                budget.reserve(stage, seconds)


def test_cli_demo_is_explicitly_synthetic_and_no_overwrite(tmp_path):
    out = tmp_path / "demo"
    result = subprocess.run([sys.executable, "-m", "eventcaption_ai", "demo", "--output", str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    receipt = json.loads((out / "receipt.json").read_text())
    assert receipt["evidence_type"] == "synthetic_software_fixture"
    records = [json.loads(line) for line in (out / "records.jsonl").read_text().splitlines()]
    assert len(records) == 3
    assert [r["operation"] for r in records] == ["create", "revise", "withdraw"]
    again = subprocess.run([sys.executable, "-m", "eventcaption_ai", "demo", "--output", str(out)], capture_output=True)
    assert again.returncode != 0


def test_evidence_identity_cannot_change_on_reopen(tmp_path):
    path = tmp_path / "registry.db"
    with Ledger(path, "s") as ledger:
        a = ledger.submit(decision(), snapshot(), 4000, {})
    with Ledger(path, "s") as ledger:
        with pytest.raises(ValueError):
            ledger.submit(decision(), snapshot(6000, 0), 6000, {})
    consumer = Consumer()
    consumer.apply(a)
    b = dict(a, sequence_no=2, record_id="new", event_id="new", evidence_cutoff_ms=6000,
             emitted_elapsed_ms=6000, evidence_timestamps={"frame:0": 6000})
    with pytest.raises(ValueError):
        consumer.apply(b)


def test_emission_clock_sampled_after_policy_and_restart_wait_guard(tmp_path):
    clock = [4000]
    def policy(ctx):
        clock[0] += 2000
        return decision()
    path = tmp_path / "clock.db"
    with Ledger(path, "s") as ledger:
        engine = Engine(ledger, policy)
        record = engine.step(snapshot(), lambda: clock[0])
        assert record["emitted_elapsed_ms"] == 6000
        ledger.submit({"action": "WAIT"}, snapshot(8000), 8000, {})
    with Ledger(path, "s") as ledger:
        calls = []
        engine = Engine(ledger, lambda ctx: calls.append(ctx) or {"action": "WAIT"})
        with pytest.raises(ValueError):
            engine.step(snapshot(7000), 9000)
        assert calls == []
