# Running reference inference

Install the base package for the synthetic demo and replay; add inference dependencies and the appropriate PyTorch build for real inference. Transformers is pinned to the existing tested adapter version. Use a separate environment; do not replace historical experiment environments.

```sh
python -m pip install ".[inference]"
python -m eventcaption_ai.inference --help
```

After explicitly obtaining the permitted model snapshot, an exploratory run can use:

```sh
python -m eventcaption_ai.inference --video data/approved.mp4 --checkpoint HuggingFaceTB/SmolVLM2-2.2B-Instruct --revision 482adb537c021c86670beed01cd58990d01e72e4 --output runs/new-run --budget runs/study-budget.sqlite --seconds 300 --max-media-ms 30000
```

This command uses GPU and requires a new output directory. Load time is included in the supervisor budget. It is an unvalidated pretrained policy, not a learned-policy benchmark. Use only sources cleared for the run purpose.

Raw model outputs and errors are traced without repair or retry. Valid prior records survive later failures in SQLite. A hard timeout may prevent the final JSONL export; the committed ledger remains authoritative. Do not interpret missing exports as zero emitted records.

The annotation CLI validates metadata and exports accepted train/dev examples; it does not run training:

```sh
python -m eventcaption_ai validate-manifest data/manifest.json
python -m eventcaption_ai export-training --manifest data/manifest.json --annotations data/accepted.json --split train --output data/new-export.json
```
