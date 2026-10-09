"""Generate new programs with trained Qwen weights and execute real CLI checks.

No experience recall, repair feedback or training-set source reuse. Larger inputs
are never shown to the model; prompts contain only the curriculum's two examples.
"""
from jarvis.paths import APP_ROOT, artifact_path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from scripts.training.train_qwen_weights import BASE, SYSTEM, prompt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--all-projects',action='store_true',help='Generate all 100 projects, then also check larger inputs on ten retained programs')
    args=parser.parse_args()
    checkpoint=args.checkpoint.resolve()
    if not checkpoint.is_relative_to(BASE/'artifacts') or not (checkpoint/'adapter_model.safetensors').is_file():
        parser.error('Use a local completed adapter checkpoint')
    os.environ.update(HF_HOME=str(BASE/'models/hf-training-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TF='0')
    import torch
    torch.set_num_threads(8)
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    from jarvis.coding_curriculum import catalogue
    from scripts.training.train_coding import inspect_source,check
    from scripts.verification.verify_coding_stress import stress_cases
    root=artifact_path(BASE, ('qwen-trained-projects-' if args.all_projects else 'qwen-trained-stress-')+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    root.mkdir(exist_ok=False)
    tokenizer=AutoTokenizer.from_pretrained(checkpoint,local_files_only=True)
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model=AutoModelForCausalLM.from_pretrained(BASE/'models/qwen-jarvis-base',torch_dtype=dtype,local_files_only=True).to('cuda')
    model=PeftModel.from_pretrained(model,checkpoint,local_files_only=True).eval()
    projects={p['name']:p for p in catalogue()}
    stress=stress_cases()
    dataset_path=checkpoint.parent/'dataset.json'
    data=json.loads(dataset_path.read_text(encoding='utf-8'))
    training_ids={p['id'] for p in data['training']}
    selected={name:project['cases'] for name,project in projects.items()} if args.all_projects else {name:[case] for name,case in stress.items()}
    report={'status':'running','checkpoint':str(checkpoint),'precision':str(dtype),
            'adapter_sha256':hashlib.sha256((checkpoint/'adapter_model.safetensors').read_bytes()).hexdigest(),
            'method':'fresh trained-weight inference; no experience recall or execution-feedback repair','projects':[],'larger_cases':[]}
    for name,cases in selected.items():
        project=projects[name]
        text=tokenizer.apply_chat_template([{'role':'system','content':SYSTEM},{'role':'user','content':prompt(project)}],tokenize=False,add_generation_prompt=True)
        tokens=tokenizer(text,return_tensors='pt').to('cuda')
        with torch.no_grad():
            result=model.generate(**tokens,do_sample=False,max_new_tokens=1024,pad_token_id=tokenizer.eos_token_id)
        raw=tokenizer.decode(result[0,tokens.input_ids.shape[1]:],skip_special_tokens=True)
        match=re.search(r'```(?:python)?\s*\n(.*?)```',raw,re.S)
        content=match.group(1) if match else raw
        folder=root/project['id'];folder.mkdir()
        (folder/'response.txt').write_text(raw,encoding='utf-8')
        (folder/'main.py').write_text(content,encoding='utf-8')
        before=hashlib.sha256((folder/'main.py').read_bytes()).hexdigest()
        kind,error=inspect_source(content)
        if kind:
            item={'id':project['id'],'passed':False,'kind':kind,'error':error,'executed':False}
        else:
            rows=check(folder,cases,stdout_limit=32000)
            unchanged=before==hashlib.sha256((folder/'main.py').read_bytes()).hexdigest()
            item={'id':project['id'],'passed':all(r['passed'] for r in rows) and unchanged,'cases':rows,'executed':True,'source_unchanged':unchanged}
        item['input_cases']=cases
        item['trained_on_project']=project['id'] in training_ids
        (folder/'verification.json').write_text(json.dumps(item,indent=2),encoding='utf-8')
        report['projects'].append(item)
        report.update(passed=sum(p['passed'] for p in report['projects']),total=len(report['projects']))
        if args.all_projects and name in stress:
            large_folder=root/'larger-cases'/project['id'];large_folder.mkdir(parents=True)
            (large_folder/'main.py').write_text(content,encoding='utf-8')
            if kind:
                large={'id':project['id'],'passed':False,'executed':False,'kind':kind}
            else:
                large_rows=check(large_folder,[stress[name]],stdout_limit=32000)
                large={'id':project['id'],'passed':all(r['passed'] for r in large_rows),'executed':True,'cases':large_rows}
            large['input_case']=stress[name]
            large['small_cases_passed']=item['passed']
            large['trained_on_project']=item['trained_on_project']
            report['larger_cases'].append(large)
        report['larger_passed']=sum(p['passed'] for p in report['larger_cases'])
        report['training_projects_passed']=sum(p['passed'] for p in report['projects'] if p['trained_on_project'])
        report['heldout_projects_passed']=sum(p['passed'] for p in report['projects'] if not p['trained_on_project'])
        (root/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'project':item['id'],'passed':item['passed']}),flush=True)
    report.update(status='complete',completed=datetime.now(timezone.utc).isoformat(),
                  executed_projects=sum(p['executed'] for p in report['projects']),
                  executed_cases=sum(len(p.get('cases',[])) for p in report['projects']),
                  cases_passed=sum(c['passed'] for p in report['projects'] for c in p.get('cases',[])),
                  larger_executed=sum(p['executed'] for p in report['larger_cases']))
    (root/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(str(root/'results.json'),flush=True)
    return 0 if report['passed']==report['total'] and all(p['passed'] for p in report['larger_cases']) else 1


if __name__=='__main__':
    sys.exit(main())
