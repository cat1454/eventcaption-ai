"""Offline, hash-bound preparation of accepted causal-prefix examples."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from ..core.contract import ACTIONS
from .data import training_examples, _context


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    def invalid(value):
        raise ValueError(f'Nonfinite JSON: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs, parse_constant=invalid)


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value) + '\n')


def inside(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path outside data boundary')
    return path


def check_bounds(context):
    _context(context)
    if len(context['frames']) > 4:
        raise ValueError('Training frame window exceeds inference limit (4)')
    state = {k: context[k] for k in ('memory', 'active_events')}
    if any(len(v) > 16 for v in state.values()) or len(canonical(state).encode('utf-8')) > 16384:
        raise ValueError('Context exceeds 16 events / 16 KiB state bound')


UNVERIFIED_REHEARSAL_DATASETS = {
    '4b1f7c624ded10ee75c242a28edf49828bad8f54b9958bc3bcdde5dcfafe8aba',
}
UNVERIFIED_REHEARSAL_SESSIONS = {
    'sess_batch1_P01',
    'sess_batch1_P11',
    'sess_batch1_P21',
}
UNVERIFIED_REHEARSAL_ANNOTATION_HASHES = {
    '72ccd71cf0ad1586f7068a446b2d6cdcff75846449aa11deddbf04a43b0209c9',
}


def is_unverified_rehearsal(sources, annotations_hash=None, dataset_sha256=None, report=None):
    if dataset_sha256 in UNVERIFIED_REHEARSAL_DATASETS:
        return True
    if report:
        if report.get('research_eligible') is False or report.get('rehearsal_status') == 'UNVERIFIED_REHEARSAL':
            return True
        if report.get('dataset_sha256') in UNVERIFIED_REHEARSAL_DATASETS:
            return True
        input_hashes = report.get('input_hashes', {})
        if any(h in UNVERIFIED_REHEARSAL_ANNOTATION_HASHES for h in input_hashes.values()):
            return True
    if annotations_hash in UNVERIFIED_REHEARSAL_ANNOTATION_HASHES:
        return True
    if sources:
        if any(s.get('session_id') in UNVERIFIED_REHEARSAL_SESSIONS or s.get('session_id', '').startswith('sess_batch1_') for s in sources):
            return True
    return False


def inspect_dataset(manifest, annotations, media_index, split):
    sources, labels, media = map(read_json, (manifest, annotations, media_index))
    if split not in ('train', 'dev'):
        raise ValueError('Final test is unavailable for training/model selection')
    if any(s.get('pilot') and s.get('split') != 'dev' for s in sources):
        raise ValueError('Pilot belongs to development only')
    examples = training_examples(sources, labels, split)
    if set(media) != {'sources', 'frames'}:
        raise ValueError('Media index requires sources and frames')
    root = Path(media_index).resolve().parent
    physical = {}
    for s in sources:
        if s['split'] != split:
            continue
        name = media['sources'].get(s['source_id'])
        if not isinstance(name, str):
            raise ValueError('Missing physical source path')
        path = inside(root, name)
        if not path.is_file() or file_hash(path) != s['sha256']:
            raise ValueError('Source hash mismatch')
        physical[str(path)] = s['sha256']
    seen, previous, transitions = set(), {}, Counter()
    for row in examples:
        ctx = row['input']
        check_bounds(ctx)
        key = (row['source_id'], ctx['cutoff_ms'])
        if key in seen or ctx['cutoff_ms'] <= previous.get(row['source_id'], (-1, 'START'))[0]:
            raise ValueError('Duplicate or nonmonotonic source cutoff')
        seen.add(key)
        old_action = previous.get(row['source_id'], (-1, 'START'))[1]
        transitions[old_action + '->' + row['target']['action']] += 1
        previous[row['source_id']] = (ctx['cutoff_ms'], row['target']['action'])
        shape = None
        for frame in ctx['frames']:
            name = frame['path']
            path = inside(root, name)
            expected = media['frames'].get(name)
            if not isinstance(expected, str) or not path.is_file() or file_hash(path) != expected:
                raise ValueError('Frame hash mismatch')
            with Image.open(path) as image:
                if image.format != 'PNG' or image.n_frames != 1 or image.width * image.height * 3 > 1920 * 1080 * 3:
                    raise ValueError('Single bounded PNG frame required')
                image.load()
                if shape is not None and shape != image.size:
                    raise ValueError('Video frames must have identical shape')
                shape = image.size
            physical[str(path)] = expected
    actions = Counter(r['target']['action'] for r in examples)
    ann_hash = file_hash(annotations)
    rehearsal = is_unverified_rehearsal(sources, annotations_hash=ann_hash)
    report = dict(split=split, examples=len(examples), actions={a: actions[a] for a in ACTIONS},
                  missing_actions=[a for a in ACTIONS if not actions[a]], transitions=dict(transitions),
                  quality_measured=False, physical_hashes=physical,
                  research_eligible=not rehearsal,
                  technical_check_only=rehearsal,
                  rehearsal_status='UNVERIFIED_REHEARSAL' if rehearsal else 'VERIFIED_CANDIDATE')
    if rehearsal:
        report['exclusion_reason'] = (
            'Excluded from research: automated pipeline rehearsal without genuine human verification '
            'or verified rights instrument (audit review 2026-10-12)'
        )
    return examples, report, root


def prepare_dataset(manifest, annotations, media_index, output, split):
    examples, report, root = inspect_dataset(manifest, annotations, media_index, split)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'frames').mkdir()
    for row in examples:
        for frame in row['input']['frames']:
            src = inside(root, frame['path'])
            name = 'frames/' + file_hash(src) + '.png'
            dest = output / name
            if not dest.exists():
                with dest.open('xb') as stream:
                    stream.write(src.read_bytes())
            if file_hash(dest) != report['physical_hashes'][str(src)]:
                raise ValueError('Frame hash changed during preparation')
            frame['path'] = name
    for name, src in [('sources.json', manifest), ('annotations.json', annotations), ('media-index.json', media_index)]:
        write_json(output / name, read_json(src))
    write_json(output / 'examples.json', examples)
    report['input_hashes'] = {str(Path(p).resolve()): file_hash(p) for p in (manifest, annotations, media_index)}
    report['files'] = {p.relative_to(output).as_posix(): file_hash(p) for p in output.rglob('*') if p.is_file()}
    report['dataset_sha256'] = digest(report)
    write_json(output / 'dataset.json', report)
    return report


def load_prepared(path, technical_only=False):
    path = Path(path)
    report = read_json(path / 'dataset.json')
    if digest({k: v for k, v in report.items() if k != 'dataset_sha256'}) != report['dataset_sha256']:
        raise ValueError('Dataset receipt hash mismatch')
    for name, expected in report['files'].items():
        file = inside(path, name)
        if not file.is_file() or file_hash(file) != expected:
            raise ValueError('Prepared file hash mismatch')
    for name, expected in report['physical_hashes'].items():
        if not Path(name).is_file() or file_hash(name) != expected:
            raise ValueError('Physical source/frame hash mismatch')
    # Recheck human/rights/split gates from the immutable snapshots, not flags in a report.
    sources = read_json(path / 'sources.json')
    if any(s.get('pilot') and s.get('split') != 'dev' for s in sources):
        raise ValueError('Pilot belongs to development only')

    rehearsal = is_unverified_rehearsal(sources, dataset_sha256=report.get('dataset_sha256'), report=report)
    if rehearsal:
        if not technical_only:
            raise ValueError(
                'Dataset rejected: unverified rehearsal data excluded from research pipeline '
                '(audit 2026-10-12: failed isolation, unverified human labels, and unverified rights)'
            )
        report['research_eligible'] = False
        report['technical_check_only'] = True
        report['rehearsal_status'] = 'UNVERIFIED_REHEARSAL'

    accepted = training_examples(sources, read_json(path / 'annotations.json'), report['split'])
    examples = read_json(path / 'examples.json')
    if len(examples) != len(accepted) or not examples:
        raise ValueError('Prepared examples do not match accepted annotations')
    for actual, original in zip(examples, accepted):
        normalized = deepcopy(actual)
        for f, old in zip(normalized['input']['frames'], original['input']['frames']):
            f['path'] = old['path']
        if normalized != original:
            raise ValueError('Prepared target/context changed')
        check_bounds(actual['input'])
    return dict(examples=examples, receipt=report)


@dataclass
class ImageFrame:
    evidence_id: str
    media_ms: float
    pixels: np.ndarray

    def rgb(self):
        return self.pixels


def context_for_model(context, root):
    check_bounds(context)
    result = deepcopy(context)
    frames = []
    for f in context['frames']:
        with Image.open(inside(root, f['path'])) as image:
            frames.append(ImageFrame(f['evidence_id'], f['media_ms'], np.array(image.convert('RGB'))))
    result['frames'] = frames
    return result
