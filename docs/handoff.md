# AI-to-iOS handoff

AI owns data/model/preprocessing, memory, event decisions, reference inference, contract and evaluation. Teammates own the application, camera UI, rendering and iOS runtime. This repo does not implement BE/FE.

Target is direct iPhone 16 Pro inference. First verify SmolVLM2 size/runtime feasibility with the device team. Record device/iOS, Mac/Xcode, runtime version, checkpoint revision, processor settings and quantization.

Compare resize/crop, normalization, frame ordering, timestamps, tokenizer/chat template and context bounds against Python. For a separate commit head, verify layer/token pooling and feature shape/dtype/value parity before main training. No validated export or feature parity currently exists.

Implement the event-caption/1 consumer semantics described in [architecture](architecture.md), including version links, replay/gaps and withdrawals. Use synthetic records solely for compatibility checks.

Acceptance requires video replay plus a camera run of at least 10 minutes. Log capture/arrival, sufficient-evidence annotation, enqueue/inference completion, record ID, actual render time, memory, thermal state and errors. Establish source-to-display clock mapping. Do not substitute generation latency or desktop GPU timing for first-correct-display latency.

If device constraints fail, report failure and revisit scope explicitly. No implicit server fallback.
