"""CPU reference CLI. Synthetic demo is explicitly not model inference."""
import argparse
import json
from pathlib import Path
import uuid

from eventcaption_ai.stream import Frame, Snapshot
from .data import validate_manifest, training_examples
from .ledger import Consumer, Ledger


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def demo(output):
    output.mkdir(parents=True, exist_ok=False)
    with Ledger(output / "ledger.sqlite", str(uuid.uuid4())) as ledger:
        previous = None
        for index, action in enumerate(("WAIT", "EMIT", "REVISE", "WITHDRAW")):
            timestamp = (index + 1) * 2000
            frame = Frame(index, timestamp, timestamp, (1, 1, 3), bytes([0, 0, 0]))
            snap = Snapshot((frame,), timestamp)
            candidate = {"action": action}
            if action != "WAIT":
                candidate.update(previous_record_id=previous, text="The person picks up a cup.",
                                 start_ms=2000, end_ms=None if action == "EMIT" else 5000,
                                 event_status="ongoing" if action == "EMIT" else "ended",
                                 evidence_refs=[frame.evidence_id])
                if action == "WITHDRAW":
                    candidate["text"] = "The earlier object identification was unsupported."
            record = ledger.submit(candidate, snap, timestamp + 100, {"evidence_type": "synthetic_software_fixture"})
            if record:
                previous = record["record_id"]
        ledger.export(output / "records.jsonl")
        write_json(output / "decisions.json", ledger.decisions())
    write_json(output / "receipt.json", dict(evidence_type="synthetic_software_fixture", records=3,
                                               model_inference=False, gpu_seconds=0, mobile_measured=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("demo")
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("validate-manifest")
    p.add_argument("path", type=Path)
    p = sub.add_parser("export-training")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--split", choices=("train", "dev"), default="train")
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("replay")
    p.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "demo":
        demo(args.output)
    elif args.command == "validate-manifest":
        sources = json.loads(args.path.read_text(encoding="utf-8"))
        validate_manifest(sources)
        print(json.dumps({"valid": True, "sources": len(sources), "human_rights_audit": "still_required"}))
    elif args.command == "export-training":
        result = training_examples(json.loads(args.manifest.read_text(encoding="utf-8")),
                                   json.loads(args.annotations.read_text(encoding="utf-8")), args.split)
        write_json(args.output, result)
    else:
        consumer = Consumer()
        for line in args.path.read_text(encoding="utf-8").splitlines():
            consumer.apply(json.loads(line))
        print(json.dumps({"records": consumer.cursor, "events": len(consumer.events), "semantic_acceptance": False}))


if __name__ == "__main__":
    main()
