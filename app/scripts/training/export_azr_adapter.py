"""Export-compatibility check for an AZR LoRA adapter (.venv-training). Registers nothing.

1. Merge the adapter into the checksum-pinned base (PEFT ``merge_and_unload``) and save the merged
   model with its tokenizer.
2. Reload the merged model with plain transformers and compare greedy outputs with the unmerged
   adapter on held-out prompts (exact text match rate).
3. Report whether a GGUF converter is available for Ollama registration; if not, that step is BLOCKED.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--tasks', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=24)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('refusing to overwrite ' + str(args.out))
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HOME=str(BASE / 'models/hf-training-cache'),
                      USE_TF='0', USE_FLAX='0')
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from jarvis.azr_tasks import SYSTEM, render_prompt
    base_dir = BASE / 'models/qwen-jarvis-base'
    tokenizer = AutoTokenizer.from_pretrained(base_dir, local_files_only=True, padding_side='left')
    rows = [json.loads(line) for line in args.tasks.read_text(encoding='utf-8').splitlines() if line.strip()]
    rows = [r for mode in ('deduction', 'abduction', 'induction') for r in rows if r['task']['mode'] == mode][::max(1, len(rows) // args.limit)][:args.limit]

    def outputs(model):
        texts = []
        for row in rows:
            prompt = tokenizer.apply_chat_template([{'role': 'system', 'content': SYSTEM},
                                                    {'role': 'user', 'content': render_prompt(row['task'])}],
                                                   tokenize=False, add_generation_prompt=True)
            encoded = tokenizer(prompt, return_tensors='pt', add_special_tokens=False).to('cuda')
            with torch.no_grad():
                generated = model.generate(**encoded, do_sample=False, max_new_tokens=256, pad_token_id=tokenizer.eos_token_id)
            texts.append(tokenizer.decode(generated[0, encoded['input_ids'].shape[1]:], skip_special_tokens=True))
        return texts

    base = AutoModelForCausalLM.from_pretrained(base_dir, torch_dtype=torch.bfloat16, local_files_only=True).to('cuda')
    adapted = PeftModel.from_pretrained(base, args.adapter, local_files_only=True)
    adapted.eval()
    adapter_texts = outputs(adapted)
    merged = adapted.merge_and_unload(safe_merge=True)
    merged_dir = args.out / 'merged'
    merged.save_pretrained(merged_dir, safe_serialization=True)
    tokenizer.save_pretrained(merged_dir)
    del merged, adapted, base
    torch.cuda.empty_cache()
    reloaded = AutoModelForCausalLM.from_pretrained(merged_dir, torch_dtype=torch.bfloat16, local_files_only=True).to('cuda')
    reloaded.eval()
    merged_texts = outputs(reloaded)
    matches = sum(a == b for a, b in zip(adapter_texts, merged_texts))
    gguf = importlib.util.find_spec('gguf') is not None or shutil.which('llama-quantize') is not None
    report = {'adapter': str(args.adapter), 'prompts': len(rows), 'exact_match': matches,
              'exact_match_rate': round(matches / len(rows), 4), 'merged_dir': str(merged_dir),
              'merged_reloads_with_transformers': True,
              'gguf_conversion': 'available' if gguf else 'BLOCKED: no GGUF converter (gguf package / llama.cpp) installed',
              'ollama_registration': 'not performed (requires approval and a GGUF export)',
              'mismatches': [{'id': r['id'], 'adapter': a[:200], 'merged': b[:200]}
                             for r, a, b in zip(rows, adapter_texts, merged_texts) if a != b][:5]}
    (args.out / 'export-check.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'mismatches'}, indent=1))


if __name__ == '__main__':
    main()
