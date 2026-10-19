"""Resource-aware LoRA SFT on independently verified AZR tasks (Pillar D, Phase 7).

Trains a LoRA adapter on the original Qwen2.5-Coder-0.5B-Instruct weights (``models/qwen-jarvis-base``,
checksum-pinned; never an Ollama quantized file). Every target comes from the deterministic oracle
(``jarvis.azr_tasks.render_target``), never from a model.

Budgets and safety:
* bounded steps, batch 1 with gradient accumulation, gradient checkpointing, max sequence length;
* explicit VRAM and process-RAM ceilings: exceeding either checkpoints and stops (``resource_limit``);
* foreground preemption: before every optimizer step the shared GPU lease registry is read; any active
  or pending Jarvis inference stops training after a checkpoint (``preempted``); training never runs
  while Jarvis needs the GPU and never preempts Jarvis;
* cancellation: creating ``<out>/STOP`` (or Ctrl+C) checkpoints and stops (``cancelled``);
* resume: ``--resume <out>`` restores adapter, optimizer, scheduler, RNG states and data position, after
  checking dataset, base model and configuration hashes;
* no network: Hugging Face offline mode; nothing is uploaded.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from scripts.training.train_qwen_weights import BASE_SHA256, MODEL, REVISION  # noqa: E402

STATE_VERSION = 1


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def foreground_gpu_busy():
    """True when any Jarvis inference holds or waits for the GPU (read-only look at the lease registry)."""
    state_path = BASE / '.jarvis-runtime' / 'gpu' / 'state.json'
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    from jarvis.gpu_scheduler import alive
    rows = ([state['active']] if state.get('active') else []) + list(state.get('pending', []))
    return any(alive(row) for row in rows)


def load_examples(dataset, split):
    from jarvis.azr_dataset import load
    from jarvis.azr_tasks import render_prompt, render_target
    rows = load(dataset, split)
    return [{'id': r['id'], 'mode': r['task']['mode'], 'prompt': render_prompt(r['task']), 'target': render_target(r['task'])}
            for r in rows]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--max-steps', type=int, default=60)
    parser.add_argument('--grad-accum', type=int, default=8)
    parser.add_argument('--lr', type=float, default=2e-4)
    parser.add_argument('--max-len', type=int, default=896)
    parser.add_argument('--lora-r', type=int, default=8)
    parser.add_argument('--checkpoint-every', type=int, default=10)
    parser.add_argument('--vram-limit-mb', type=int, default=3300)
    parser.add_argument('--ram-limit-mb', type=int, default=6144)
    parser.add_argument('--max-minutes', type=float, default=45)
    parser.add_argument('--seed', type=int, default=20261019)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--ignore-foreground', action='store_true', help='tests only: skip the GPU lease check')
    args = parser.parse_args(argv)
    if not 1 <= args.max_steps <= 2000 or not 1 <= args.grad_accum <= 64 or not 128 <= args.max_len <= 2048:
        parser.error('bounded budgets: 1-2000 steps, 1-64 accumulation, 128-2048 tokens')
    out = args.out.resolve()
    if args.resume:
        if not (out / 'run.json').is_file():
            parser.error('nothing to resume in ' + str(out))
    elif out.exists():
        parser.error('refusing to overwrite ' + str(out))
    out.mkdir(parents=True, exist_ok=True)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HOME=str(BASE / 'models/hf-training-cache'),
                      USE_TF='0', USE_FLAX='0', TOKENIZERS_PARALLELISM='false')
    import psutil
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    def log(event):
        event = {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), **event}
        with (out / 'metrics.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event) + '\n')
        print(json.dumps(event), flush=True)

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        log({'status': 'blocked', 'reason': 'CUDA with BF16 is required; no silent CPU fallback'})
        return 3
    base_dir = BASE / 'models/qwen-jarvis-base'
    if sha256_file(base_dir / 'model.safetensors') != BASE_SHA256:
        raise SystemExit('Base model checksum mismatch; refusing to train on unknown weights.')
    manifest_sha = sha256_file(args.dataset / 'manifest.json')
    config = {k: v for k, v in vars(args).items() if k not in {'resume', 'out', 'dataset', 'max_steps', 'max_minutes',
                                                               'ignore_foreground'}}
    run = {'state_version': STATE_VERSION, 'base_model': MODEL, 'base_revision': REVISION, 'base_sha256': BASE_SHA256,
           'dataset': str(args.dataset), 'dataset_manifest_sha256': manifest_sha, 'config': config,
           'versions': {'torch': torch.__version__, 'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(0)}}
    if args.resume:
        stored = json.loads((out / 'run.json').read_text(encoding='utf-8'))
        for key in ('base_sha256', 'dataset_manifest_sha256', 'config'):
            if stored[key] != run[key]:
                raise SystemExit('Resume mismatch in ' + key + '; refusing to mix runs.')
    else:
        (out / 'run.json').write_text(json.dumps(run, indent=1), encoding='utf-8')

    examples = load_examples(args.dataset, 'train')
    tokenizer = AutoTokenizer.from_pretrained(base_dir, local_files_only=True)
    from jarvis.azr_tasks import SYSTEM

    def encode(example):
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': example['prompt']}]
        prefix = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        full = tokenizer.apply_chat_template(messages + [{'role': 'assistant', 'content': example['target']}], tokenize=False)
        ids = tokenizer(full, add_special_tokens=False)['input_ids']
        cut = len(tokenizer(prefix, add_special_tokens=False)['input_ids'])
        if len(ids) > args.max_len:
            return None
        return ids, cut

    encoded = [(e['id'], encode(e)) for e in examples]
    skipped = [i for i, e in encoded if e is None]
    encoded = [(i, e) for i, e in encoded if e is not None]
    torch.manual_seed(args.seed)
    model = AutoModelForCausalLM.from_pretrained(base_dir, torch_dtype=torch.bfloat16, attn_implementation='sdpa',
                                                 local_files_only=True).to('cuda')
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    checkpoints = sorted(out.glob('checkpoint-*'), key=lambda p: int(p.name.split('-')[1]))
    if args.resume and checkpoints:
        model = PeftModel.from_pretrained(model, checkpoints[-1], is_trainable=True, local_files_only=True)
    else:
        model = get_peft_model(model, LoraConfig(r=args.lora_r, lora_alpha=2 * args.lora_r, lora_dropout=0.05,
                                                 target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj',
                                                                 'up_proj', 'down_proj'], task_type='CAUSAL_LM'))
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    warmup = max(1, args.max_steps // 10)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: min(1.0, (step + 1) / warmup) * max(0.1, 1 - step / args.max_steps))
    step, position, order = 0, 0, None
    rng = random.Random(args.seed)
    if args.resume and checkpoints:
        state = torch.load(checkpoints[-1] / 'trainer-state.pt', map_location='cpu', weights_only=False)
        optimizer.load_state_dict(state['optimizer'])
        scheduler.load_state_dict(state['scheduler'])
        torch.set_rng_state(state['torch_rng'])
        torch.cuda.set_rng_state_all(state['cuda_rng'])
        rng.setstate(state['python_rng'])
        step, position, order = state['step'], state['position'], state['order']
        log({'status': 'resumed', 'step': step, 'checkpoint': checkpoints[-1].name})
    if order is None:
        order = [i for i, _ in encoded]
        rng.shuffle(order)
    by_id = dict(encoded)

    def checkpoint(reason):
        target = out / f'checkpoint-{step}'
        temporary = out / f'.checkpoint-{step}.tmp'
        if temporary.exists():
            shutil.rmtree(temporary)
        model.save_pretrained(temporary, safe_serialization=True)
        torch.save({'optimizer': optimizer.state_dict(), 'scheduler': scheduler.state_dict(),
                    'torch_rng': torch.get_rng_state(), 'cuda_rng': torch.cuda.get_rng_state_all(),
                    'python_rng': rng.getstate(), 'step': step, 'position': position, 'order': order,
                    'state_version': STATE_VERSION}, temporary / 'trainer-state.pt')
        if target.exists():
            shutil.rmtree(target)
        temporary.rename(target)
        for old in sorted(out.glob('checkpoint-*'), key=lambda p: int(p.name.split('-')[1]))[:-2]:
            shutil.rmtree(old)  # keep the two newest checkpoints
        log({'event': 'checkpoint', 'step': step, 'reason': reason,
             'adapter_sha256': sha256_file(target / 'adapter_model.safetensors')})

    started = time.monotonic()
    process = psutil.Process()
    torch.cuda.reset_peak_memory_stats()
    log({'status': 'training', 'examples': len(encoded), 'skipped_too_long': len(skipped), 'trainable_parameters':
         sum(p.numel() for p in params), 'start_step': step, 'max_steps': args.max_steps})
    status = 'completed'
    model.train()
    while step < args.max_steps:
        if (out / 'STOP').exists():
            status = 'cancelled'
            break
        if not args.ignore_foreground and foreground_gpu_busy():
            status = 'preempted'
            break
        if (time.monotonic() - started) / 60 > args.max_minutes:
            status = 'time_budget'
            break
        losses, step_started = [], time.monotonic()
        try:
            for _ in range(args.grad_accum):
                ids, cut = by_id[order[position % len(order)]]
                position += 1
                tensor = torch.tensor([ids], device='cuda')
                labels = tensor.clone()
                labels[0, :cut] = -100
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    loss = model(input_ids=tensor, attention_mask=torch.ones_like(tensor), labels=labels).loss
                if not torch.isfinite(loss):
                    raise RuntimeError('non-finite loss')
                (loss / args.grad_accum).backward()
                losses.append(float(loss.detach()))
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
        except KeyboardInterrupt:
            status = 'cancelled'
            optimizer.zero_grad(set_to_none=True)
            break
        step += 1
        peak_vram = torch.cuda.max_memory_allocated() / 2 ** 20
        rss = process.memory_info().rss / 2 ** 20
        log({'step': step, 'loss': round(sum(losses) / len(losses), 5), 'lr': scheduler.get_last_lr()[0],
             'seconds': round(time.monotonic() - step_started, 2), 'peak_vram_mb': round(peak_vram), 'rss_mb': round(rss)})
        if peak_vram > args.vram_limit_mb or rss > args.ram_limit_mb:
            status = 'resource_limit'
            break
        if step % args.checkpoint_every == 0:
            checkpoint('interval')
    checkpoint(status)
    final = {'status': status, 'step': step, 'minutes': round((time.monotonic() - started) / 60, 2),
             'peak_vram_mb': round(torch.cuda.max_memory_allocated() / 2 ** 20)}
    (out / 'final.json').write_text(json.dumps(final, indent=1), encoding='utf-8')
    log(final)
    return 0 if status == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
