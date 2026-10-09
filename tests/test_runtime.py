import json
import sys

import pytest

from eventcaption_ai.runtime import supervise
from eventcaption_ai.budget import Budget
from eventcaption_ai.model import messages, parse_response
from tests.test_foundation import snapshot, decision


def test_supervisor_receipts_and_budget_including_failures(tmp_path):
    budget = tmp_path / "budget.db"
    output = tmp_path / "success"
    receipt = supervise([sys.executable, "-c", "print('ok')"], output, budget, "feasibility", 10)
    assert receipt["status"] == "completed"
    assert "ok" in (output / "stdout.log").read_text()
    assert receipt["elapsed_seconds"] > 0
    with Budget(budget) as db:
        assert db.used("feasibility") == receipt["elapsed_seconds"]
    receipt = supervise([sys.executable, "-c", "raise RuntimeError('expected')"], tmp_path / "failed", budget, "feasibility", 10)
    assert receipt["status"] == "failed"
    receipt = supervise([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path / "timeout", budget, "feasibility", .3)
    assert receipt["status"] == "timeout"
    assert receipt["elapsed_seconds"] < 10
    with pytest.raises(FileExistsError):
        supervise([sys.executable, "-c", "pass"], output, budget, "feasibility", 10)


def test_supervisor_spawn_failure_keeps_receipt(tmp_path):
    receipt = supervise([str(tmp_path / "does-not-exist")], tmp_path / "failed", tmp_path / "budget.db", "A", 1)
    assert receipt["status"] == "failed"
    assert receipt["error"]
    assert json.loads((tmp_path / "failed/receipt.json").read_text())["status"] == "failed"


def test_model_input_is_only_prefix_and_output_is_not_repaired():
    snap = snapshot()
    context = dict(cutoff_ms=4000, evidence=snap.evidence(), frames=snap.frames, memory=[], active_events=[])
    chat, images = messages(context)
    assert len(images) == 1
    assert "4000" in str(chat)
    assert "WAIT" in str(chat)
    assert parse_response(json.dumps(decision()), context) == decision()
    assert parse_response('{"action":"WAIT"}', context) == {"action": "WAIT"}
    for raw in ['```json\n{"action":"WAIT"}\n```', '{"action":', '{"action":"WAIT","action":"EMIT"}', 'NaN']:
        with pytest.raises(ValueError):
            parse_response(raw, context)


def test_adapter_logs_raw_failure_and_never_retries(monkeypatch):
    from types import SimpleNamespace
    import torch
    import transformers
    from eventcaption_ai.model import SmolPolicy

    calls = []
    class Batch(dict):
        def to(self, *args, **kwargs):
            return self
    class Processor:
        raw = '{"action":"WAIT"}'
        def apply_chat_template(self, *args, **kwargs):
            return "prefix"
        def __call__(self, **kwargs):
            assert "videos" in kwargs and "images" not in kwargs
            return Batch(input_ids=torch.zeros((1, 3), dtype=torch.long))
        def batch_decode(self, *args, **kwargs):
            return [self.raw]
    class Model:
        dtype = torch.float32
        config = SimpleNamespace(text_config=SimpleNamespace(max_position_embeddings=2048))
        def to(self, *args):
            return self
        def eval(self):
            return self
        def generate(self, **kwargs):
            calls.append(kwargs)
            return torch.zeros((1, 5), dtype=torch.long)
    processor, model = Processor(), Model()
    monkeypatch.setattr(transformers.AutoProcessor, "from_pretrained", lambda *a, **kw: processor)
    monkeypatch.setattr(transformers.AutoModelForImageTextToText, "from_pretrained", lambda *a, **kw: model)
    trace = []
    policy = SmolPolicy("HuggingFaceTB/SmolVLM2-2.2B-Instruct", "a" * 40, trace.append, device="cpu")
    snap = snapshot()
    context = dict(cutoff_ms=4000, evidence=snap.evidence(), frames=snap.frames, memory=[], active_events=[])
    assert policy(context) == {"action": "WAIT"}
    processor.raw = '{"action":'
    with pytest.raises(ValueError):
        policy(context)
    assert len(calls) == 2
    assert trace[-1]["raw"] == processor.raw and trace[-1]["error"]
    model.config.text_config.max_position_embeddings = 3
    with pytest.raises(ValueError):
        policy(context)
    assert len(calls) == 2
    assert trace[-1]["error"]
    for checkpoint, revision, tokens in [("other", "a" * 40, 256),
                                         ("HuggingFaceTB/SmolVLM2-2.2B-Instruct", "main", 256),
                                         ("HuggingFaceTB/SmolVLM2-2.2B-Instruct", "a" * 40, 0)]:
        with pytest.raises(ValueError):
            SmolPolicy(checkpoint, revision, trace.append, max_tokens=tokens)
