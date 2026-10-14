"""Offline option-A trainer. Preparation is CPU-only; real runs require reviewed gates."""
import argparse
import json
import math
from pathlib import Path
import random
import sqlite3
import sys
import time

from .adapters import attach_lora, save_adapter, verify_adapter
from ..learning.model import CHECKPOINTS, messages
from ..streaming.processing import ProcessorRoute
from ..execution.runtime import supervise
from .training_data import (canonical, context_for_model, digest, file_hash, inspect_dataset,
                            load_prepared, prepare_dataset, read_json, write_json)


def encode_example(example, root, processor, max_tokens, max_target_tokens):
    """Compare actual processor tokens, never estimate a text-only prefix length."""
    import torch
    chat, images = messages(context_for_model(example['input'], root))
    prompt = processor.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
    target = json.dumps(example['target'], ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    full = processor.apply_chat_template(chat + [dict(role='assistant', content=[dict(type='text', text=target)])],
                                         tokenize=False, add_generation_prompt=False)
    prefix = processor(text=prompt, images=images, return_tensors='pt')
    encoded = processor(text=full, images=images, return_tensors='pt')
    prompt_ids = prefix['input_ids'][0][prefix['attention_mask'][0].bool()]
    full_ids = encoded['input_ids'][0][encoded['attention_mask'][0].bool()]
    length = len(prompt_ids)
    if len(full_ids) <= length or not torch.equal(full_ids[:length], prompt_ids):
        raise ValueError('Chat template token prefix mismatch; no guessed loss boundary')
    if len(full_ids) > max_tokens or len(full_ids) - length > max_target_tokens:
        raise ValueError('Example exceeds token budget; no truncation')
    positions = encoded['attention_mask'][0].bool().nonzero().flatten()
    labels = encoded['input_ids'].clone()
    labels[:] = -100
    labels[0, positions[length:]] = full_ids[length:]
    tokenizer = processor.tokenizer
    image_ids = []
    for name in ('image_token_id', 'video_token_id'):
        value = getattr(tokenizer, name, None)
        if isinstance(value, int):
            image_ids.append(value)
    vocab = tokenizer.get_vocab() if hasattr(tokenizer, 'get_vocab') else {}
    for token in ('<image>', '<fake_token_around_image>', '<global-img>'):
        if token in vocab:
            image_ids.append(vocab[token])
    if any((labels == value).any() for value in image_ids):
        raise ValueError('Image token inside answer')
    encoded['labels'] = labels
    return encoded


CONFIG_FIELDS = {'checkpoint', 'revision', 'phase', 'seed', 'device', 'dtype', 'max_steps',
                 'learning_rate', 'weight_decay', 'warmup_steps', 'gradient_accumulation',
                 'max_grad_norm', 'save_steps', 'max_tokens', 'max_target_tokens', 'lora'}


def validate_config(config):
    import re
    if set(config) != CONFIG_FIELDS:
        raise ValueError('Missing or unexpected training configuration fields')
    if config['checkpoint'] not in CHECKPOINTS or not re.fullmatch('[0-9a-f]{40}', config['revision']):
        raise ValueError('Supported checkpoint and pinned revision required')
    if config['phase'] not in ('pilot', 'main') or config['device'] not in ('cpu', 'cuda'):
        raise ValueError('Invalid phase/device')
    if config['dtype'] not in ('float32', 'bfloat16') or (config['device'] == 'cpu' and config['dtype'] != 'float32'):
        raise ValueError('Use float32 CPU or float32/bfloat16 CUDA; no unscaled fp16')
    for name in ('seed', 'warmup_steps'):
        if type(config[name]) is not int or config[name] < 0:
            raise ValueError(f'Invalid {name}')
    for name in ('max_steps', 'gradient_accumulation', 'save_steps', 'max_tokens', 'max_target_tokens'):
        if type(config[name]) is not int or config[name] < 1:
            raise ValueError(f'Invalid {name}')
    if config['warmup_steps'] >= config['max_steps'] or config['max_target_tokens'] > 1024:
        raise ValueError('Invalid warmup or target budget')
    for name in ('learning_rate', 'weight_decay', 'max_grad_norm'):
        value = config[name]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (name != 'weight_decay' and value == 0):
            raise ValueError(f'Invalid {name}')
    lora = config['lora']
    if set(lora) != {'target_modules', 'r', 'alpha', 'dropout'}:
        raise ValueError('Explicit LoRA configuration required')
    if any(type(lora[k]) is not int or lora[k] < 1 for k in ('r', 'alpha')):
        raise ValueError('Invalid LoRA rank/alpha')
    if type(lora['dropout']) not in (float, int) or not 0 <= lora['dropout'] < 1:
        raise ValueError('Invalid LoRA dropout')
    if not isinstance(lora['target_modules'], list) or not lora['target_modules'] or any(not isinstance(n, str) for n in lora['target_modules']):
        raise ValueError('Explicit LoRA target module paths required')
    return config


def validate_gates(gates, config, budget, phase, dataset_sha, config_sha):
    """A supplied reviewed receipt binds evidence to this exact recipe/data/ledger."""
    if (gates.get('schema') != 'training-gates/1' or gates.get('phase') != phase or
            gates.get('dataset_sha256') != dataset_sha or gates.get('config_sha256') != config_sha or
            gates.get('budget_reconciled') is not True or not isinstance(gates.get('reviewed_by'), str) or
            not gates['reviewed_by'].strip()):
        raise ValueError('Reviewed training gates are missing or do not match')
    budget = Path(budget).resolve()
    if not budget.is_file() or Path(gates.get('budget_path', '')).resolve() != budget:
        raise ValueError('Existing reconciled study budget required; cannot create a new ledger')
    required = {'data', 'budget'} | ({'ios_feasibility', 'recipe_lock'} if phase == 'main' else set())
    evidence = gates.get('evidence', {})
    for key in required:
        entry = evidence.get(key, {})
        path = Path(entry.get('path', ''))
        if not path.is_file() or file_hash(path) != entry.get('sha256'):
            raise ValueError(f'Missing or changed gate evidence: {key}')
    with sqlite3.connect(budget.as_uri() + '?mode=ro', uri=True) as db:
        columns = {r[1] for r in db.execute('PRAGMA table_info(runs)')}
        if columns != {'id', 'stage', 'reserved', 'actual', 'status'}:
            raise ValueError('Invalid budget ledger schema')
        from ..execution.budget import LIMITS
        for stage, reserved, actual, status in db.execute('SELECT stage,reserved,actual,status FROM runs'):
            if (stage not in LIMITS or type(reserved) not in (int, float) or
                    not math.isfinite(reserved) or not 0 < reserved <= 14400 or
                    status not in ('reserved', 'completed', 'failed', 'interrupted', 'timeout') or
                    (status == 'reserved' and actual is not None) or
                    (status != 'reserved' and (type(actual) not in (int, float) or not math.isfinite(actual) or actual < 0))):
                raise ValueError('Invalid budget row; reconcile before running')


def save_checkpoint(path, model, optimizer, scheduler, step, identity):
    import torch
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    save_adapter(model, path / 'adapter', identity)
    state = dict(optimizer=optimizer.state_dict(), scheduler=scheduler.state_dict(), step=step,
                 torch_rng=torch.get_rng_state(), python_rng=random.getstate(),
                 cuda_rng=torch.cuda.get_rng_state_all() if next(model.parameters()).is_cuda else [])
    torch.save(state, path / 'state.pt')
    write_json(path / 'complete.json', dict(identity=identity, step=step,
        files={p.relative_to(path).as_posix(): file_hash(p) for p in path.rglob('*') if p.is_file()}))


def restore_checkpoint(path, model, optimizer, scheduler, identity):
    import torch
    from peft import set_peft_model_state_dict
    from safetensors.torch import load_file
    from .training_data import inside
    path = Path(path)
    complete = read_json(path / 'complete.json')
    if complete['identity'] != identity:
        raise ValueError('Resume identity mismatch (recipe, base, data or environment)')
    for name, expected in complete['files'].items():
        if file_hash(inside(path, name)) != expected:
            raise ValueError('Checkpoint hash mismatch')
    verify_adapter(path / 'adapter', identity['checkpoint'], identity['revision'])
    set_peft_model_state_dict(model, load_file(str(path / 'adapter/adapter_model.safetensors')))
    state = torch.load(path / 'state.pt', map_location='cpu', weights_only=True)
    if state['step'] != complete['step']:
        raise ValueError('Checkpoint step mismatch')
    optimizer.load_state_dict(state['optimizer'])
    scheduler.load_state_dict(state['scheduler'])
    torch.set_rng_state(state['torch_rng'])
    random.setstate(state['python_rng'])
    if state['cuda_rng']:
        torch.cuda.set_rng_state_all(state['cuda_rng'])
    return state['step']


def train_loop(model, processor, dataset, root, config, output, identity, resume=None):
    """One example/microbatch; deterministic cyclic order supports exact step resume."""
    import torch
    from transformers import get_linear_schedule_with_warmup
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    parameters = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=config['learning_rate'], weight_decay=config['weight_decay'])
    scheduler = get_linear_schedule_with_warmup(optimizer, config['warmup_steps'], config['max_steps'])
    start = restore_checkpoint(resume, model, optimizer, scheduler, identity) if resume else 0
    if not 0 <= start < config['max_steps']:
        raise ValueError('Resume has no remaining optimizer steps')
    model.train()
    for name, module in model.named_modules():
        if name.split('.')[-1] in ('vision_model', 'connector'):
            module.eval()
    accumulation = config['gradient_accumulation']
    order = list(range(len(dataset)))
    random.Random(config['seed']).shuffle(order)
    started = time.perf_counter()
    with (output / 'loss.jsonl').open('x', encoding='utf-8') as trace:
        for step in range(start, config['max_steps']):
            optimizer.zero_grad(set_to_none=True)
            loss_sum = 0.0
            for micro in range(accumulation):
                index = order[(step * accumulation + micro) % len(order)]
                batch = encode_example(dataset[index], root, processor, config['max_tokens'], config['max_target_tokens'])
                batch = {k: v.to(device=config['device'], dtype=getattr(torch, config['dtype']) if v.is_floating_point() else v.dtype)
                         for k, v in batch.items()}
                loss = model(**batch).loss
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite training loss')
                (loss / accumulation).backward()
                loss_sum += loss.detach().float().item() / accumulation
            torch.nn.utils.clip_grad_norm_(parameters, config['max_grad_norm'], error_if_nonfinite=True)
            optimizer.step()
            scheduler.step()
            trace.write(canonical(dict(step=step+1, loss=loss_sum, elapsed_seconds=time.perf_counter()-started,
                                       quality_measured=False)) + '\n')
            trace.flush()
            if (step+1) % config['save_steps'] == 0 or step+1 == config['max_steps']:
                save_checkpoint(output / f'checkpoint-{step+1:06d}', model, optimizer, scheduler, step+1, identity)
    elapsed = time.perf_counter() - started
    return dict(steps=config['max_steps'], resumed_from_step=start, quality_measured=False,
                training_seconds=elapsed, microbatches_per_second=(config['max_steps']-start)*accumulation/elapsed)


def preflight(config_path, dataset_path, gates_path, budget, evaluation=False):
    config = validate_config(read_json(config_path))
    prepared = load_prepared(dataset_path)
    if prepared['receipt']['split'] != ('dev' if evaluation else 'train'):
        raise ValueError('Incorrect dataset split for requested operation')
    config_sha = digest(config)
    gates = read_json(gates_path)
    validate_gates(gates, config, budget, 'dev' if evaluation else config['phase'], prepared['receipt']['dataset_sha256'], config_sha)
    return config, prepared, gates


def worker(config, prepared, dataset_path, output, resume):
    import importlib.metadata
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor
    random.seed(config['seed'])
    torch.manual_seed(config['seed'])
    if config['device'] == 'cuda':
        if not torch.cuda.is_available():
            raise ValueError('CUDA requested but unavailable')
        if config['dtype'] == 'bfloat16' and not torch.cuda.is_bf16_supported():
            raise ValueError('bfloat16 unsupported on this GPU')
        torch.cuda.manual_seed_all(config['seed'])
        torch.cuda.reset_peak_memory_stats()
    identity = dict(config_sha256=digest(config), dataset_sha256=prepared['receipt']['dataset_sha256'],
                    checkpoint=config['checkpoint'], revision=config['revision'],
                    versions={p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'peft')})
    load_started = time.perf_counter()
    processor = ProcessorRoute(AutoProcessor.from_pretrained(config['checkpoint'], revision=config['revision'], local_files_only=True), 'video')
    base = AutoModelForImageTextToText.from_pretrained(config['checkpoint'], revision=config['revision'],
        local_files_only=True, torch_dtype=getattr(torch, config['dtype']), attn_implementation='eager')
    if config['max_tokens'] > base.config.text_config.max_position_embeddings:
        raise ValueError('Token limit exceeds model capacity')
    base.config.use_cache = False
    model, names = attach_lora(base, config['lora'])
    model.to(config['device'])
    load_seconds = time.perf_counter() - load_started
    write_json(Path(output) / 'trainable.json', dict(names=names, identity=identity))
    result = train_loop(model, processor, prepared['examples'], dataset_path, config, Path(output)/'training', identity, resume)
    result['peak_cuda_bytes'] = torch.cuda.max_memory_allocated() if config['device'] == 'cuda' else None
    result['load_seconds'] = load_seconds
    write_json(Path(output) / 'training-result.json', result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'prepare'):
        p = sub.add_parser(name)
        for option in ('manifest', 'annotations', 'media-index'):
            p.add_argument('--'+option, type=Path, required=True)
        p.add_argument('--split', choices=('train', 'dev'), required=True)
        if name == 'prepare':
            p.add_argument('--output', type=Path, required=True)
    for name in ('train', 'evaluate'):
        p = sub.add_parser(name)
        for option in ('config', 'dataset', 'gates', 'budget', 'output'):
            p.add_argument('--'+option, type=Path, required=True)
        p.add_argument('--seconds', type=float, required=True)
        p.add_argument('--resume', type=Path) if name == 'train' else p.add_argument('--adapter', type=Path)
        p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p = sub.add_parser('compare-dev')
    for option in ('dataset', 'baseline-trace', 'candidate-trace', 'output'):
        p.add_argument('--'+option, type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'compare-dev':
        from .training_eval import compare_traces
        rows = lambda path: [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        report = compare_traces(args.dataset, rows(args.baseline_trace), rows(args.candidate_trace))
        write_json(args.output, report)
        print(canonical(report))
        return 0
    if args.command in ('validate', 'prepare'):
        if args.command == 'validate':
            _, report, _ = inspect_dataset(args.manifest, args.annotations, args.media_index, args.split)
        else:
            report = prepare_dataset(args.manifest, args.annotations, args.media_index, args.output, args.split)
        print(canonical(report))
        return 0
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 14400:
        raise ValueError('Run cap is 4 hours including load')
    evaluation = args.command == 'evaluate'
    config, prepared, gates = preflight(args.config, args.dataset, args.gates, args.budget, evaluation)
    resume = getattr(args, 'resume', None)
    adapter = getattr(args, 'adapter', None)
    if adapter:
        verify_adapter(adapter, config['checkpoint'], config['revision'])
    if resume:
        identity = read_json(resume / 'complete.json')['identity']
        expected = dict(config_sha256=digest(config), dataset_sha256=prepared['receipt']['dataset_sha256'],
                        checkpoint=config['checkpoint'], revision=config['revision'])
        if any(identity.get(k) != v for k, v in expected.items()):
            raise ValueError('Resume identity mismatch before reservation')
    stage = 'feasibility' if config['phase'] == 'pilot' else 'A'
    if args.worker:
        reservation = read_json(args.output / 'reservation.json')
        with sqlite3.connect(args.budget.resolve().as_uri()+'?mode=ro', uri=True) as db:
            row = db.execute('SELECT stage,reserved,status FROM runs WHERE id=?', (reservation['run_id'],)).fetchone()
        if row != (stage, args.seconds, 'reserved'):
            raise ValueError('Worker requires an active matching reservation')
        write_json(args.output / 'worker-started.json', dict(config=config, dataset_sha256=prepared['receipt']['dataset_sha256'],
                    gates=gates, supersedes_checkpoint=str(resume.resolve()) if resume else None))
        if evaluation:
            from ..learning.model import SmolPolicy
            from .training_eval import evaluate_policy
            captured = []
            policy = SmolPolicy(config['checkpoint'], config['revision'], captured.append,
                                device=config['device'], max_tokens=config['max_target_tokens'], adapter=adapter,
                                dtype=config['dtype'], max_input_tokens=config['max_tokens'])
            evaluate_policy(args.dataset, policy, captured, args.output / 'evaluation')
        else:
            worker(config, prepared, args.dataset, args.output, resume)
        return 0
    command = [sys.executable, '-u', '-m', 'eventcaption_ai.training', args.command]
    for option in ('config', 'dataset', 'gates', 'budget', 'output'):
        command += ['--'+option, str(getattr(args, option).resolve())]
    command += ['--seconds', str(args.seconds), '--worker']
    if resume:
        command += ['--resume', str(resume.resolve())]
    if adapter:
        command += ['--adapter', str(adapter.resolve())]
    receipt = supervise(command, args.output, args.budget, stage, args.seconds)
    print(canonical(receipt))
    return 0 if receipt['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
