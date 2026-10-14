"""Exact language-only LoRA targets and hash-verified local adapter artifacts."""
from pathlib import Path
import re

from .training_data import file_hash, inside, read_json, write_json


def _check_language_targets(model, targets):
    import torch
    modules = dict(model.named_modules())
    if not isinstance(targets, list) or not targets or any(not isinstance(n, str) for n in targets) or len(set(targets)) != len(targets):
        raise ValueError('Explicit unique language module names required')
    for name in targets:
        if (not isinstance(name, str) or 'text_model' not in name.split('.') or
                any(x in name.lower() for x in ('vision', 'connector', 'lm_head', 'embed')) or
                not isinstance(modules.get(name), torch.nn.Linear)):
            raise ValueError('LoRA target must be an exact language linear module')


def attach_lora(model, config):
    from peft import LoraConfig, get_peft_model
    targets = config['target_modules']
    _check_language_targets(model, targets)
    for p in model.parameters():
        p.requires_grad_(False)
    # Regex full-match prevents PEFT suffix matching a vision projection accidentally.
    expression = '(?:' + '|'.join(re.escape(n) for n in targets) + ')'
    adapted = get_peft_model(model, LoraConfig(r=config['r'], lora_alpha=config['alpha'],
        lora_dropout=config['dropout'], target_modules=expression, bias='none'))
    names = [n for n, p in adapted.named_parameters() if p.requires_grad]
    if not names or any('lora_' not in n or 'text_model' not in n.split('.') for n in names):
        raise ValueError('Unexpected trainable parameters')
    return adapted, names


def save_adapter(model, path, identity):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(path, safe_serialization=True, save_embedding_layers=False)
    files = {p.relative_to(path).as_posix(): file_hash(p) for p in path.rglob('*') if p.is_file()}
    write_json(path / 'provenance.json', dict(identity=identity, files=files))


def verify_adapter(path, checkpoint, revision):
    path = Path(path)
    receipt = read_json(path / 'provenance.json')
    inventory = {p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file() and p != path / 'provenance.json'}
    if inventory != set(receipt['files']):
        raise ValueError('Adapter inventory mismatch')
    if any(receipt['identity'].get(k) != v for k, v in [('checkpoint', checkpoint), ('revision', revision)]):
        raise ValueError('Adapter base checkpoint/revision mismatch')
    for name, expected in receipt['files'].items():
        if file_hash(inside(path, name)) != expected:
            raise ValueError('Adapter hash mismatch')
    if not {'adapter_config.json', 'adapter_model.safetensors'} <= set(receipt['files']):
        raise ValueError('Missing safe adapter files')
    config = read_json(path / 'adapter_config.json')
    if config.get('peft_type') != 'LORA' or config.get('bias') != 'none' or config.get('modules_to_save'):
        raise ValueError('Only language LoRA adapters supported')
    return receipt


def load_adapter(model, path, checkpoint, revision):
    from peft import PeftModel
    from safetensors import safe_open
    verify_adapter(path, checkpoint, revision)
    config = read_json(Path(path) / 'adapter_config.json')
    declared = config['target_modules']
    targets = ([name for name, _ in model.named_modules() if re.fullmatch(declared, name)]
               if isinstance(declared, str) else declared)
    _check_language_targets(model, targets)
    expected = {f'base_model.model.{name}.lora_{side}.weight' for name in targets for side in ('A', 'B')}
    with safe_open(str(Path(path) / 'adapter_model.safetensors'), framework='pt', device='cpu') as stream:
        if set(stream.keys()) != expected:
            raise ValueError('Adapter tensors do not match exact language targets')
    return PeftModel.from_pretrained(model, str(path), is_trainable=False, local_files_only=True)
