"""CPU-only training tests: random tiny models and synthetic pixels, no downloads."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from tests.helpers import decision, source


def inputs(tmp_path):
    raw = tmp_path / 'source.bin'
    raw.write_bytes(b'synthetic-source-not-a-quality-dataset')
    Image.new('RGB', (2, 2), (10, 20, 30)).save(tmp_path / 'frame.png')
    sources = [source(1, sha256=hashlib.sha256(raw.read_bytes()).hexdigest())]
    context = dict(cutoff_ms=4000, evidence={'frame:0': 4000}, memory=[], active_events=[],
                   frames=[dict(evidence_id='frame:0', media_ms=4000, path='frame.png')])
    labels = [dict(source_id='v1', verified_by_human=True, annotator='synthetic-test',
                   context=context, target=decision())]
    index = dict(sources={'v1': 'source.bin'}, frames={'frame.png': hashlib.sha256((tmp_path/'frame.png').read_bytes()).hexdigest()})
    paths = [tmp_path/n for n in ('sources.json','labels.json','media.json')]
    for p, obj in zip(paths, (sources, labels, index)):
        p.write_text(json.dumps(obj), encoding='utf-8')
    return paths, sources, labels, index


def test_preparation_hashes_gates_and_no_overwrite(tmp_path):
    from eventcaption_ai.training_data import prepare_dataset, load_prepared
    paths, _, _, _ = inputs(tmp_path)
    out = tmp_path/'prepared'
    report = prepare_dataset(*paths, out, 'train')
    assert report['actions'] == {'WAIT':0, 'EMIT':1, 'REVISE':0, 'WITHDRAW':0}
    assert report['missing_actions'] == ['WAIT','REVISE','WITHDRAW']
    prepared = load_prepared(out)
    assert prepared['examples'][0]['target'] == decision()
    assert 'target' not in prepared['examples'][0]['input']
    with pytest.raises(FileExistsError): prepare_dataset(*paths, out, 'train')
    frame = next((out/'frames').glob('*.png'))
    frame.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash'): load_prepared(out)


@pytest.mark.parametrize('kind', ['future','unreviewed','rights','test','pilot_train','memory','raw_hash','frame_hash','stale'])
def test_data_rejected_before_output(tmp_path, kind):
    from eventcaption_ai.training_data import prepare_dataset
    paths, sources, labels, media = inputs(tmp_path)
    if kind=='future': labels[0]['context']['frames'][0]['media_ms']=5000
    if kind=='unreviewed': labels[0]['verified_by_human']=False
    if kind=='rights': sources[0]['training_allowed']=False
    if kind=='test': sources[0]['split']='test'
    if kind=='pilot_train': sources[0]['pilot']=True
    if kind=='memory': labels[0]['context']['memory']=[dict(text='a'*17000,evidence={'frame:0':4000})]
    if kind=='raw_hash': sources[0]['sha256']='f'*64
    if kind=='frame_hash': media['frames']['frame.png']='f'*64
    if kind=='stale': labels[0]['target']=decision('REVISE','missing')
    for p, obj in zip(paths,(sources,labels,media)): p.write_text(json.dumps(obj))
    with pytest.raises(ValueError): prepare_dataset(*paths,tmp_path/'bad','train')
    assert not (tmp_path/'bad').exists()


class FakeProcessor:
    """Character tokens make exact prompt boundaries observable."""
    tokenizer = SimpleNamespace(pad_token_id=0, all_special_ids=[0,1])
    def apply_chat_template(self, chat, tokenize=False, add_generation_prompt=False):
        prompt = 'USER:' + json.dumps(chat[0]['content']) + '|ASSISTANT:'
        if len(chat)==1: return prompt
        return prompt + chat[1]['content'][0]['text'] + '~'
    def __call__(self, *, text, videos, return_tensors, **kwargs):
        assert len(videos)==1
        ids = torch.tensor([[ord(c)+2 for c in text]+[0,0]])
        return dict(input_ids=ids, attention_mask=(ids!=0).long(),pixel_values=torch.zeros(1,1,3,2,2))


def test_completion_only_mask_and_same_prompt(tmp_path):
    from eventcaption_ai.training_data import prepare_dataset, load_prepared, context_for_model
    from eventcaption_ai.training import encode_example
    from eventcaption_ai.processing import ProcessorRoute
    from eventcaption_ai.model import messages
    paths, _, _, _ = inputs(tmp_path)
    out=tmp_path/'prepared'
    prepare_dataset(*paths,out,'train')
    example=load_prepared(out)['examples'][0]
    processor=ProcessorRoute(FakeProcessor(),'video')
    encoded=encode_example(example,out,processor,max_tokens=8192,max_target_tokens=1024)
    chat,_=messages(context_for_model(example['input'],out))
    prefix=processor.apply_chat_template(chat,tokenize=False,add_generation_prompt=True)
    assert torch.all(encoded['labels'][0,:len(prefix)]==-100)
    assert torch.all(encoded['labels'][0,-2:]==-100)
    learned=encoded['labels'][encoded['labels']!=-100].tolist()
    assert ''.join(chr(x-2) for x in learned)==json.dumps(example['target'],ensure_ascii=False,allow_nan=False,separators=(',',':'))+'~'
    with pytest.raises(ValueError, match='token'): encode_example(example,out,processor,10,1024)


def tiny_model():
    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.vision_model=torch.nn.Linear(3,3)
            self.text_model=torch.nn.Module()
            self.text_model.proj=torch.nn.Linear(3,3)
        def forward(self,x): return self.text_model.proj(self.vision_model(x))
    return Tiny()


def test_lora_gradients_adapter_save_reload_and_forbidden_targets(tmp_path):
    from eventcaption_ai.adapters import attach_lora, save_adapter, load_adapter
    torch.manual_seed(2)
    base=tiny_model(); original=copy.deepcopy(base.state_dict())
    config=dict(target_modules=['text_model.proj'],r=2,alpha=4,dropout=0.0)
    model,names=attach_lora(base,config)
    assert names and all('lora_' in n for n in names)
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.1)
    x=torch.ones(1,3)
    for _ in range(2):
        loss=model(x).square().mean();loss.backward();opt.step();opt.zero_grad()
    assert base.vision_model.weight.grad is None
    assert torch.equal(base.vision_model.weight,original['vision_model.weight'])
    assert any(torch.count_nonzero(p).item()>0 for n,p in model.named_parameters() if 'lora_B' in n)
    out=tmp_path/'adapter'
    save_adapter(model,out,dict(checkpoint='test',revision='a'*40,config_sha256='b'*64))
    clean=tiny_model();clean.load_state_dict(original)
    loaded=load_adapter(clean,out,'test','a'*40)
    model.eval();loaded.eval()
    assert torch.allclose(model(x),loaded(x))
    with pytest.raises(ValueError): load_adapter(tiny_model(),out,'test','b'*40)
    for targets in [['vision_model'],['proj'],['text_model.missing']]:
        with pytest.raises(ValueError): attach_lora(tiny_model(),dict(config,target_modules=targets))


def test_checkpoint_restores_optimizer_scheduler_rng_and_rejects_mismatch(tmp_path):
    from eventcaption_ai.adapters import attach_lora
    from eventcaption_ai.training import save_checkpoint, restore_checkpoint
    torch.manual_seed(4)
    model,_=attach_lora(tiny_model(),dict(target_modules=['text_model.proj'],r=2,alpha=4,dropout=0.0))
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.01)
    sched=torch.optim.lr_scheduler.LambdaLR(opt,lambda step:1/(step+1))
    model(torch.ones(1,3)).sum().backward();opt.step();sched.step();opt.zero_grad()
    identity=dict(config_sha256='a'*64,dataset_sha256='b'*64,checkpoint='test',revision='c'*40)
    path=tmp_path/'checkpoint'
    save_checkpoint(path,model,opt,sched,1,identity)
    expected=torch.rand(2)
    assert restore_checkpoint(path,model,opt,sched,identity)==1
    assert torch.equal(torch.rand(2),expected)
    assert sched.last_epoch==1 and opt.state_dict()['state']
    with pytest.raises(ValueError): restore_checkpoint(path,model,opt,sched,dict(identity,dataset_sha256='d'*64))
    with pytest.raises(FileExistsError): save_checkpoint(path,model,opt,sched,2,identity)


def test_gates_fail_before_loading_or_reservation(tmp_path):
    from eventcaption_ai.training import validate_gates
    with pytest.raises(ValueError): validate_gates({}, {}, tmp_path/'missing.db', 'main', 'a'*64, 'b'*64)


def test_cli_is_offline_and_validate_does_not_create_output(tmp_path):
    from eventcaption_ai.training import main
    paths, _, _, _=inputs(tmp_path)
    assert main(['validate','--manifest',str(paths[0]),'--annotations',str(paths[1]),'--media-index',str(paths[2]),'--split','train'])==0


def config():
    return dict(checkpoint='HuggingFaceTB/SmolVLM2-500M-Video-Instruct',revision='a'*40,
                phase='pilot',seed=42,device='cpu',dtype='float32',max_steps=3,learning_rate=.01,
                weight_decay=0.,warmup_steps=0,gradient_accumulation=2,max_grad_norm=1.,
                save_steps=1,max_tokens=8192,max_target_tokens=1024,
                lora=dict(target_modules=['text_model.proj'],r=2,alpha=4,dropout=0.0))


def test_actual_smolvlm_architecture_gradients_cpu():
    from transformers import SmolVLMConfig, SmolVLMForConditionalGeneration
    from eventcaption_ai.adapters import attach_lora
    cfg=SmolVLMConfig(image_token_id=1,pad_token_id=0,scale_factor=2,use_cache=False,
        vision_config=dict(hidden_size=16,intermediate_size=32,num_hidden_layers=1,
                           num_attention_heads=2,image_size=8,patch_size=4),
        text_config=dict(model_type='llama',vocab_size=32,hidden_size=16,intermediate_size=32,
                         num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=2,max_position_embeddings=32))
    base=SmolVLMForConditionalGeneration(cfg)
    frozen=base.model.vision_model.embeddings.patch_embedding.weight.detach().clone()
    model,_=attach_lora(base,dict(target_modules=['model.text_model.layers.0.self_attn.q_proj',
        'model.text_model.layers.0.self_attn.v_proj'],r=2,alpha=4,dropout=0.0))
    result=model(input_ids=torch.tensor([[1,3,4,5]]),attention_mask=torch.ones(1,4,dtype=torch.long),
                 pixel_values=torch.ones(1,1,3,8,8),labels=torch.tensor([[-100,-100,4,5]]))
    result.loss.backward()
    assert any(p.grad is not None and torch.count_nonzero(p.grad) for n,p in model.named_parameters() if 'lora_B' in n)
    assert all(p.grad is None for n,p in model.named_parameters() if 'lora_' not in n)
    assert torch.equal(base.model.vision_model.embeddings.patch_embedding.weight,frozen)


def test_train_loop_resume_equivalent_and_no_overwrite(tmp_path):
    from eventcaption_ai.adapters import attach_lora
    from eventcaption_ai.training import train_loop
    from eventcaption_ai.training_data import prepare_dataset,load_prepared
    from eventcaption_ai.processing import ProcessorRoute
    class LM(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.text_model=torch.nn.Module()
            self.text_model.embed=torch.nn.Embedding(1024,8)
            self.text_model.proj=torch.nn.Linear(8,1024)
        def forward(self,input_ids,labels,**kwargs):
            logits=self.text_model.proj(self.text_model.embed(input_ids))
            return SimpleNamespace(loss=torch.nn.functional.cross_entropy(logits[:,:-1].reshape(-1,1024),labels[:,1:].reshape(-1)))
    torch.manual_seed(7); base=LM();initial=copy.deepcopy(base.state_dict())
    cfg=config(); model,_=attach_lora(base,cfg['lora'])
    paths,*_=inputs(tmp_path); root=tmp_path/'prepared';prepare_dataset(*paths,root,'train')
    examples=load_prepared(root)['examples']; processor=ProcessorRoute(FakeProcessor(),'video')
    identity=dict(config_sha256='a'*64,dataset_sha256='b'*64,checkpoint='test',revision='c'*40)
    result=train_loop(model,processor,examples,root,cfg,tmp_path/'run',identity)
    assert result['steps']==3
    resumed_base=LM();resumed_base.load_state_dict(initial)
    resumed,_=attach_lora(resumed_base,cfg['lora'])
    result=train_loop(resumed,processor,examples,root,cfg,tmp_path/'resume',identity,tmp_path/'run/checkpoint-000001')
    assert result['resumed_from_step']==1
    for (name,a),(_,b) in zip(model.named_parameters(),resumed.named_parameters()):
        assert torch.equal(a,b),name
    with pytest.raises(FileExistsError): train_loop(model,processor,examples,root,cfg,tmp_path/'run',identity)


def gate_fixture(tmp_path,phase='pilot'):
    from eventcaption_ai.budget import Budget
    from eventcaption_ai.training_data import file_hash
    budget=tmp_path/'budget.sqlite'
    with Budget(budget): pass
    evidence=tmp_path/'review.txt';evidence.write_text('synthetic reviewed receipt, not research clearance')
    gates=dict(schema='training-gates/1',phase=phase,dataset_sha256='a'*64,config_sha256='b'*64,
               budget_path=str(budget),budget_reconciled=True,reviewed_by='fixture',
               evidence={k:dict(path=str(evidence),sha256=file_hash(evidence)) for k in ['data','budget']})
    return gates,budget


def test_reviewed_gates_main_needs_ios_and_recipe_and_existing_ledger(tmp_path):
    from eventcaption_ai.training import validate_gates
    gates,budget=gate_fixture(tmp_path)
    validate_gates(gates,config(),budget,'pilot','a'*64,'b'*64)
    gates['phase']='main'
    with pytest.raises(ValueError,match='evidence'):validate_gates(gates,config(),budget,'main','a'*64,'b'*64)
    gates['evidence'].update(ios_feasibility=gates['evidence']['data'],recipe_lock=gates['evidence']['data'])
    validate_gates(gates,config(),budget,'main','a'*64,'b'*64)
    with pytest.raises(ValueError):validate_gates(gates,config(),tmp_path/'missing.sqlite','main','a'*64,'b'*64)
    assert not (tmp_path/'missing.sqlite').exists()


@pytest.mark.parametrize('key,value',[('revision','main'),('max_steps',0),('warmup_steps',3),('seed',True),
    ('device','auto'),('dtype','float16'),('learning_rate',float('nan')),('max_target_tokens',1025)])
def test_recipe_validation(key,value):
    from eventcaption_ai.training import validate_config
    cfg=config();assert validate_config(cfg)==cfg;cfg[key]=value
    with pytest.raises(ValueError):validate_config(cfg)


def test_state_prompt_parity():
    from eventcaption_ai.model import prompt_state
    shared=dict(cutoff_ms=4000,evidence={'frame:0':4000})
    event=dict(record_id='r1',text='Cup',start_ms=0,end_ms=None,event_status='ongoing')
    runtime=dict(shared,memory=[dict(text='Cup',evidence_timestamps={'frame:0':4000},operation='create')],
                 active_events=[dict(event,event_id='e1',version=1)])
    train=dict(shared,memory=[dict(text='Cup',evidence={'frame:0':4000})],active_events=[dict(event,evidence_refs=['frame:0'])])
    assert prompt_state(runtime)==prompt_state(train)


def test_dev_report_matches_inputs_keeps_raw_and_does_not_claim_semantics(tmp_path):
    from eventcaption_ai.training_eval import compare_traces
    from eventcaption_ai.training_data import prepare_dataset,load_prepared,digest
    paths,sources,labels,media=inputs(tmp_path);sources[0].update(split='dev',pilot=True)
    for p,obj in zip(paths,(sources,labels,media)):p.write_text(json.dumps(obj))
    root=tmp_path/'dev';prepare_dataset(*paths,root,'dev')
    example=load_prepared(root)['examples'][0]
    provenance=dict(policy='pretrained',checkpoint='tiny',revision='a'*40,input_route='RAM_prefix_video',
                    device='cpu',dtype='float32',max_tokens=256,max_input_tokens=8192,prompt_format='eventcaption-policy/2')
    baseline=[dict(index=0,input_sha256=digest(example['input']),raw='not JSON',error='invalid',provenance=provenance)]
    candidate=[dict(baseline[0],raw=json.dumps(decision()),error=None,provenance=dict(provenance,policy='lora'))]
    report=compare_traces(root,baseline,candidate)
    assert report['candidate']['contract_valid']==1 and report['baseline']['contract_valid']==0
    assert report['candidate']['unsupported_caption_rate'] is None
    assert report['candidate']['coverage'] is None
    assert report['quality_accepted'] is False
    candidate[0]['provenance']['max_tokens']=128
    with pytest.raises(ValueError,match='settings'):compare_traces(root,baseline,candidate)
    candidate[0]['provenance']['max_tokens']=256
    candidate[0]['input_sha256']='f'*64
    with pytest.raises(ValueError):compare_traces(root,baseline,candidate)


def test_incomplete_adapter_manifest_rejected(tmp_path):
    from eventcaption_ai.adapters import attach_lora,save_adapter,verify_adapter
    from eventcaption_ai.training import validate_gates
    model,_=attach_lora(tiny_model(),config()['lora'])
    out=tmp_path/'adapter';save_adapter(model,out,dict(checkpoint='test',revision='a'*40))
    (out/'unlisted.bin').write_bytes(b'not in receipt')
    with pytest.raises(ValueError,match='inventory'):verify_adapter(out,'test','a'*40)


def test_bad_budget_rejected(tmp_path):
    from eventcaption_ai.training import validate_gates
    gates,budget=gate_fixture(tmp_path)
    import sqlite3
    with sqlite3.connect(budget) as db:
        db.execute("INSERT INTO runs VALUES('bad','A',-10,NULL,'reserved')")
    with pytest.raises(ValueError,match='budget'):validate_gates(gates,config(),budget,'pilot','a'*64,'b'*64)


def test_frozen_vision_is_in_eval_mode_during_training(tmp_path,monkeypatch):
    from eventcaption_ai.adapters import attach_lora
    from eventcaption_ai.training import train_loop
    import eventcaption_ai.training as training
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__();self.vision_model=torch.nn.Dropout(.5)
            self.text_model=torch.nn.Module();self.text_model.proj=torch.nn.Linear(3,3)
        def forward(self,**kwargs):
            assert not self.vision_model.training
            return SimpleNamespace(loss=self.text_model.proj(torch.ones(1,3)).square().mean())
    model,_=attach_lora(Model(),config()['lora'])
    monkeypatch.setattr(training,'encode_example',lambda *a,**kw:{})
    monkeypatch.setattr(training,'save_checkpoint',lambda *a,**kw:None)
    train_loop(model,None,[{}],tmp_path,config(),tmp_path/'run',{})


def test_worker_and_cli_gates_reservations_and_duplicate_worker(tmp_path,monkeypatch):
    import eventcaption_ai.training as training
    from eventcaption_ai.training_data import prepare_dataset,digest
    from eventcaption_ai.budget import Budget
    paths,*_=inputs(tmp_path);dataset=tmp_path/'dataset';receipt=prepare_dataset(*paths,dataset,'train')
    cfg=config();config_path=tmp_path/'config.json';config_path.write_text(json.dumps(cfg))
    gates,budget=gate_fixture(tmp_path);gates.update(config_sha256=digest(cfg),dataset_sha256=receipt['dataset_sha256'])
    gate_path=tmp_path/'gates.json';gate_path.write_text(json.dumps(gates))
    out=tmp_path/'worker'
    args=['train','--config',str(config_path),'--dataset',str(dataset),'--gates',str(gate_path),
          '--budget',str(budget),'--seconds','10','--output',str(out)]
    calls=[]
    monkeypatch.setattr(training,'supervise',lambda command,output,budget_path,stage,seconds:calls.append((command,stage,seconds)) or {'status':'completed'})
    assert training.main(args)==0
    assert calls[0][1:]==('feasibility',10.) and '--worker' in calls[0][0]
    out.mkdir()
    with Budget(budget) as ledger: run_id=ledger.reserve('feasibility',10)
    (out/'reservation.json').write_text(json.dumps(dict(run_id=run_id)))
    monkeypatch.setattr(training,'worker',lambda *a:calls.append('worker'))
    assert training.main(args+['--worker'])==0 and calls[-1]=='worker'
    with pytest.raises(FileExistsError):training.main(args+['--worker'])
    gates['budget_reconciled']=False;gate_path.write_text(json.dumps(gates))
    with pytest.raises(ValueError):training.main(args)


def test_evaluate_policy_raw_errors_preserved_and_exclusive(tmp_path):
    from eventcaption_ai.training_eval import evaluate_policy
    from eventcaption_ai.training_data import prepare_dataset
    paths,sources,labels,media=inputs(tmp_path);sources[0].update(split='dev',pilot=True)
    for p,obj in zip(paths,(sources,labels,media)):p.write_text(json.dumps(obj))
    dataset=tmp_path/'dev';prepare_dataset(*paths,dataset,'dev')
    captured=[]
    def policy(context):
        captured.append(dict(stage='finished',raw='bad JSON',error='parse error'))
        raise ValueError('parse error')
    out=tmp_path/'eval';evaluate_policy(dataset,policy,captured,out)
    row=json.loads((out/'raw.jsonl').read_text())
    assert row['raw']=='bad JSON' and row['error']=='parse error'
    assert json.loads((out/'evaluation.json').read_text())['sequential_rollout'] is False
    with pytest.raises(FileExistsError):evaluate_policy(dataset,policy,captured,out)


def test_loading_adapter_cannot_target_vision(tmp_path):
    from eventcaption_ai.adapters import attach_lora,save_adapter,load_adapter
    from eventcaption_ai.training_data import read_json,file_hash
    model,_=attach_lora(tiny_model(),config()['lora'])
    out=tmp_path/'adapter';save_adapter(model,out,dict(checkpoint='test',revision='a'*40))
    cfg=read_json(out/'adapter_config.json');cfg['target_modules']='vision_model'
    (out/'adapter_config.json').write_text(json.dumps(cfg))
    receipt=read_json(out/'provenance.json');receipt['files']['adapter_config.json']=file_hash(out/'adapter_config.json')
    (out/'provenance.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='language'):load_adapter(tiny_model(),out,'test','a'*40)


def test_worker_loads_only_local_pinned_weights_and_records_trainables(tmp_path,monkeypatch):
    import transformers
    import eventcaption_ai.training as training
    calls=[]
    class Base:
        config=SimpleNamespace(text_config=SimpleNamespace(max_position_embeddings=8192),use_cache=True)
        def to(self,device):calls.append(('device',device));return self
    base=Base()
    def load(*a,**kw):
        assert kw['local_files_only'] is True and kw['revision']=='a'*40
        calls.append(('load',a[0]));return base
    monkeypatch.setattr(transformers.AutoModelForImageTextToText,'from_pretrained',load)
    monkeypatch.setattr(transformers.AutoProcessor,'from_pretrained',lambda *a,**kw:FakeProcessor() if kw['local_files_only'] else None)
    monkeypatch.setattr(training,'attach_lora',lambda model,cfg:(model,['base.text_model.proj.lora_A.default.weight']))
    monkeypatch.setattr(training,'train_loop',lambda *a:dict(steps=3,quality_measured=False))
    training.worker(config(),dict(receipt=dict(dataset_sha256='b'*64),examples=[{}]),tmp_path,tmp_path,None)
    assert base.config.use_cache is False
    assert json.loads((tmp_path/'trainable.json').read_text())['names']
    result=json.loads((tmp_path/'training-result.json').read_text())
    assert result['peak_cuda_bytes'] is None and result['load_seconds']>=0


def test_batch1_rehearsal_excluded_from_research():
    from eventcaption_ai.training_data import load_prepared, inspect_dataset
    batch1_prep = Path('runs/prepared-dev-batch1-20261012-v1')
    batch1_ann = Path('runs/annotation-batch1-20261012-v1/export')
    if batch1_prep.exists():
        with pytest.raises(ValueError, match='unverified rehearsal data excluded from research pipeline'):
            load_prepared(batch1_prep, technical_only=False)
        tech = load_prepared(batch1_prep, technical_only=True)
        assert tech['receipt']['research_eligible'] is False
        assert tech['receipt']['technical_check_only'] is True
        assert tech['receipt']['rehearsal_status'] == 'UNVERIFIED_REHEARSAL'
    if batch1_ann.exists():
        _, report, _ = inspect_dataset(
            batch1_ann / 'sources.json',
            batch1_ann / 'dev-labels.json',
            batch1_ann / 'media.json',
            'dev'
        )
        assert report['research_eligible'] is False
        assert report['technical_check_only'] is True
        assert report['rehearsal_status'] == 'UNVERIFIED_REHEARSAL'
        assert 'exclusion_reason' in report


def test_source_id_reusable_in_new_verified_session(tmp_path):
    from eventcaption_ai.training_data import prepare_dataset, load_prepared
    paths, sources, labels, media = inputs(tmp_path)
    sources[0]['source_id'] = 'v_oB6h3DscMUw'
    sources[0]['session_id'] = 'sess_human_session_P01_2026'
    labels[0]['source_id'] = 'v_oB6h3DscMUw'
    media['sources']['v_oB6h3DscMUw'] = media['sources'].pop('v1')
    for p, obj in zip(paths, (sources, labels, media)):
        p.write_text(json.dumps(obj), encoding='utf-8')
    out = tmp_path / 'new_verified_prep'
    rep = prepare_dataset(*paths, out, 'train')
    assert rep['research_eligible'] is True
    assert rep['technical_check_only'] is False
    assert rep['rehearsal_status'] == 'VERIFIED_CANDIDATE'
    loaded = load_prepared(out)
    assert loaded['examples'][0]['source_id'] == 'v_oB6h3DscMUw'

