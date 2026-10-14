# Data and annotation

No accepted event-caption dataset is distributed with this repo. Target: 30-video pilot, then 150 selected segments of 30–60 seconds. Scene keys: `food_drink`, `organizing`, `craft_assembly`. Plan 30 train/10 dev/10 test videos per group.

Record original source, hash, capture session, scenario family, selected segment and reviewed rights. Keep source media and consent/license evidence outside Git. Permission to evaluate does not imply permission to train. Review near-duplicates manually; different IDs/hashes alone do not prove independence.

Two annotation passes:

1. View increasing prefixes without prior knowledge of the ending. Record when evidence first supports a caption and whether to WAIT/EMIT/REVISE/WITHDRAW. Do not rewrite earlier decisions using later knowledge.
2. Separately view the full sequence to label event boundaries and reference descriptions. These labels must not enter earlier model inputs.

Final test has two independent reviewers with model/configuration names hidden. Preserve individual judgments, disagreements and adjudication. AI drafts are not human acceptance.

Manifest JSON is an array with exactly these fields per source: source_id, sha256, origin_id, session_id, scenario_group, split, scene, duration_ms, training_allowed, evaluation_allowed, license_evidence, pilot. Hash must be the actual 64-hex source digest. Split must be train/dev/test. Pilot cannot enter test. Rights flags must follow source review, not convenience.

Annotations contain source_id, verified_by_human, annotator, context and target. Context has cutoff_ms, evidence, frames, memory and active_events only. Frame entries have evidence_id/media_ms/path; memory entries text/evidence; active events record_id/text/start_ms/end_ms/event_status/evidence_refs. The target follows the decision interface. Export separates model inputs from targets and blocks final-test export for training.

The validator checks metadata consistency, not file authenticity, legal interpretation or caption meaning. Before training, verify actual hashes/frame paths, rights and human review. Lock rubric, timestamp tolerance, event matching, splits and model-selection procedure after pilot.
