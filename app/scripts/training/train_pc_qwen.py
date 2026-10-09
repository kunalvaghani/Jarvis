"""Real local LoRA gradient training for PC name/context resolution, not actions."""
from jarvis.paths import APP_ROOT, artifact_path
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import math

from scripts.training.train_qwen_weights import BASE,MODEL,REVISION,BASE_SHA256,dump
from jarvis.pc_context import inventory,prompt,resolve_entries,SYSTEM,PRIVATE,canonical_resolution


def dataset(config):
    entries=inventory(BASE,config)
    # Only public-looking source filenames, never file contents.
    for project in list(entries):
        if project['kind']!='project':continue
        try:
            for path in sorted(Path(project['path']).iterdir())[:80]:
                if path.is_file() and not path.is_symlink() and not PRIVATE.search(path.name) and path.suffix in {'.py','.md','.toml','.json','.ts','.tsx'}:
                    entries.append({'name':path.name,'kind':'file','path':str(path)})
        except OSError:pass
    entries=list({(e['kind'],e['path']):e for e in entries}.values())
    rng=random.Random(20260927)
    train=[];heldout=[]
    for index,entry in enumerate(entries[:100]):
        choices=rng.sample(entries,min(7,len(entries)))
        choices=[c for c in choices if c['kind']!=entry['kind'] or c['name']!=entry['name']]
        choices.append(entry);rng.shuffle(choices)
        for variant in range(3):
            goal=[f"open {entry['name']} {entry['kind']}",f"show my {entry['name']} {entry['kind']}",f"please locate the {entry['name']} {entry['kind']}"][variant]
            row={'id':f'entry-{index}-{variant}','goal':goal,'kind':entry['kind'],'entries':choices,
                 'target':resolve_entries(goal,choices,entry['kind'])}
            if row['target']!={'status':'resolved','kind':entry['kind'],'paths':[entry['path']]}:
                raise ValueError('Known-name example is mislabeled: '+row['id'])
            (heldout if variant==2 and index%5==0 else train if variant<2 else []).append(row)
    for index in range(12):
        choices=rng.sample(entries,min(8,len(entries)))
        goal=f"open missing-project-{index} project"
        row={'id':f'missing-{index}','goal':goal,'kind':'project','entries':choices,'target':resolve_entries(goal,choices,'project')}
        (heldout if index>=8 else train).append(row)
    # Real duplicate basenames: require clarification instead of guessing.
    groups={}
    for entry in entries:groups.setdefault((entry['kind'],entry['name']),[]).append(entry)
    for index,((kind,name),group) in enumerate((item for item in groups.items() if len(item[1])>1)):
        choices=group[:3]
        goal=f'open {name} {kind}'
        row={'id':f'ambiguous-{index}','goal':goal,'kind':kind,'entries':choices,'target':resolve_entries(goal,choices,kind)}
        (heldout if index%3==0 else train).append(row)
        if index>=11:break
    # Changed paths and removed entries teach context over memorized locations.
    for index,entry in enumerate(e for e in entries if e['kind']=='project'):
        choices=[{**entry,'path':str(Path(entry['path']).parent/('relocated-'+Path(entry['path']).name))}]
        goal=f"open {entry['name']} project"
        row={'id':f'relocated-{index}','goal':goal,'kind':'project','entries':choices,'target':resolve_entries(goal,choices,'project'),'synthetic_path':True}
        (heldout if index>=8 else train).append(row)
        if index>=11:break
    return {'entries':entries,'training':train,'heldout':heldout,
            'privacy':'metadata only; local Git-ignored artifact; no file contents or uploads',
            'split':'withheld request wording and selected missing/duplicate/relocated cases; entity names overlap'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rounds',type=int,default=2)
    parser.add_argument('--initialize-adapter',type=Path,default=BASE/'artifacts/training/qwen-jarvis-trained-20260927/adapter')
    parser.add_argument('--resume',type=Path)
    args=parser.parse_args()
    if not 1<=args.rounds<=10:parser.error('Use 1..10 rounds')
    out=artifact_path(BASE, 'qwen-pc-training-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir(exist_ok=False)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(BASE/'models/hf-training-cache'),USE_TF='0',USE_FLAX='0')
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    if not torch.cuda.is_available():raise RuntimeError('CUDA training required; no silent fallback')
    torch.set_num_threads(8);torch.manual_seed(42);random.seed(42)
    data=json.loads((args.resume.parent/'dataset.json').read_text()) if args.resume else dataset(json.loads((BASE/'config/config.json').read_text()))
    dump(out/'dataset.json',data)
    dataset_sha=hashlib.sha256((out/'dataset.json').read_bytes()).hexdigest()
    digest=hashlib.sha256()
    with (BASE/'models/qwen-jarvis-base/model.safetensors').open('rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    if digest.hexdigest()!=BASE_SHA256:raise ValueError('Base checksum mismatch')
    tokenizer=AutoTokenizer.from_pretrained(BASE/'models/qwen-jarvis-base',local_files_only=True)
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    if dtype!=torch.bfloat16:raise RuntimeError('This local PC run requires BF16 support')
    base=AutoModelForCausalLM.from_pretrained(BASE/'models/qwen-jarvis-base',torch_dtype=dtype,attn_implementation='sdpa',local_files_only=True).to('cuda')
    model=PeftModel.from_pretrained(base,args.resume or args.initialize_adapter,is_trainable=True,local_files_only=True)
    params=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(params,lr=1e-4)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads()
    def encoded(row,training=True):
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':prompt(row['goal'],row['entries'],row['kind'])}]
        prefix=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        text=tokenizer.apply_chat_template(messages+[{'role':'assistant','content':json.dumps(row['target'])}],tokenize=False) if training else prefix
        ids=tokenizer(text,add_special_tokens=False)['input_ids']
        if len(ids)>1536:raise ValueError('PC example exceeds context budget')
        tokens={'input_ids':torch.tensor([ids],device='cuda'),'attention_mask':torch.ones((1,len(ids)),dtype=torch.long,device='cuda')}
        if training:
            n=len(tokenizer(prefix,add_special_tokens=False)['input_ids']);tokens['labels']=torch.tensor([[-100]*n+ids[n:]],device='cuda')
        return tokens
    for row in data['training']+data['heldout']:encoded(row)
    report={'status':'training','base_model':MODEL,'base_revision':REVISION,'base_sha256':BASE_SHA256,
            'method':'actual LoRA forward/backward and AdamW updates on local PC metadata',
            'trainable_parameters':sum(p.numel() for p in params),'training_examples':len(data['training']),
            'heldout_examples':len(data['heldout']),'rounds':[],'dataset_sha256':dataset_sha,
            'initialized_from':str(args.resume or args.initialize_adapter)}
    def evaluate(name):
        model.eval();model.config.use_cache=True;rows=[]
        for row in data['heldout']:
            tokens=encoded(row,False)
            with torch.no_grad():result=model.generate(**tokens,do_sample=False,max_new_tokens=300,pad_token_id=tokenizer.eos_token_id)
            raw=tokenizer.decode(result[0,tokens['input_ids'].shape[1]:],skip_special_tokens=True)
            try:actual=json.loads(raw);passed=canonical_resolution(actual)==row['target']
            except ValueError:actual=None;passed=False
            rows.append({'id':row['id'],'passed':passed,'expected':row['target'],'actual':actual,'raw':raw})
            print(json.dumps({'evaluation':name,'id':row['id'],'passed':passed}),flush=True)
        result={'passed':sum(r['passed'] for r in rows),'total':len(rows),'rows':rows}
        dump(out/(name+'.json'),result);return result
    completed=0
    if args.resume:
        state=torch.load(args.resume/'training-state.pt',map_location='cpu',weights_only=True)
        if state['dataset_sha256']!=dataset_sha or state['base_revision']!=REVISION:raise ValueError('Resume mismatch')
        optimizer.load_state_dict(state['optimizer']);torch.set_rng_state(state['rng']);torch.cuda.set_rng_state_all(state['cuda_rng']);completed=state['completed_rounds']
    report['baseline']=evaluate('before-pc-training');dump(out/'results.json',report)
    for roundno in range(completed+1,completed+args.rounds+1):
        model.train();model.config.use_cache=False;losses=[];optimizer.zero_grad(set_to_none=True)
        before=[p.detach().float().cpu().clone() for p in params]
        order=list(data['training']);random.Random(42+roundno).shuffle(order)
        for i,row in enumerate(order):
            with torch.autocast('cuda',dtype=dtype):loss=model(**encoded(row)).loss
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite training loss')
            (loss/min(4,len(order)-(i//4)*4)).backward();losses.append(float(loss.detach()))
            if (i+1)%4==0 or i+1==len(order):
                torch.nn.utils.clip_grad_norm_(params,1);optimizer.step();optimizer.zero_grad(set_to_none=True)
            if i%20==0:print(json.dumps({'round':roundno,'example':i,'loss':losses[-1]}),flush=True)
        checkpoint=out/f'round-{roundno}'
        model.peft_config['default'].base_model_name_or_path=MODEL
        model.save_pretrained(checkpoint,safe_serialization=True,save_embedding_layers=False);tokenizer.save_pretrained(checkpoint)
        torch.save({'optimizer':optimizer.state_dict(),'rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),
                    'completed_rounds':roundno,'dataset_sha256':dataset_sha,'base_revision':REVISION},checkpoint/'training-state.pt')
        delta=sum(float((p.detach().float().cpu()-old).abs().sum()) for p,old in zip(params,before))
        if delta<=0:raise RuntimeError('No parameter updates')
        torch.cuda.empty_cache()
        result=evaluate(f'round-{roundno}-evaluation')
        report['rounds'].append({'round':roundno,'training_loss':sum(losses)/len(losses),'parameter_delta':delta,
                                'checkpoint':str(checkpoint),'adapter_sha256':hashlib.sha256((checkpoint/'adapter_model.safetensors').read_bytes()).hexdigest(),**result})
        dump(out/'results.json',report)
    best=max(report['rounds'],key=lambda r:(r['passed'],-r['training_loss']))
    report.update(status='complete',best_checkpoint=best['checkpoint'],completed=datetime.now(timezone.utc).isoformat(),
                  optimizer_steps=args.rounds*math.ceil(len(data['training'])/4),gradient_examples=args.rounds*len(data['training']))
    dump(out/'results.json',report);print(str(out/'results.json'),flush=True)


if __name__=='__main__':main()
