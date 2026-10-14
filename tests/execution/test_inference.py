import json

import numpy as np
import pytest

from eventcaption_ai.inference import replay


def test_replay_exports_prior_records_on_bad_output(tmp_path):
    frames = [(np.zeros((2, 2, 3), dtype=np.uint8), t) for t in (0, 1000, 2000)]
    def policy(context):
        if context["cutoff_ms"] > 0:
            raise ValueError("Invalid model output")
        return dict(action="EMIT", previous_record_id=None, text="A cup is visible.", start_ms=0,
                    end_ms=None, event_status="ongoing", evidence_refs=["frame:0"])
    root = tmp_path / "run"
    with pytest.raises(ValueError):
        replay(frames, policy, root, cadence_ms=1000)
    assert len((root / "records.jsonl").read_text().splitlines()) == 1
    assert json.loads((root / "session.json").read_text())["status"] == "failed"


def test_replay_is_sequential_and_records_actual_clock(tmp_path):
    frames = [(np.zeros((2, 2, 3), dtype=np.uint8), t) for t in (0, 1000, 2000, 3000)]
    calls = []
    def policy(ctx):
        calls.append(ctx)
        assert all(f.media_ms <= ctx["cutoff_ms"] for f in ctx["frames"])
        return {"action": "WAIT"}
    replay(frames, policy, tmp_path / "run", cadence_ms=2000)
    assert [c["cutoff_ms"] for c in calls] == [0, 2000]
    receipt = json.loads((tmp_path / "run/session.json").read_text())
    assert receipt["status"] == "completed"
    assert receipt["mobile_measured"] is False
