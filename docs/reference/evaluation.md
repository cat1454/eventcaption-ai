# Evaluation

Targets agreed for the study:

- Unsupported-caption rate reduced by >=20% relative to matched periodic emission baseline.
- Event coverage >=80%, with <=5 percentage-point drop from baseline.
- iPhone 16 Pro p95 first-correct-display latency <=5000 ms after sufficient evidence.

Count every published caption version. A later correction never erases a prior unsupported caption. Report missing events separately; latency among covered events alone does not prove coverage. Zero baseline error makes relative reduction undefined.

Lock semantic rubric, event-matching policy and time tolerance before main experiments. Compare on the same source cohort/prefixes and budgets. Report duplicate captions, correct/incorrect revisions, unsupported withdrawals, interval accuracy and uncertainty clustered by video/source. Select on development, then freeze and open final test once.

`evaluation.compare` is only a numerical calculator for reviewed counts and supplied latency measurements. Its `accepted` field means numerical thresholds were met, not independent semantic or device certification. It does not compute semantic judgments, matching or confidence intervals.

Software tests cover future-frame isolation, immutable history, state transitions, malformed output, split leakage, budget/timeouts and packaging. Model mocks and synthetic fixtures are not quality evidence. No GPU or downloaded model is used in CI.
