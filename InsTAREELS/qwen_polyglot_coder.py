"""Generate JavaScript or SQL with a locally trained Jarvis Qwen adapter.

Generation only returns source text. It never executes the model's output.
"""
import argparse
import json
import os
from pathlib import Path

from train_polyglot_qwen import SYSTEM


BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--language', choices=('javascript', 'sql'), required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--max-tokens', type=int, default=512)
    args = parser.parse_args()
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_relative_to(BASE / 'artifacts') or not (checkpoint / 'adapter_model.safetensors').is_file():
        parser.error('Choose an existing local Jarvis checkpoint under artifacts/')
    metadata = checkpoint / 'jarvis_training.json'
    if not metadata.is_file() or args.language not in json.loads(metadata.read_text(encoding='utf-8')).get('languages', []):
        parser.error('Checkpoint has no training record for this language')
    if not 1 <= args.max_tokens <= 2048:
        parser.error('--max-tokens must be between 1 and 2048')
    if len(args.task) > 8000:
        parser.error('Task is too long')
    os.environ.update(HF_HOME=str(BASE / 'models/hf-training-cache'), HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1', USE_TF='0', USE_FLAX='0')
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
    torch.set_num_threads(8)
    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(BASE / 'models/qwen-jarvis-base',
                                                 torch_dtype=torch.float32, local_files_only=True)
    model = PeftModel.from_pretrained(model, checkpoint, local_files_only=True).eval()
    if args.language == 'javascript':
        request = 'Write one complete CommonJS JavaScript file exporting solve(input). ' + args.task
    else:
        request = ('Write one SQLite SELECT statement over users(id,name,active) and '
                   'orders(id,user_id,amount,status,created_at). ' + args.task)
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': request}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    tokens = tokenizer(prompt, return_tensors='pt')
    if tokens.input_ids.shape[1] > 4096:
        parser.error('Prompt exceeds the model context budget')
    with torch.no_grad():
        result = model.generate(**tokens, do_sample=False, max_new_tokens=args.max_tokens,
                                pad_token_id=tokenizer.eos_token_id)
    source = tokenizer.decode(result[0, tokens.input_ids.shape[1]:], skip_special_tokens=True).strip()
    print(json.dumps({'language': args.language, 'content': source, 'checkpoint': str(checkpoint),
                      'executed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
