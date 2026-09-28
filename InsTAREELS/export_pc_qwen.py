"""Export a full dedicated PC Qwen model from a verified local adapter."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
from train_qwen_weights import BASE,BASE_SHA256,MODEL


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',type=Path,required=True);args=parser.parse_args()
    checkpoint=(BASE/args.checkpoint).resolve()
    if not checkpoint.is_relative_to(BASE/'artifacts') or not (checkpoint/'adapter_model.safetensors').is_file():parser.error('Use local adapter')
    out=checkpoint.parent/'merged-model';out.mkdir(exist_ok=False)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TF='0',USE_FLAX='0')
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from peft import PeftModel
    from safetensors import safe_open
    torch.set_num_threads(8)
    digest=hashlib.sha256()
    with (BASE/'models/qwen-jarvis-base/model.safetensors').open('rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    if digest.hexdigest()!=BASE_SHA256:raise ValueError('Base checksum mismatch')
    report=json.loads((checkpoint.parent/'results.json').read_text())
    recorded=next(row for row in report['rounds'] if Path(row['checkpoint']).resolve()==checkpoint)
    if hashlib.sha256((checkpoint/'adapter_model.safetensors').read_bytes()).hexdigest()!=recorded['adapter_sha256']:raise ValueError('Adapter changed since evaluation')
    model=AutoModelForCausalLM.from_pretrained(BASE/'models/qwen-jarvis-base',torch_dtype=torch.float32,local_files_only=True)
    model=PeftModel.from_pretrained(model,checkpoint,local_files_only=True).merge_and_unload(safe_merge=True)
    key='model.layers.0.self_attn.q_proj.weight'
    with safe_open(BASE/'models/qwen-jarvis-base/model.safetensors',framework='pt',device='cpu') as source:original=source.get_tensor(key).float()
    delta=float((model.state_dict()[key].float()-original).abs().sum())
    if delta<=0:raise ValueError('No modified model weights')
    model.save_pretrained(out,safe_serialization=True,max_shard_size='2GB')
    AutoTokenizer.from_pretrained(checkpoint,local_files_only=True).save_pretrained(out)
    shutil.copy2(BASE/'models/qwen-jarvis-base/LICENSE',out/'LICENSE')
    digest=hashlib.sha256()
    with (out/'model.safetensors').open('rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    result={'model':MODEL,'merged_sha256':digest.hexdigest(),'projection_absolute_delta':delta,'checkpoint':checkpoint.name,
            'method':'full FP32 model export, PC-trained adapter merged into original Qwen weights'}
    (checkpoint.parent/'merged-export.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
