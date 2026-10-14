# Architecture and contract

Observed frames → bounded prefix → SmolVLM2 policy with event memory → decision → durable ledger → reference consumer.

`stream.py` owns immutable frames/snapshots and bounded sampling; `video.py` decodes sequentially; `processing.py` adapts RAM frames to the processor. No complete source video is passed to the model.

`Engine.step(snapshot, emitted_ms, provenance)` accepts a clock callable for real inference so emission time is sampled after policy completion. Source timestamps and emission elapsed times are distinct. Replay is sequential desktop inference, not a realtime/mobile measurement.

`Ledger.submit` assigns IDs/versions and commits decision plus record atomically. WAIT logs a decision without a displayed caption. `Consumer.apply` verifies contiguous sequence, current previous-record link, event version, replay equality and evidence identity. This Python consumer is not a deployed iOS consumer.

## Public interface

The existing [event-caption/1 schema](../../src/eventcaption_ai/contracts/event-caption-v1.schema.json) is unchanged. Its legacy schema URI retains the original namespace for compatibility; the Python package is now `eventcaption_ai`.

- Create: new event ID, version 1, no previous record.
- Revise/withdraw: current previous-record ID, same event, next version.
- Ongoing: end_ms=null. Ended: start_ms <= end_ms <= evidence cutoff.
- Withdraw preserves the previous interval/status and gives a reason in text. It does not delete history.
- Evidence registry timestamps cannot change for the same ID or exceed cutoff.
- Semantic correctness still requires review. Completion or occlusion alone is not a reason to withdraw.

Memory is bounded independently of the full ledger. Model assertions are not ground truth. The no-history option still supplies minimal active event state needed to reference revisions; it is not zero historical information.

`SmolPolicy` is a pinned, local-only adapter with raw traces and no JSON repair/retry;
it can load a hash-verified language-side LoRA adapter. Option A now has an offline,
gated trainer and paired teacher-forced dev diagnostics (see [training](../guides/training.md)).
Option B training and trained-model quality remain unvalidated. Training and inference
share a canonical prompt projection of memory/active state. `Budget` and
`runtime.supervise` account for load and enforce subprocess time limits, retaining
reservations when terminal evidence is missing.
