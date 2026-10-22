"""Explicit, offline teacher/student LoRA candidate pipeline; never auto-promotes.

No network, installs, runtime-data collection or deletion. Local trainable base
weights must match a user-supplied SHA256 manifest. Default invocation prepares
curated family-separated examples only. --train is an explicit offline run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from jarvis.teacher_student import curated_examples


def busy():
    from scripts.training.train_azr_lora import foreground_gpu_busy
    from jarvis.paths import state_file
    if foreground_gpu_busy():
        return True
    try:
        path = state_file('task_state.json', BASE)
        if not path.exists():
            return False
        if path.stat().st_size > 8_000_000:
            return True
        current = json.loads(path.read_text(encoding='utf-8')).get('current') or {}
        return current.get('status') == 'running'
    except (OSError, ValueError, TypeError):
        return True


def pinned_base(root, manifest):
    root = root.resolve(strict=True)
    expected = json.loads(manifest.read_text(encoding='utf-8'))
    if expected.get('model') not in {'Qwen/Qwen3.5-2B', 'Qwen/Qwen3.5-4B'} or not re.fullmatch(r'[0-9a-f]{40}', str(expected.get('revision', ''))):
        raise ValueError('Pin an original Qwen3.5 2B/4B trainable base and immutable revision.')
    files = expected.get('files')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if not isinstance(files, dict) or actual != set(files) or not any(p.endswith('.safetensors') for p in actual):
        raise ValueError('Every base/tokenizer/config file must be checksum pinned; GGUF is not a training base.')
    for name, digest in files.items():
        path = root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Linked training bases are unsupported.')
        checksum = hashlib.sha256()
        with path.open('rb') as source:
            while block := source.read(1 << 20):
                checksum.update(block)
        if checksum.hexdigest() != digest:
            raise ValueError('Training base checksum mismatch: '+name)
    return expected


def training_class(config, library):
    if config.get('model_type') != 'qwen3_5' or config.get('architectures') != ['Qwen3_5ForConditionalGeneration']:
        raise ValueError('Expected the pinned official Qwen3.5 conditional-generation architecture.')
    model_class = getattr(library, 'Qwen3_5ForConditionalGeneration', None)
    if model_class is None:
        raise ValueError('Installed Transformers lacks Qwen3.5 support. An approved isolated dependency upgrade is required; nothing was installed.')
    return model_class


def target_matches(text, target):
    from jarvis.mcp_contract import json_equal
    try:
        return json_equal(json.loads(text), json.loads(target))
    except ValueError:
        return text.strip() == target.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--allow-private', action='store_true', help='Explicitly authorize these curated private examples')
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--base', type=Path)
    parser.add_argument('--base-manifest', type=Path)
    parser.add_argument('--steps', type=int, default=20)
    parser.add_argument('--max-minutes', type=int, default=30)
    parser.add_argument('--ram-limit-mb', type=int, default=24576)
    args = parser.parse_args(argv)
    if args.out.exists() or not 1 <= args.steps <= 200 or not 1 <= args.max_minutes <= 120:
        parser.error('Use a new output directory, 1-200 steps and 1-120 minutes.')
    if not 4096 <= args.ram_limit_mb <= 24576 or args.examples.stat().st_size > 16_000_000:
        parser.error('Bounded RAM (4-24 GB) and examples (16 MB) required.')
    splits = curated_examples([json.loads(line) for line in args.examples.read_text(encoding='utf-8').splitlines() if line.strip()], args.allow_private)
    base = None
    if args.train:
        if not args.base or not args.base_manifest:
            parser.error('--train needs --base and --base-manifest; no weights are downloaded.')
        if busy():
            raise ValueError('Foreground work active or unavailable; defer the offline run.')
        base = pinned_base(args.base, args.base_manifest)
    args.out.mkdir(parents=True)
    for split, rows in splits.items():
        (args.out/(split+'.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
    report = {'status': 'prepared', 'base': base, 'train_examples': len(splits['train']),
              'heldout_examples': len(splits['heldout']), 'promotion': 'requires held-out success, full regression tests and explicit approval'}
    def save():
        (args.out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    save()
    if not args.train:
        return 0
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', USE_TF='0', USE_FLAX='0')
    import psutil
    import torch
    from peft import LoraConfig, get_peft_model
    import transformers
    from transformers import AutoTokenizer
    # CPU training keeps this 4 GB GPU available for speech and foreground
    # inference. It is intentionally slow and manually invoked, never idle-auto.
    torch.set_num_threads(2)
    process = psutil.Process()
    try:
        loader = training_class(json.loads((args.base/'config.json').read_text(encoding='utf-8')), transformers)
        estimate = sum(p.stat().st_size for p in args.base.rglob('*.safetensors'))*2/1048576+2048
        if estimate > args.ram_limit_mb or estimate+4096 > psutil.virtual_memory().available/1048576:
            raise ValueError('Insufficient conservative RAM headroom for offline CPU training; no weights allocated.')
        if busy():
            raise ValueError('Foreground activity arrived during preflight; no weights allocated.')
        tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True, trust_remote_code=False)
        model = loader.from_pretrained(args.base, local_files_only=True, torch_dtype=torch.float32)
    except (ValueError, RuntimeError, AttributeError, ImportError) as error:
        report.update(status='blocked', error=str(error))
        save()
        return 3
    started = time.monotonic()
    def admitted():
        return (not busy() and not (args.out/'STOP').exists()
                and process.memory_info().rss/1048576 <= args.ram_limit_mb
                and time.monotonic()-started < args.max_minutes*60)
    def prompt(row):
        return tokenizer.apply_chat_template([{'role': 'user', 'content': row['input']}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    def evaluate():
        model.eval()
        scores = []
        for row in splits['heldout']:
            if not admitted():
                raise ValueError('Offline evaluation preempted or resource/time budget reached.')
            encoded = tokenizer(prompt(row), return_tensors='pt', truncation=False)
            if encoded.input_ids.shape[1] > 384:
                raise ValueError('Held-out input exceeds the 384-token budget.')
            with torch.no_grad():
                output = model.generate(**encoded, max_new_tokens=128, do_sample=False, pad_token_id=tokenizer.eos_token_id)
            text = tokenizer.decode(output[0, encoded.input_ids.shape[1]:], skip_special_tokens=True).strip()
            # Strict held-out tool/argument JSON or exact deterministic target;
            # language fluency alone is never accepted as task correctness.
            correct = target_matches(text, row['target'])
            scores.append({'id': row['id'], 'correct': correct})
        return scores
    try:
        report['baseline'] = evaluate()
        model = get_peft_model(model, LoraConfig(r=4, lora_alpha=8, target_modules=['q_proj', 'v_proj'], task_type='CAUSAL_LM'))
        optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=1e-4)
        report['steps'] = 0
        for step in range(args.steps):
            if not admitted():
                report['status'] = 'preempted_or_budget'
                break
            model.train()
            row = splits['train'][step % len(splits['train'])]
            prefix = tokenizer(prompt(row), add_special_tokens=False)['input_ids']
            target = tokenizer(row['target']+tokenizer.eos_token, add_special_tokens=False)['input_ids']
            if not target or len(prefix)+len(target) > 512:
                raise ValueError('Training sequence exceeds the 512-token budget; curate a shorter example.')
            tensor = torch.tensor([prefix+target])
            labels = tensor.clone()
            labels[:, :len(prefix)] = -100
            loss = model(input_ids=tensor, labels=labels).loss
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite loss; candidate rejected.')
            loss.backward()
            if not admitted():
                report['status'] = 'preempted_or_budget'
                break
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            report['steps'] = step+1
        else:
            report['candidate'] = evaluate()
            report['no_heldout_regressions'] = all(not before['correct'] or after['correct'] for before, after in zip(report['baseline'], report['candidate']))
            report['all_heldout_correct'] = all(row['correct'] for row in report['candidate'])
            report['status'] = 'review_required' if report['no_heldout_regressions'] and report['all_heldout_correct'] else 'rejected'
    except (ValueError, RuntimeError) as error:
        report.update(status='blocked', error=str(error))
    finally:
        if hasattr(model, 'peft_config'):
            model.save_pretrained(args.out/'adapter', safe_serialization=True)
        save()
    return 0 if report['status'] == 'review_required' else 3


if __name__ == '__main__':
    raise SystemExit(main())
