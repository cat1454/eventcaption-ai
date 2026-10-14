# Option A: language-side LoRA training

The pipeline learns the complete WAIT/EMIT/REVISE/WITHDRAW decision JSON. It is
implemented and CPU-tested; no accepted research dataset, trained policy quality
or iPhone feasibility is established by those tests. Existing research gates
remain closed. Option B and application/UI work are outside this implementation.

## Environment and configuration

Install the appropriate PyTorch build separately, then `pip install ".[test,training]"`.
Training dependencies pin Transformers 4.51.3 and PEFT 0.15.2. Tests use CPU tensors,
synthetic pixels and random tiny networks, including a tiny SmolVLM architecture;
CI sets Hugging Face offline mode and installs CPU PyTorch. No weights are downloaded.

[Example configuration](../../examples/training-option-a.json) is deliberately blocked
by a placeholder revision. Its checkpoint, first-layer target list and hyperparameters
illustrate the schema; they are **not a selected model size or accepted recipe**.
Provide an exact supported checkpoint revision already cached locally. Explicitly
list every intended `torch.nn.Linear` module under `text_model`; suffix-only targets,
vision, connector, embeddings and lm_head targets are rejected. Only LoRA A/B
parameters train. No full-weight or vision fine-tuning is enabled.

Microbatch size is one prefix; `gradient_accumulation` controls the effective batch.
The ordering is a seeded permutation cycled deterministically. AdamW, linear warmup/
decay and gradient clipping are used. CPU uses float32; CUDA permits float32 or
bfloat16 after checking device support. There is no implicit fp16 scaling or CPU
fallback. Freeze module selection, recipe and size after a resource pilot.

## Accepted data preparation

Use the existing source manifest and annotation schemas in [data.md](../reference/data.md).
Annotations must already have real human acceptance. Keep targets separate from
input context. Pilot sources must be `dev`; final test cannot be prepared here.
Each invocation takes annotations for exactly one split; the source manifest can
contain all splits so the existing cross-source/session leakage checks apply.

Add a local media-index JSON beside the indexed files:

```json
{
  "sources": {"source-id": "sources/original.mp4"},
  "frames": {"prefixes/frame-001.png": "ACTUAL_64_HEX_SHA256"}
}
```

`sources` maps IDs to original files whose SHA-256 matches the source manifest.
Annotation frame paths resolve relative to this index directory. All paths must
stay inside that directory after resolution. Frames must be single PNG images,
at most 1920x1080 RGB bytes, with equal dimensions within a prefix. At most four
frames and 16 events / 16 KiB state are allowed, matching the reference window.
Use audited causal-prefix extraction; matching file hashes do not prove a PNG was
extracted at the claimed timestamp. Human/curator provenance must establish that.

```powershell
python -m eventcaption_ai.training validate --manifest data/sources.json --annotations data/train-labels.json --media-index data/media.json --split train
python -m eventcaption_ai.training prepare --manifest data/sources.json --annotations data/train-labels.json --media-index data/media.json --split train --output runs/prepared-train-01
```

`validate` writes nothing. `prepare` creates a new directory with accepted-input
snapshots, hash-named frame copies, examples and `dataset.json`. Preserve originals:
they are rehashed at run preflight. Changed/missing media fail closed. Reports give
counts for all four actions, missing actions and consecutive action-pair counts;
these are descriptive counts, not independently verified event transitions.
Missing actions require appropriate accepted examples, not fabricated labels.

The same `messages()` and video `ProcessorRoute` are used for training/inference.
Runtime ledger memory and annotation memory are projected to the same prompt state.
The processor tokenizes both the generation prompt and complete assistant response;
the trainer requires an exact token-prefix match, then masks prompt and padding.
It never silently truncates. Image tokens in an answer are rejected. Assistant
JSON and its template terminator receive loss. Caption-language and semantic
correctness remain human review responsibilities, not keyword tests.

## Gates, budget and running

[Gate template](../../examples/training-gates.json) is deliberately unapproved. A real
reviewed receipt binds the prepared dataset hash, canonical config hash and absolute
path of the existing reconciled study ledger. Compute config hash with
`eventcaption_ai.training_data.digest(read_json(config_path))`; use `file_hash()` for
evidence files. Evidence entries use actual file paths and SHA-256. Paths in the
gate receipt are resolved from the invoking working directory; absolute paths are
recommended. This local receipt records a human decision; it does not authenticate
a reviewer or turn a claim into independent proof of rights or device readiness.

- `phase=pilot`: requires data evidence (rights, accepted labels, protocol and causal
  isolation) and budget reconciliation. Reserves the feasibility stage.
- `phase=main`: additionally requires `ios_feasibility` and `recipe_lock` evidence
  entries. The iOS evidence must cover the checks in the research plan, including
  B feature extraction/parity. Reserves stage A.
- For dev inference, use a separate receipt with `phase=dev`, the dev dataset hash
  and evaluation rights in data evidence. The recipe's pilot/main phase determines
  whether that inference is charged to feasibility/A.

```powershell
python -m eventcaption_ai.training train --config data/recipe.json --dataset runs/prepared-train-01 --gates data/train-gates.json --budget runs/study-budget.sqlite --seconds 600 --output runs/option-a-pilot-01
```

No ledger is initialized by this CLI. The shared cap is 40 hours, at most 14400
seconds per invocation including model load. Existing unclosed reservations still
count. Preflight validates before reservation; the supervised worker rechecks and
requires a matching active reservation. CPU real-model invocations conservatively
use the same supervisor/ledger; only isolated synthetic unit tests bypass it.
No automatic retries, model downloads or fallback to server inference occur.

Each output directory is new. Receipts/stdout/stderr survive failure. `loss.jsonl`
is append-only. Checkpoints include adapter safetensors, optimizer/scheduler, RNG,
step, model/revision, config/data identities and library versions. `complete.json`
is written last; incomplete checkpoints cannot resume. Hash verification is a
consistency check, not authentication of untrusted artifacts. PyTorch loads optimizer
state with `weights_only=True`.

Resume with the same recipe and `--resume runs/option-a-pilot-01/training/checkpoint-000010`
and a **new** output directory. It reserves a new run, restores the completed
optimizer-step boundary and preserves the old run. Do not extend `max_steps` in a
resume: that changes the schedule/recipe identity. A deliberately new recipe starts
a separately reviewed run. CUDA bitwise determinism is not claimed.

## Dev output diagnostics and inference

Run `evaluate` twice with the same dev dataset, config and generation settings,
once without an adapter and once with it; each gets its own budgeted output.

```powershell
python -m eventcaption_ai.training evaluate --config data/recipe.json --dataset runs/prepared-dev-01 --gates data/dev-gates.json --budget runs/study-budget.sqlite --seconds 300 --output runs/dev-base-01
python -m eventcaption_ai.training evaluate --config data/recipe.json --dataset runs/prepared-dev-01 --gates data/dev-gates.json --budget runs/study-budget.sqlite --seconds 300 --adapter runs/option-a-pilot-01/training/checkpoint-000100/adapter --output runs/dev-lora-01
python -m eventcaption_ai.training compare-dev --dataset runs/prepared-dev-01 --baseline-trace runs/dev-base-01/evaluation/raw.jsonl --candidate-trace runs/dev-lora-01/evaluation/raw.jsonl --output runs/dev-comparison-01.json
```

The comparison enforces identical ordered prefix inputs and matching generation
settings (checkpoint/revision, route, device/dtype, token limits and prompt format).
It reports strict contract
validity, active-record target validity, action agreement and reference-boundary
differences. Generation errors and raw responses remain available, with no JSON
repair/retry. This is **teacher-forced accepted context**, not autonomous sequential
rollout. Semantic unsupported-caption rate, event coverage, wrong revisions,
unsupported withdrawals and display latency stay null pending the required human
and device measurements. No `quality_accepted=true` is produced from these diagnostics.

The existing sequential reference inference CLI also accepts `--adapter PATH`.
Adapter loading verifies local files and exact base checkpoint/revision; record
contract and append-only ledger behavior remain unchanged. For study evaluation,
match settings, retain all published versions and perform the semantic review in
[evaluation.md](../reference/evaluation.md). Loss reduction or valid JSON alone does not establish
quality. Full app/runtime integration remains later; minimum feasibility checks
still precede main training.

Implementation API references: [PEFT LoRA](https://huggingface.co/docs/peft/v0.15.0/en/package_reference/lora)
and [PEFT checkpoint format](https://huggingface.co/docs/peft/v0.15.0/en/developer_guides/checkpoint).
