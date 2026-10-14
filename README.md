# EventCaption-AI

**Mô tả sự kiện trong luồng video bằng SmolVLM2 với cơ chế học thời điểm phát và cập nhật mô tả.**

AI-only research for PBL: observe video prefixes, maintain bounded event memory, emit English captions when evidence is sufficient, and revise or withdraw them with an append-only history. An action can be described before it finishes.

**Status:** software foundation and pretrained adapter; no trained emission policy, demonstrated quality improvement, or validated iPhone deployment yet. Synthetic demos and passing tests are not model-quality evidence.

The option-A LoRA trainer, accepted-data preparation and paired dev diagnostics are
now available; see [training](docs/guides/training.md). Real training remains gated on
accepted labels, source rights, reconciled budget and the planned feasibility checks.

## Install and run

Python 3.12 is the tested version. From the repository:

```sh
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install ".[test]"
python -m eventcaption_ai demo --output runs/software-demo-01
python -m eventcaption_ai replay runs/software-demo-01/records.jsonl
```

The demo is scripted, uses synthetic pixels, and makes no model/GPU calls. Output directories must be new.

For full tests including the CPU-mocked model adapter:

```sh
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install ".[test,inference]"
python -m pytest --cov=eventcaption_ai --cov-report=term-missing
```

For GPU inference, install the appropriate PyTorch build for your hardware instead of the CPU build. No weights are bundled. The adapter requires a locally available SmolVLM2 snapshot with an exact revision and does not download or retry silently. See [running inference](docs/guides/running.md).

For a metadata-only Google Drive video inventory (including folders with more than
1,000 files), install `.[drive]` and follow the [Windows OAuth and inventory guide](docs/guides/drive-inventory.md).
This CPU tool does not download media or certify sources/labels for training.

## Read next

1. [Documentation index](docs/README.md)
2. [Research plan](docs/plan.md)
3. [Architecture and contract](docs/reference/architecture.md)
4. [Data and annotation](docs/reference/data.md)
5. [Evaluation](docs/reference/evaluation.md)
6. [Current status and history](docs/status.md)
7. [AI-to-iOS handoff](docs/reference/handoff.md)

This repository owns AI tooling and reference inference only. Backend, frontend, camera UI and the iOS application/runtime are owned by teammates and are not included. iPhone 16 Pro remains the deployment target, not an established capability.

## Rights and artifacts

No open-source license has been granted for this repository yet. Public visibility is not a general grant of reuse rights. Model weights, datasets and any third-party components retain their own terms. Raw media, weights, local experiment logs and private information are intentionally excluded.

Historical research evidence is retained locally; the public repository contains a factual summary rather than broken links to private artifacts. No training or new model benchmark was performed as part of repository extraction.
