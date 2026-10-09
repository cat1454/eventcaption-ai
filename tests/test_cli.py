import json

import pytest

from eventcaption_ai.__main__ import main
from tests.test_foundation import source, decision


def test_cli_demo_replay_and_exclusive_output(tmp_path, monkeypatch, capsys):
    output = tmp_path / 'demo'
    monkeypatch.setattr('sys.argv', ['eventcaption', 'demo', '--output', str(output)])
    main()
    receipt = json.loads((output / 'receipt.json').read_text())
    assert receipt['model_inference'] is False
    with pytest.raises(FileExistsError): main()
    monkeypatch.setattr('sys.argv', ['eventcaption', 'replay', str(output / 'records.jsonl')])
    main()
    assert json.loads(capsys.readouterr().out)['records'] == 3


def test_cli_manifest_export_keeps_targets_separate(tmp_path, monkeypatch, capsys):
    manifest, annotations, output = [tmp_path / n for n in ('sources.json', 'labels.json', 'export.json')]
    manifest.write_text(json.dumps([source(1)]))
    context = dict(cutoff_ms=4000, evidence={'frame:0':4000}, memory=[], active_events=[],
                   frames=[dict(evidence_id='frame:0',media_ms=4000,path='frame.png')])
    annotations.write_text(json.dumps([dict(source_id='v1',verified_by_human=True,annotator='human',context=context,target=decision())]))
    monkeypatch.setattr('sys.argv',['eventcaption','validate-manifest',str(manifest)])
    main()
    assert json.loads(capsys.readouterr().out)['valid'] is True
    monkeypatch.setattr('sys.argv',['eventcaption','export-training','--manifest',str(manifest),'--annotations',str(annotations),'--output',str(output)])
    main()
    exported = json.loads(output.read_text())
    assert exported[0]['input'] == context
    assert 'target' not in exported[0]['input']
    assert exported[0]['target'] == decision()
