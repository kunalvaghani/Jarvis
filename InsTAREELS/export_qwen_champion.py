"""Select the best fully evaluated local checkpoint and export modified weights."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

from train_qwen_weights import BASE, MODEL, BASE_SHA256


def main():
    roots=[BASE/'artifacts'/name for name in ('qwen-weight-training-20260927-cuda',
           'qwen-weight-training-20260927-corrective','qwen-weight-training-20260927-resumed')]
    candidates=[]
    reports=[]
    for root in roots:
        report=json.loads((root/'results.json').read_text(encoding='utf-8'))
        if report['base_sha256'] != BASE_SHA256:
            raise ValueError('Candidate base revision mismatch')
        candidates.extend(report['rounds'])
        reports.append(report)
    best=max(candidates,key=lambda r:(r['projects_passed'],-r['heldout_loss']))
    checkpoint=Path(best['checkpoint']).resolve()
    if not checkpoint.is_relative_to(BASE/'artifacts'):
        raise ValueError('Checkpoint outside local artifacts')
    if hashlib.sha256((checkpoint/'adapter_model.safetensors').read_bytes()).hexdigest() != best['adapter_sha256']:
        raise ValueError('Checkpoint weights changed since evaluation')
    out=BASE/'artifacts/qwen-jarvis-trained-20260927'
    out.mkdir(exist_ok=False)
    shutil.copytree(checkpoint,out/'adapter')
    # Optimizer state is preserved for continuity, but it belongs to the source dataset.
    shutil.copy2(checkpoint.parent/'dataset.json',out/'dataset.json')
    os.environ.update(HF_HOME=str(BASE/'models/hf-training-cache'),HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1',USE_TF='0',USE_FLAX='0')
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from peft import PeftModel
    from safetensors import safe_open
    torch.set_num_threads(8)
    completed_rounds=gradient_examples=optimizer_steps=0
    for root, report in zip(roots,reports):
        checkpoints=list(root.glob('round-*/training-state.pt'))
        states=[torch.load(path,map_location='cpu',weights_only=True) for path in checkpoints]
        rounds=max(state['completed_rounds'] for state in states)
        initialized=Path(report['initialized_from']) if report.get('initialized_from') else None
        if initialized and (initialized/'training-state.pt').is_file():
            previous=torch.load(initialized/'training-state.pt',map_location='cpu',weights_only=True)
            if previous['dataset_sha256']==report['dataset_sha256']:
                rounds-=previous['completed_rounds']
        if rounds<0:
            raise ValueError('Invalid training round continuity')
        examples=report.get('training_examples',report['training_projects'])
        completed_rounds+=rounds
        gradient_examples+=rounds*examples
        optimizer_steps+=rounds*math.ceil(examples/4)
    model=AutoModelForCausalLM.from_pretrained(BASE/'models/qwen-jarvis-base',torch_dtype=torch.float32,local_files_only=True)
    model=PeftModel.from_pretrained(model,checkpoint,local_files_only=True)
    merged=model.merge_and_unload(safe_merge=True)
    key='model.layers.0.self_attn.q_proj.weight'
    with safe_open(BASE/'models/qwen-jarvis-base/model.safetensors',framework='pt',device='cpu') as source:
        original=source.get_tensor(key).float()
    delta=float((merged.state_dict()[key].float()-original).abs().sum())
    if not delta>0:
        raise ValueError('Selected merged weights did not change')
    merged.save_pretrained(out/'merged-model',safe_serialization=True,max_shard_size='2GB')
    AutoTokenizer.from_pretrained(checkpoint,local_files_only=True).save_pretrained(out/'merged-model')
    shutil.copy2(BASE/'models/qwen-jarvis-base/LICENSE',out/'merged-model/LICENSE')
    digest=hashlib.sha256()
    with (out/'merged-model/model.safetensors').open('rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    summary={'base_model':MODEL,'base_sha256':BASE_SHA256,'selected_checkpoint':str(checkpoint),
          'local_adapter':str(out/'adapter'),'local_merged_model':str(out/'merged-model'),
          'merged_projection_absolute_delta':delta,'merged_sha256':digest.hexdigest(),
          'selected_heldout_passes':best['projects_passed'],'heldout_total':best['projects_total'],
          'selected_heldout_loss':best['heldout_loss'],'completed_gradient_rounds':completed_rounds,
          'gradient_examples':gradient_examples,'optimizer_steps':optimizer_steps,
          'trainable_parameters':reports[0]['trainable_parameters'],
          'phase_reports':[str(root/'results.json') for root in roots],
          'note':'Best completed held-out result retained; corrective round-two parser failure recovered separately. No production configuration change.'}
    (out/'results.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
