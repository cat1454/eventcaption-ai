"""Threshold calculator from reviewed counts, not an automatic semantic judge."""
import math


def _counts(value):
    if not isinstance(value, dict) or set(value) != {"captions", "unsupported", "events", "covered"}:
        raise ValueError("Expected reviewed caption/event counts")
    if any(type(n) is not int or n < 0 for n in value.values()):
        raise ValueError("Counts must be nonnegative integers")
    if value["unsupported"] > value["captions"] or value["covered"] > value["events"] or value["events"] == 0:
        raise ValueError("Inconsistent counts")


def compare(baseline, candidate, latencies_ms, *, device, complete_latency):
    """Caller must count *all* published versions; a revision never erases an error.

    This computes numerical gates only. Independent paired review, matching rubric,
    provenance, CI and device traces are still required to accept a research claim.
    """
    _counts(baseline)
    _counts(candidate)
    if baseline["events"] != candidate["events"]:
        raise ValueError("Comparisons require the same event cohort")
    if type(complete_latency) is not bool or not isinstance(latencies_ms, list):
        raise ValueError("Invalid latency metadata")
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in latencies_ms):
        raise ValueError("Invalid latency")
    if complete_latency and len(latencies_ms) != candidate["covered"]:
        raise ValueError("Need first-correct-display latency for every covered event")
    b_rate = baseline["unsupported"] / baseline["captions"] if baseline["captions"] else None
    c_rate = candidate["unsupported"] / candidate["captions"] if candidate["captions"] else None
    reduction = (b_rate - c_rate) / b_rate if b_rate and c_rate is not None else None
    b_coverage = baseline["covered"] / baseline["events"]
    coverage = candidate["covered"] / candidate["events"]
    p95 = sorted(latencies_ms)[math.ceil(.95 * len(latencies_ms)) - 1] if latencies_ms else None
    quality = reduction is not None and reduction >= .2 - 1e-12
    coverage_pass = coverage >= .8 and coverage >= b_coverage - .05 - 1e-12
    latency_pass = complete_latency and device == "iPhone 16 Pro" and p95 is not None and p95 <= 5000
    return dict(relative_error_reduction=reduction, baseline_error_rate=b_rate, candidate_error_rate=c_rate,
                coverage=coverage, missed_events=candidate["events"] - candidate["covered"],
                p95_first_correct_display_ms=p95, quality_gate=quality, coverage_gate=coverage_pass,
                latency_gate=latency_pass, accepted=quality and coverage_pass and latency_pass,
                evidence_type="numerical_gate_only_requires_review_and_device_artifacts")
