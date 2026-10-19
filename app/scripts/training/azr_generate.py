"""Batched greedy generation for AZR tasks with the base model or base + LoRA adapter (.venv-training).

Writes answers only; scoring happens separately in the main environment through the independent
oracle (``jarvis.azr_reward``), so the generation process cannot influence its own rewards.
Records per-task latency, generated tokens and peak VRAM.
Usage: python -m scripts.training.azr_generate --tasks <jsonl> --out <jsonl> [--adapter <dir>]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from scripts.training.train_qwen_weights import BASE_SHA256  # noqa: E402

MAX_NEW = {'deduction': 320, 'abduction': 384, 'induction': 192}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--tasks', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--adapter', type=Path)
    parser.add_argument('--merged', type=Path, help='a merged full model directory (export compatibility check)')
    parser.add_argument('--batch', type=int, default=8)
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('refusing to overwrite ' + str(args.out))
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HOME=str(BASE / 'models/hf-training-cache'),
                      USE_TF='0', USE_FLAX='0', TOKENIZERS_PARALLELISM='false')
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from jarvis.azr_tasks import SYSTEM, render_prompt
    base_dir = BASE / 'models/qwen-jarvis-base'
    digest = hashlib.sha256()
    with (base_dir / 'model.safetensors').open('rb') as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    if digest.hexdigest() != BASE_SHA256:
        raise SystemExit('Base model checksum mismatch.')
    tokenizer = AutoTokenizer.from_pretrained(base_dir, local_files_only=True, padding_side='left')
    source = args.merged or base_dir
    model = AutoModelForCausalLM.from_pretrained(source, torch_dtype=torch.bfloat16, attn_implementation='sdpa',
                                                 local_files_only=True).to('cuda')
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter, local_files_only=True)
    model.eval()
    rows = [json.loads(line) for line in args.tasks.read_text(encoding='utf-8').splitlines() if line.strip()]
    if args.limit:
        rows = rows[:args.limit]
    torch.cuda.reset_peak_memory_stats()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    started_all = time.monotonic()
    with args.out.open('w', encoding='utf-8') as handle:
        for mode in ('deduction', 'abduction', 'induction'):
            subset = [r for r in rows if r['task']['mode'] == mode]
            for start in range(0, len(subset), args.batch):
                batch = subset[start:start + args.batch]
                texts = [tokenizer.apply_chat_template([{'role': 'system', 'content': SYSTEM},
                                                        {'role': 'user', 'content': render_prompt(r['task'])}],
                                                       tokenize=False, add_generation_prompt=True) for r in batch]
                encoded = tokenizer(texts, return_tensors='pt', padding=True, add_special_tokens=False).to('cuda')
                began = time.monotonic()
                with torch.no_grad():
                    output = model.generate(**encoded, do_sample=False, max_new_tokens=MAX_NEW[mode],
                                            pad_token_id=tokenizer.eos_token_id)
                seconds = time.monotonic() - began
                for index, row in enumerate(batch):
                    generated = output[index, encoded['input_ids'].shape[1]:]
                    text = tokenizer.decode(generated, skip_special_tokens=True)
                    tokens = int((generated != tokenizer.eos_token_id).sum())
                    handle.write(json.dumps({'id': row['id'], 'mode': mode, 'answer': text, 'new_tokens': tokens,
                                             'batch_seconds': round(seconds, 3), 'batch_size': len(batch)}) + '\n')
                handle.flush()
                print(json.dumps({'mode': mode, 'done': start + len(batch), 'of': len(subset), 'seconds': round(seconds, 2)}),
                      flush=True)
    summary = {'model': 'base' if not (args.adapter or args.merged) else str(args.adapter or args.merged),
               'tasks': len(rows), 'seconds': round(time.monotonic() - started_all, 1),
               'peak_vram_mb': round(torch.cuda.max_memory_allocated() / 2 ** 20), 'batch': args.batch,
               'decoding': 'greedy', 'max_new_tokens': MAX_NEW}
    args.out.with_suffix('.summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
