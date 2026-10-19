"""RLVR/GRPO feasibility probe on the 4 GB GPU (.venv-training). Measures; does not claim training.

For a few train tasks: sample G answers from the SFT adapter (temperature 0.8), score each with the
independent oracle (deduction/abduction only; no code execution in this process), compute
group-normalized advantages (GRPO, per task), and take policy-gradient steps on the LoRA weights:
loss = -mean(advantage * mean token log-prob of the sampled answer). Reports peak VRAM, seconds per
step, reward statistics and whether any group had non-zero reward variance (a learning signal).
Writes no adapter unless --save is given.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tasks', type=int, default=4)
    parser.add_argument('--group', type=int, default=4)
    parser.add_argument('--max-new', type=int, default=256)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('refusing to overwrite ' + str(args.out))
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HOME=str(BASE / 'models/hf-training-cache'),
                      USE_TF='0', USE_FLAX='0')
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from jarvis.azr_dataset import load
    from jarvis.azr_reward import score_symbolic
    from jarvis.azr_tasks import SYSTEM, render_prompt
    base_dir = BASE / 'models/qwen-jarvis-base'
    tokenizer = AutoTokenizer.from_pretrained(base_dir, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(base_dir, torch_dtype=torch.bfloat16, local_files_only=True).to('cuda')
    model = PeftModel.from_pretrained(model, args.adapter, is_trainable=True, local_files_only=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.enable_input_require_grads()
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=1e-5)
    rows = [r for r in load(args.dataset, 'validation') if r['task']['mode'] in {'deduction', 'abduction'}][:args.tasks]
    torch.manual_seed(7)
    torch.cuda.reset_peak_memory_stats()
    steps = []
    for row in rows:
        started = time.monotonic()
        prompt = tokenizer.apply_chat_template([{'role': 'system', 'content': SYSTEM},
                                                {'role': 'user', 'content': render_prompt(row['task'])}],
                                               tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(prompt, return_tensors='pt', add_special_tokens=False).to('cuda')
        model.eval()
        model.config.use_cache = True
        with torch.no_grad():
            samples = model.generate(**encoded, do_sample=True, temperature=0.8, top_p=0.95, max_new_tokens=args.max_new,
                                     num_return_sequences=args.group, pad_token_id=tokenizer.eos_token_id)
        sampled_seconds = time.monotonic() - started
        prefix = encoded['input_ids'].shape[1]
        texts = [tokenizer.decode(s[prefix:], skip_special_tokens=True) for s in samples]
        rewards = [score_symbolic(row['task'], text)['reward'] for text in texts]
        mean, spread = statistics.fmean(rewards), statistics.pstdev(rewards)
        advantages = [(r - mean) / (spread + 1e-6) for r in rewards]
        model.train()
        model.config.use_cache = False
        optimizer.zero_grad(set_to_none=True)
        losses = []
        for sample, advantage in zip(samples, advantages):
            if advantage == 0:
                continue
            ids = sample.unsqueeze(0)
            mask = (ids != tokenizer.pad_token_id).long() if tokenizer.pad_token_id is not None else torch.ones_like(ids)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(input_ids=ids, attention_mask=mask).logits[:, :-1].float()
            targets = ids[:, 1:]
            logprobs = torch.log_softmax(logits, -1).gather(-1, targets.unsqueeze(-1)).squeeze(-1)[:, prefix - 1:]
            answer_mask = (targets[:, prefix - 1:] != tokenizer.eos_token_id).float()
            loss = -advantage * (logprobs * answer_mask).sum() / answer_mask.sum().clamp(min=1) / args.group
            loss.backward()
            losses.append(float(loss.detach()))
        if losses:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            optimizer.step()
        steps.append({'task': row['id'], 'mode': row['task']['mode'], 'rewards': rewards, 'reward_std': round(spread, 4),
                      'updated': bool(losses), 'sample_seconds': round(sampled_seconds, 2),
                      'step_seconds': round(time.monotonic() - started, 2)})
        print(json.dumps(steps[-1]), flush=True)
    args.out.mkdir(parents=True)
    report = {'group_size': args.group, 'tasks': len(steps), 'steps': steps,
              'peak_vram_mb': round(torch.cuda.max_memory_allocated() / 2 ** 20),
              'groups_with_signal': sum(s['reward_std'] > 0 for s in steps),
              'mean_step_seconds': round(statistics.fmean(s['step_seconds'] for s in steps), 2) if steps else None,
              'note': 'Feasibility probe only: a handful of GRPO-style updates; no claim of improvement.'}
    (args.out / 'grpo-feasibility.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'steps'}, indent=1))


if __name__ == '__main__':
    main()
