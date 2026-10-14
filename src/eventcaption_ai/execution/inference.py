"""Sequential desktop reference inference, explicitly not a realtime/mobile benchmark."""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid

from eventcaption_ai.streaming.stream import PrefixBuffer
from ..core.engine import Engine
from ..core.ledger import Ledger
from ..learning.model import SmolPolicy
from ..execution.runtime import supervise


def replay(frames, policy, output, cadence_ms=3000, use_memory=True):
    if type(cadence_ms) not in (int, float) or not 0 < cadence_ms <= 60000:
        raise ValueError("Invalid source cadence")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    receipt = dict(status="started", mode="sequential_source_replay", mobile_measured=False,
                   quality_measured=False, cadence_ms=cadence_ms, use_memory=use_memory)
    clock = lambda: (time.perf_counter() - started) * 1000
    with Ledger(output / "ledger.sqlite", str(uuid.uuid4())) as ledger:
        engine = Engine(ledger, policy, use_memory=use_memory)
        buffer = PrefixBuffer()
        due = 0
        try:
            for index, (rgb, timestamp) in enumerate(frames):
                if buffer.push(rgb, index, timestamp, clock()) and timestamp >= due:
                    engine.step(buffer.snapshot(), clock, getattr(policy, "provenance", {"type": "injected_policy"}))
                    due = timestamp + cadence_ms
            receipt["status"] = "completed"
        except BaseException as exc:
            receipt.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                           error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            ledger.export(output / "records.jsonl")
            (output / "decisions.json").write_text(json.dumps(ledger.decisions(), ensure_ascii=False, indent=2), encoding="utf-8")
            receipt["elapsed_seconds"] = time.perf_counter() - started
            (output / "session.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--adapter", type=Path, help="Local hash-verified LoRA adapter directory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=300)
    parser.add_argument("--max-media-ms", type=float, default=30000)
    parser.add_argument("--cadence-ms", type=float, default=3000)
    parser.add_argument("--no-memory", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker:
        command = [sys.executable, "-u", "-m", "eventcaption_ai.inference", *sys.argv[1:], "--worker"]
        receipt = supervise(command, args.output, args.budget, "feasibility", args.seconds)
        print(json.dumps(receipt, ensure_ascii=False))
        if receipt["status"] != "completed":
            raise SystemExit(1)
        return
    if not args.video.is_file() or not args.max_media_ms > 0:
        raise ValueError("Video and positive prefix limit required")
    from eventcaption_ai.streaming.video import video_frames
    with (args.output / "model-trace.jsonl").open("x", encoding="utf-8") as stream:
        def trace(row):
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
        load = time.perf_counter()
        try:
            model = SmolPolicy(args.checkpoint, args.revision, trace, adapter=args.adapter)
        finally:
            trace(dict(stage="load_finished_or_failed", elapsed_seconds=time.perf_counter() - load))
        replay(video_frames(args.video, args.max_media_ms), model, args.output / "session", args.cadence_ms, not args.no_memory)


if __name__ == "__main__":
    main()
