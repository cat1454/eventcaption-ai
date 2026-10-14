# EventCaption-AI instructions

Read docs/plan.md and docs/status.md first. Work only on AI; do not add backend/frontend or application UI. SmolVLM2 family is selected, size remains unvalidated. Main training requires accepted event-caption labels and the planned iOS feasibility checks.

Keep future frames unavailable to earlier outputs. Separate source cutoff, evidence sufficiency and wall-clock emission/display. Preserve append-only records and version links. Never invent commit probabilities or use keyword repair to certify semantics.

The event-caption/1 contract describes observed intervals, not forecasts. WAIT is trace-only. Occlusion or event completion alone does not invalidate an earlier caption.

Maintain bounded model context, honest raw traces, new output paths and the shared 40-hour GPU study budget (4 hours/run maximum, including load). This repository extraction does not authorize consuming all remaining budget without the research gates.

Preserve data, weights, results, negative evidence and user changes. Keep secrets and local media out of Git. Tests and fixtures do not demonstrate trained-model quality or mobile readiness. No model downloads or GPU calls in CI.

For model completion, use [docs/model-completion/README.md](docs/model-completion/README.md) as the task router. Load the relevant gate document before its stage; do not load every reference by default. Follow [agent-workflow.md](docs/model-completion/agent-workflow.md) for focused reads and evidence-linked handoffs. These documents do not approve runs or replace the research gates. Reuse unchanged evidence; never omit a required check to save tokens.
