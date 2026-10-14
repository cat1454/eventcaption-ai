# Research plan

**Title:** Mô tả sự kiện trong luồng video bằng SmolVLM2 với cơ chế học thời điểm phát và cập nhật mô tả.

The selected scope is observed streaming event captioning, bounded memory and learned emission/revision. Forecasting and intervention-based causal inference are outside acceptance. Three scene groups: food/drink preparation, organizing objects, simple craft/assembly. English captions; direct iPhone 16 Pro deployment with application work owned by teammates.

## Study

- Compare A: language-side LoRA learns WAIT/EMIT/REVISE/WITHDRAW plus caption/interval; B: fine-tuned captioner with a separate learned decision head.
- Start with frozen vision encoder. Lock modules, loss masking and hyperparameters after resource pilot, before main training. Validate B feature extraction/parity on iOS first.
- Select SmolVLM2 size using development and device feasibility, not final test.
- Compare pretrained periodic emission, fine-tuned periodic emission, A/B and selected policy with/without memory. Match captioner and inference conditions to isolate emission-policy effects.
- Initial memory budget: 16 events / 16 KiB, identical across comparisons. Declare minimal active state retained in no-history ablations.

## Data and acceptance

Pilot 30 videos, expand to 150 (50 per group), 30–60 seconds each. Planned train/dev/test: 90/30/30; pilot belongs to development data. Human-approved annotations and source rights are required. See [data](reference/data.md).

Targets: at least 20% relative reduction in unsupported captions versus the corresponding periodic baseline; coverage >=80% and no more than 5 percentage points below baseline; iPhone p95 first-correct-display latency <=5 seconds from sufficient evidence. These are not measured achievements. See [evaluation](reference/evaluation.md).

## Timeline and resources

8–12 weeks: weeks 1–2 pilot and device feasibility; 3–4 data/rubric/baseline and recipe lock; 5–6 A/B training/development; 7–8 ablations/conversion; 9–10 final evaluation/handoff; 11–12 contingency.

GPU cap: 40 hours total, <=4 hours/run including load/training/validation/inference. Stage quotas: feasibility 4h, A 10h, B 10h, ablation 8h, final 4h, reserve 4h. Use one budget ledger or explicitly allocated machine quotas; do not multiply the budget using separate ledgers. Unclosed runs retain their reservation. Option A training tooling is implemented (see [training](guides/training.md)); main training has not started and remains gated.

If quality/device targets fail, report not achieved. Do not silently lower thresholds, replace on-device execution with a server, or reuse final test for model selection.
