"""Continue the local Jarvis Qwen LoRA on checked JavaScript and SQL examples."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from jarvis.polyglot_training_data import TASKS


BASE = Path(__file__).resolve().parent
SYSTEM = "You are Jarvis, a coding assistant. Return only the complete requested source file or SQL query, without Markdown."
SCHEMA = """CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, active INTEGER);
CREATE TABLE orders(id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER, status TEXT, created_at TEXT);
INSERT INTO users VALUES (1,'Ada',1),(2,'Ben',1),(3,'Cal',0),(4,'Dee',1);
INSERT INTO orders VALUES (1,1,10,'paid','2026-01-01'),(2,1,15,'paid','2026-02-01'),
 (3,1,99,'refunded','2026-03-01'),(4,2,7,'paid','2026-01-03'),(5,3,30,'paid','2026-01-04');"""


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def prompt(row):
    if row['language'] == 'javascript':
        format_rule = 'Write one complete CommonJS JavaScript file exporting solve(input). '
    elif row['language'] == 'sql':
        format_rule = 'Write one SQLite SELECT statement over users(id,name,active) and orders(id,user_id,amount,status,created_at). '
    else:
        format_rule = 'Write one complete Python source file. '
    return format_rule + row['task']


def verify_reference(row, folder):
    folder.mkdir(parents=True, exist_ok=False)
    if row['language'] == 'javascript':
        file = folder / 'solution.js'
        file.write_text(row['source'], encoding='utf-8')
        checked = subprocess.run(['node', '--check', str(file)], capture_output=True, text=True, timeout=5)
        if checked.returncode:
            raise ValueError(f"Invalid JavaScript reference {row['id']}: {checked.stderr[:200]}")
        runner = "const fs=require('fs'); const {solve}=require(process.argv[1]); process.stdout.write(JSON.stringify(solve(JSON.parse(fs.readFileSync(0,'utf8')))));"
        for value, expected in row['cases']:
            result = subprocess.run(['node', '-e', runner, str(file)], input=json.dumps(value),
                                    capture_output=True, text=True, timeout=5)
            if result.returncode or json.loads(result.stdout) != expected:
                raise ValueError(f"JavaScript reference case failed: {row['id']}")
    elif row['language'] == 'sql':
        if not re.fullmatch(r'\s*SELECT\b[\s\S]*;\s*', row['source'], re.I):
            raise ValueError(f"Reference is not one SELECT: {row['id']}")
        connection = sqlite3.connect(':memory:')
        try:
            connection.executescript(SCHEMA)
            actual = [list(item) for item in connection.execute(row['source'])]
            if actual != row['expected']:
                raise ValueError(f"SQL reference case failed: {row['id']}: {actual!r}")
        finally:
            connection.close()
        (folder / 'query.sql').write_text(row['source'], encoding='utf-8')
    save(folder / 'verification.json', {'id': row['id'], 'reference_passed': True})


def syntax_check(row, source, folder):
    source = source.strip()
    if not source or len(source) > 8000:
        return False
    if row['language'] == 'javascript':
        file = folder / 'generated.js'
        file.write_text(source, encoding='utf-8')
        result = subprocess.run(['node', '--check', str(file)], capture_output=True, text=True, timeout=5)
        return result.returncode == 0 and 'module.exports' in source
    if row['language'] == 'sql':
        if not re.fullmatch(r'\s*SELECT\b[^;]*;?\s*', source, re.I | re.S):
            return False
        connection = sqlite3.connect(':memory:')
        try:
            connection.executescript(SCHEMA)
            connection.execute('EXPLAIN QUERY PLAN ' + source.rstrip(';'))
            return True
        except sqlite3.Error:
            return False
        finally:
            connection.close()
    import ast
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--initialize-adapter', type=Path, default=BASE / 'artifacts/qwen-jarvis-trained-20260927/adapter')
    parser.add_argument('--rounds', type=int, choices=(1, 2, 3), default=2)
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'preparing', 'started': datetime.now(timezone.utc).isoformat(),
              'method': 'local supervised LoRA gradient training', 'base_model': 'Qwen/Qwen2.5-Coder-0.5B-Instruct',
              'initialized_from': str(args.initialize_adapter.resolve()), 'rounds': []}
    save(out / 'results.json', report)
    try:
        if not (args.initialize_adapter / 'adapter_model.safetensors').is_file():
            raise FileNotFoundError('Prior trained adapter is missing')
        for row in TASKS:
            verify_reference(row, out / 'reference-verification' / row['id'])
        training = [dict(row) for row in TASKS if row['split'] == 'train']
        heldout = [dict(row) for row in TASKS if row['split'] == 'heldout']
        # Rehearse a small sample of previously verified Python projects to limit forgetting.
        previous = json.loads((BASE / 'artifacts/qwen-weight-training-20260927-corrective/dataset.json').read_text(encoding='utf-8'))
        for row in previous['training'][::max(1, len(previous['training']) // 4)][:4]:
            training.append({'id': 'python-replay-' + row['id'], 'language': 'python',
                             'task': 'Read one JSON value from stdin and print one JSON value. ' + row['contract'],
                             'source': row['content'], 'split': 'train', 'origin': 'previously case-verified Python curriculum'})
        save(out / 'dataset.json', {'training': training, 'heldout': heldout,
                                   'reference_fixture': SCHEMA, 'generated_outputs_executed': False})
        os.environ.update(HF_HOME=str(BASE / 'models/hf-training-cache'), HF_HUB_OFFLINE='1',
                          TRANSFORMERS_OFFLINE='1', USE_TF='0', USE_FLAX='0')
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import PeftModel
        torch.set_num_threads(8)
        if args.device == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable; no implicit CPU fallback')
        dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if args.device == 'cuda' else torch.float32
        modeldir = BASE / 'models/qwen-jarvis-base'
        tokenizer = AutoTokenizer.from_pretrained(modeldir, local_files_only=True)
        tokenizer.pad_token = tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(modeldir, torch_dtype=dtype, local_files_only=True,
                                                    attn_implementation='sdpa').to(args.device)
        model = PeftModel.from_pretrained(base, args.initialize_adapter, is_trainable=True, local_files_only=True)
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        model.enable_input_require_grads()
        trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
        before = [parameter.detach().float().cpu().clone() for parameter in trainable]
        report.update(device=args.device, precision=str(dtype), gpu=torch.cuda.get_device_name() if args.device == 'cuda' else None,
                      training_examples=len(training), heldout_tasks=len(heldout),
                      trainable_parameters=sum(parameter.numel() for parameter in trainable),
                      dataset_sha256=hashlib.sha256((out / 'dataset.json').read_bytes()).hexdigest())

        def encode(row):
            messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt(row)}]
            prefix = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            complete = tokenizer.apply_chat_template(messages + [{'role': 'assistant', 'content': row['source']}], tokenize=False)
            ids = tokenizer(complete, add_special_tokens=False)['input_ids']
            prefix_ids = tokenizer(prefix, add_special_tokens=False)['input_ids']
            if len(ids) > 1536 or ids[:len(prefix_ids)] != prefix_ids:
                raise ValueError(f"Invalid or overlong tokenized example: {row['id']} ({len(ids)})")
            return {'input_ids': torch.tensor([ids], device=args.device),
                    'attention_mask': torch.ones((1, len(ids)), device=args.device, dtype=torch.long),
                    'labels': torch.tensor([[-100] * len(prefix_ids) + ids[len(prefix_ids):]], device=args.device)}

        for row in training + heldout:
            encode(row)

        def evaluate(tag):
            model.eval()
            model.config.use_cache = True
            records = []
            with torch.no_grad():
                for row in heldout:
                    if args.device == 'cuda':
                        torch.cuda.empty_cache()
                    loss = float(model(**encode(row)).loss)
                    text = tokenizer.apply_chat_template([{'role': 'system', 'content': SYSTEM},
                        {'role': 'user', 'content': prompt(row)}], tokenize=False, add_generation_prompt=True)
                    tokens = tokenizer(text, return_tensors='pt').to(args.device)
                    generated = model.generate(**tokens, do_sample=False, max_new_tokens=256,
                                               pad_token_id=tokenizer.eos_token_id)
                    raw = tokenizer.decode(generated[0, tokens.input_ids.shape[1]:], skip_special_tokens=True)
                    folder = out / tag / row['id']
                    folder.mkdir(parents=True, exist_ok=False)
                    (folder / 'response.txt').write_text(raw, encoding='utf-8')
                    valid = syntax_check(row, raw, folder)
                    records.append({'id': row['id'], 'language': row['language'], 'loss': loss, 'syntax_valid': valid})
                    print(json.dumps({'evaluation': tag, **records[-1]}), flush=True)
            summary = {'mean_heldout_loss': sum(record['loss'] for record in records) / len(records),
                       'syntax_valid': sum(record['syntax_valid'] for record in records), 'total': len(records),
                       'tasks': records, 'generated_code_executed': False}
            save(out / tag / 'evaluation.json', summary)
            return summary

        report['status'] = 'baseline_evaluation'
        save(out / 'results.json', report)
        report['baseline'] = evaluate('baseline')
        optimizer = torch.optim.AdamW(trainable, lr=1e-4)
        scaler = torch.amp.GradScaler('cuda', enabled=dtype == torch.float16)
        for round_number in range(1, args.rounds + 1):
            report['status'] = 'training'
            save(out / 'results.json', report)
            model.train()
            model.config.use_cache = False
            optimizer.zero_grad(set_to_none=True)
            losses = []
            for index, row in enumerate(training):
                divisor = min(4, len(training) - (index // 4) * 4)
                with torch.autocast(args.device, dtype=dtype, enabled=args.device == 'cuda'):
                    loss = model(**encode(row)).loss
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite training loss')
                scaler.scale(loss / divisor).backward()
                losses.append(float(loss.detach()))
                if (index + 1) % 4 == 0 or index + 1 == len(training):
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(trainable, 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
                print(json.dumps({'round': round_number, 'example': row['id'], 'loss': losses[-1]}), flush=True)
            checkpoint = out / f'round-{round_number}'
            model.peft_config['default'].base_model_name_or_path = report['base_model']
            model.save_pretrained(checkpoint, safe_serialization=True, save_embedding_layers=False)
            tokenizer.save_pretrained(checkpoint)
            save(checkpoint / 'jarvis_training.json', {'languages': ['javascript', 'sql'], 'python_replay': True,
                                                       'system_prompt': SYSTEM, 'source_dataset_sha256': report['dataset_sha256']})
            delta = sum(float((parameter.detach().float().cpu() - old).abs().sum()) for parameter, old in zip(trainable, before))
            if delta <= 0:
                raise RuntimeError('Adapter weights did not change')
            evaluation = evaluate(f'round-{round_number}-evaluation')
            report['rounds'].append({'round': round_number, 'mean_training_loss': sum(losses) / len(losses),
                                     'optimizer_steps': (len(training) + 3) // 4, 'adapter_absolute_delta': delta,
                                     'checkpoint': str(checkpoint),
                                     'adapter_sha256': hashlib.sha256((checkpoint / 'adapter_model.safetensors').read_bytes()).hexdigest(),
                                     'evaluation': evaluation})
            save(out / 'results.json', report)
        best = min(report['rounds'], key=lambda item: item['evaluation']['mean_heldout_loss'])
        report.update(status='complete', completed=datetime.now(timezone.utc).isoformat(),
                      best_checkpoint=best['checkpoint'],
                      peak_tensor_vram_bytes=torch.cuda.max_memory_allocated() if args.device == 'cuda' else 0,
                      production_promoted=False)
        save(out / 'results.json', report)
        print(json.dumps({'status': report['status'], 'best_checkpoint': report['best_checkpoint']}), flush=True)
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        save(out / 'results.json', report)
        raise


if __name__ == '__main__':
    main()
