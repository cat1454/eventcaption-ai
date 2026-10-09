"""Pinned SmolVLM2 prefix adapter. Pretrained inference is not a learned policy result."""
import json
import re
import time

from PIL import Image

from .contract import validate_decision, validate_evidence

CHECKPOINTS = {"HuggingFaceTB/SmolVLM2-2.2B-Instruct",
               "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
               "HuggingFaceTB/SmolVLM2-256M-Video-Instruct"}


def messages(context):
    validate_evidence(context["evidence"], context["cutoff_ms"])
    content, images = [], []
    for frame in context["frames"]:
        if frame.media_ms > context["cutoff_ms"] or context["evidence"].get(frame.evidence_id) != frame.media_ms:
            raise ValueError("Frame outside prefix or inconsistent registry")
        content.extend([dict(type="text", text=f"{frame.evidence_id} at {frame.media_ms} ms"), dict(type="image")])
        images.append(Image.fromarray(frame.rgb()))
    prompt = (
        'Describe observed events, never forecast. Return one JSON object, no markdown. '
        'Choose WAIT if there is no sufficiently grounded new caption or change: {"action":"WAIT"}. '
        'Otherwise use exactly: action (EMIT/REVISE/WITHDRAW), previous_record_id '
        '(null for EMIT; exact current record ID for changes), text (English, <=500 characters), '
        'start_ms, end_ms (null while ongoing), event_status (ongoing/ended), evidence_refs. '
        'All times describe already observed source media. Emit once enough evidence is visible, '
        'even before an action ends. Preserve identity when updating the same event. '
        'An ended action or occlusion does not invalidate a previously correct caption. '
        'Withdraw only an unsupported earlier assertion; keep its interval/status and explain in text. '
        'Memory contains model assertions, not ground truth. Context: '
        + json.dumps({k: context[k] for k in ("cutoff_ms", "evidence", "memory", "active_events")}, ensure_ascii=False, allow_nan=False)
    )
    content.append(dict(type="text", text=prompt))
    return [dict(role="user", content=content)], images


def parse_response(raw, context):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate JSON field")
            obj[key] = value
        return obj
    def invalid_constant(value):
        raise ValueError(f"Invalid JSON constant {value}")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 32768:
        raise ValueError("Output is not bounded text")
    candidate = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    validate_decision(candidate, context["cutoff_ms"], context["evidence"])
    return candidate


class SmolPolicy:
    def __init__(self, checkpoint, revision, trace, device="cuda", max_tokens=256):
        if checkpoint not in CHECKPOINTS or not re.fullmatch(r"[0-9a-f]{40}", revision or ""):
            raise ValueError("Require a supported SmolVLM2 checkpoint and exact pinned revision")
        if type(max_tokens) is not int or not 1 <= max_tokens <= 1024:
            raise ValueError("Invalid generation budget")
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText
        from eventcaption_ai.processing import ProcessorRoute
        self.trace, self.device, self.max_tokens, self.torch = trace, device, max_tokens, torch
        self.processor = ProcessorRoute(AutoProcessor.from_pretrained(checkpoint, revision=revision, local_files_only=True), "video")
        self.model = AutoModelForImageTextToText.from_pretrained(checkpoint, revision=revision,
                    local_files_only=True, torch_dtype=torch.float16 if device.startswith("cuda") else torch.float32,
                    attn_implementation="eager").to(device).eval()
        self.provenance = dict(checkpoint=checkpoint, revision=revision, policy="pretrained_prompt_unvalidated",
                               input_route="RAM_prefix_video", device=device, retry=0)

    def __call__(self, context):
        chat, images = messages(context)
        text = self.processor.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
        row = dict(cutoff_ms=context["cutoff_ms"], prompt=text, raw=None, error=None, provenance=self.provenance)
        self.trace(dict(stage="started", **row))
        started = time.perf_counter()
        try:
            inputs = self.processor(text=text, images=images, return_tensors="pt").to(self.device, dtype=self.model.dtype)
            length = inputs["input_ids"].shape[1]
            if length + self.max_tokens > self.model.config.text_config.max_position_embeddings:
                raise ValueError("Context too long; no silent truncation")
            with self.torch.inference_mode():
                generated = self.model.generate(**inputs, do_sample=False, max_new_tokens=self.max_tokens)
            row["raw"] = self.processor.batch_decode(generated[:, length:], skip_special_tokens=True)[0]
            row["generated_tokens"] = int(generated.shape[1] - length)
            row["token_limit_reached"] = row["generated_tokens"] >= self.max_tokens
            return parse_response(row["raw"], context)
        except BaseException as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            row["elapsed_seconds"] = time.perf_counter() - started
            self.trace(dict(stage="finished", **row))
