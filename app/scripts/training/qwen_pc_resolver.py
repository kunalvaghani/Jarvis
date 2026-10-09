"""Read-only trained PC resolver. Its JSON never dispatches an action."""
import argparse,json,os,sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',type=Path,required=True)
    args=parser.parse_args()
    base=Path(__file__).resolve().parents[2];checkpoint=(base/args.checkpoint).resolve()
    if not checkpoint.is_relative_to(base/'artifacts') or not (checkpoint/'adapter_model.safetensors').is_file():
        parser.error('Use an existing local adapter under artifacts')
    request=json.loads(sys.stdin.read(50000))
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TF='0',USE_FLAX='0')
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    from jarvis.pc_context import SYSTEM,prompt
    torch.set_num_threads(8)
    tokenizer=AutoTokenizer.from_pretrained(checkpoint,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(base/'models/qwen-jarvis-base',torch_dtype=torch.float32,local_files_only=True)
    model=PeftModel.from_pretrained(model,checkpoint,local_files_only=True).eval()
    text=tokenizer.apply_chat_template([{'role':'system','content':SYSTEM},{'role':'user','content':prompt(request['goal'],request['entries'],request.get('kind'))}],tokenize=False,add_generation_prompt=True)
    tokens=tokenizer(text,return_tensors='pt')
    if tokens.input_ids.shape[1]>1536:parser.error('PC context exceeds bounded resolver input')
    with torch.no_grad():result=model.generate(**tokens,do_sample=False,max_new_tokens=300,pad_token_id=tokenizer.eos_token_id)
    raw=tokenizer.decode(result[0,tokens.input_ids.shape[1]:],skip_special_tokens=True)
    print(json.dumps({'proposal':json.loads(raw),'model_used':'jarvis-qwen-pc-lora'}))


if __name__=='__main__':main()
