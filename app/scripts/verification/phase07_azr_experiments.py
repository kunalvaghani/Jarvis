"""Phase 7 real runs: compatibility, baseline, cancel/resume and preemption smoke tests, LoRA training,
sealed held-out gate, export compatibility, GRPO feasibility and experimental registration.

Runs on this machine's RTX 3050 4 GB through .venv-training. Every step records its own evidence in
--out (refuses to overwrite). Nothing is registered with Ollama and no configured model changes.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
TRAIN_PY = str(BASE / '.venv-training' / 'Scripts' / 'python.exe')
DATASET = BASE / '.jarvis-runtime' / 'azr' / 'datasets' / 'azr-v1-20261019'


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=120)
    args = parser.parse_args(argv)
    out = args.out
    if out.exists():
        raise SystemExit('refusing to overwrite ' + str(out))
    out.mkdir(parents=True)
    record = {'started_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'steps': {}}
    log_path = out / 'run-log.txt'

    def log(message):
        line = datetime.now().strftime('%H:%M:%S ') + str(message)
        print(line, flush=True)
        with log_path.open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')

    def save():
        (out / 'experiment-record.json').write_text(json.dumps(record, indent=1, default=str), encoding='utf-8')

    def step(name, function):
        started = time.monotonic()
        log('start ' + name)
        try:
            result = function()
        except Exception as exc:
            result = {'error': type(exc).__name__ + ': ' + str(exc)[:800]}
        record['steps'][name] = {'seconds': round(time.monotonic() - started, 1), 'result': result}
        log(f'done {name} ({record["steps"][name]["seconds"]} s): ' + json.dumps(result, default=str)[:400])
        save()
        return result

    def train(run, *extra, background=False):
        command = [TRAIN_PY, '-m', 'scripts.training.train_azr_lora', '--dataset', str(DATASET), '--out', str(out / run), *extra]
        if background:
            return subprocess.Popen(command, cwd=BASE, stdout=(out / (run + '.log')).open('a'), stderr=subprocess.STDOUT)
        with (out / (run + '.log')).open('a') as handle:
            return subprocess.run(command, cwd=BASE, stdout=handle, stderr=subprocess.STDOUT, timeout=7200).returncode

    def metrics(run):
        path = out / run / 'metrics.jsonl'
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []

    def unload_ollama():
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/ps', timeout=5) as response:
                models = [m['name'] for m in json.loads(response.read()).get('models', [])]
            for name in models:
                body = json.dumps({'model': name, 'keep_alive': 0}).encode()
                urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434/api/generate', body,
                                                              {'Content-Type': 'application/json'}), timeout=30).read()
            return models
        except OSError:
            return []

    # 0. hardware and versions
    def environment():
        probe = subprocess.run([TRAIN_PY, '-c', 'import json,torch,transformers,peft,platform;'
                                'f,t=torch.cuda.mem_get_info();print(json.dumps({"python":platform.python_version(),'
                                '"torch":torch.__version__,"cuda":torch.version.cuda,"gpu":torch.cuda.get_device_name(0),'
                                '"bf16":torch.cuda.is_bf16_supported(),"vram_free_mb":f//2**20,"vram_total_mb":t//2**20,'
                                '"transformers":transformers.__version__,"peft":peft.__version__}))'],
                               capture_output=True, text=True, cwd=BASE, timeout=300)
        import psutil
        return {**json.loads(probe.stdout.strip().splitlines()[-1]), 'ram_total_gb': round(psutil.virtual_memory().total / 2 ** 30, 1),
                'ram_available_gb': round(psutil.virtual_memory().available / 2 ** 30, 1), 'unloaded_ollama_models': unload_ollama()}
    step('environment', environment)

    # 1. existing adapter compatibility (inspection only)
    def existing_adapter():
        code = ('import os,json,torch;os.environ.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1");'
                'from transformers import AutoModelForCausalLM,AutoTokenizer;from peft import PeftModel;'
                'b="models/qwen-jarvis-base";a="artifacts/training/qwen-pc-training-20260927T161836Z/round-2";'
                't=AutoTokenizer.from_pretrained(b,local_files_only=True);'
                'm=AutoModelForCausalLM.from_pretrained(b,torch_dtype=torch.bfloat16,local_files_only=True).to("cuda");'
                'm=PeftModel.from_pretrained(m,a,local_files_only=True);'
                'x=t("open my notes project",return_tensors="pt").to("cuda");'
                'y=m.generate(**x,max_new_tokens=8,do_sample=False,pad_token_id=t.eos_token_id);'
                'print(json.dumps({"loaded":True,"generated_tokens":int(y.shape[1]-x["input_ids"].shape[1]),'
                '"peft_type":m.peft_config["default"].peft_type,"r":m.peft_config["default"].r}))')
        run = subprocess.run([TRAIN_PY, '-c', code], capture_output=True, text=True, cwd=BASE, timeout=600)
        return json.loads(run.stdout.strip().splitlines()[-1]) if run.returncode == 0 else {'error': run.stderr[-600:]}
    step('existing_pc_adapter_compatibility', existing_adapter)

    from evolution_eval.model_gate import ModelGate
    gate = ModelGate(BASE)
    base_cache = out / 'base-heldout.json'

    # 2. baseline on the sealed held-out set
    def baseline():
        tasks = gate.tasks()
        answers, summary = gate.generate('base', out / 'gate-base')
        scores = gate.score(tasks, answers)
        report = gate.summarize(tasks, scores, answers, summary)
        base_cache.write_text(json.dumps({'seal': gate.retention.seal(), 'scores': scores, 'summary': report}), encoding='utf-8')
        return report
    step('baseline_heldout', baseline)

    # 3. cancellation + exact resume smoke test, compared with an uninterrupted reference run
    def cancel_resume():
        small = ['--max-steps', '4', '--checkpoint-every', '2', '--grad-accum', '2', '--ignore-foreground']
        reference = train('smoke-reference', *small)
        process = train('smoke-cancel', *small, background=True)
        while process.poll() is None:
            if any(m.get('step', 0) >= 2 for m in metrics('smoke-cancel')):
                (out / 'smoke-cancel' / 'STOP').write_text('stop', encoding='utf-8')
                break
            time.sleep(.5)
        process.wait(1800)
        stopped = json.loads((out / 'smoke-cancel' / 'final.json').read_text(encoding='utf-8'))
        (out / 'smoke-cancel' / 'STOP').unlink()
        resumed = train('smoke-cancel', *small, '--resume')
        final = json.loads((out / 'smoke-cancel' / 'final.json').read_text(encoding='utf-8'))
        ref_losses = [m['loss'] for m in metrics('smoke-reference') if 'loss' in m]
        run_losses = {m['step']: m['loss'] for m in metrics('smoke-cancel') if 'loss' in m}
        return {'reference_exit': reference, 'stopped': stopped, 'resume_exit': resumed, 'final': final,
                'reference_losses': ref_losses, 'interrupted_then_resumed_losses': [run_losses[s] for s in sorted(run_losses)],
                'max_abs_loss_difference': round(max(abs(a - run_losses[i + 1]) for i, a in enumerate(ref_losses)), 6)}
    step('cancel_and_resume', cancel_resume)

    # 4. foreground preemption with a real lease in the shared GPU registry
    def preemption():
        from jarvis.gpu_scheduler import Lease, configured
        process = train('smoke-preempt', '--max-steps', '20', '--checkpoint-every', '5', '--grad-accum', '2', background=True)
        lease = None
        while process.poll() is None:
            if lease is None and any(m.get('step', 0) >= 2 for m in metrics('smoke-preempt')):
                lease = Lease('question', 'qwen3.5:0.8b', configured())
                lease.acquire()
                log('foreground lease admitted (role question)')
            time.sleep(.3)
        if lease:
            lease.close()
        final = json.loads((out / 'smoke-preempt' / 'final.json').read_text(encoding='utf-8'))
        checkpoints = sorted(p.name for p in (out / 'smoke-preempt').glob('checkpoint-*'))
        return {'final': final, 'checkpoints': checkpoints, 'lease_acquired': lease is not None}
    step('foreground_preemption', preemption)

    # 5. main training run
    def main_training():
        unload_ollama()
        code = train('lora-main', '--max-steps', str(args.steps), '--checkpoint-every', '20', '--grad-accum', '8',
                     '--max-len', '896', '--max-minutes', '60')
        rows = metrics('lora-main')
        losses = [m['loss'] for m in rows if 'loss' in m]
        return {'exit': code, 'final': json.loads((out / 'lora-main' / 'final.json').read_text(encoding='utf-8')),
                'first_losses': losses[:5], 'last_losses': losses[-5:], 'steps_logged': len(losses),
                'max_peak_vram_mb': max((m.get('peak_vram_mb', 0) for m in rows), default=0),
                'max_rss_mb': max((m.get('rss_mb', 0) for m in rows), default=0)}
    trained = step('lora_main_training', main_training)
    final_checkpoint = None
    checkpoints = sorted((out / 'lora-main').glob('checkpoint-*'), key=lambda p: int(p.name.split('-')[1]))
    if checkpoints:
        final_checkpoint = checkpoints[-1]

    # 6. sealed held-out gate (paired against the base answers already generated)
    if final_checkpoint and not trained.get('error'):
        step('heldout_gate', lambda: gate.evaluate(final_checkpoint, out / 'gate-candidate', base_cache=base_cache))
        step('export_compatibility', lambda: (subprocess.run(
            [TRAIN_PY, '-m', 'scripts.training.export_azr_adapter', '--adapter', str(final_checkpoint), '--tasks',
             str(BASE / 'evolution_eval/heldout/azr_tasks.jsonl'), '--out', str(out / 'export'), '--limit', '24'],
            cwd=BASE, capture_output=True, text=True, timeout=3600).returncode,
            json.loads((out / 'export' / 'export-check.json').read_text(encoding='utf-8')))[1])
        step('grpo_feasibility', lambda: (subprocess.run(
            [TRAIN_PY, '-m', 'scripts.training.grpo_feasibility', '--adapter', str(final_checkpoint), '--dataset', str(DATASET),
             '--out', str(out / 'grpo'), '--tasks', '4', '--group', '4'], cwd=BASE, capture_output=True, text=True,
            timeout=3600).returncode, json.loads((out / 'grpo' / 'grpo-feasibility.json').read_text(encoding='utf-8')))[1])
        def register():
            from jarvis.model_registry import ModelRegistry
            from scripts.training.train_qwen_weights import BASE_SHA256
            import hashlib
            gate_report = record['steps']['heldout_gate']['result']
            export = record['steps']['export_compatibility']['result']
            dataset_sha = hashlib.sha256((DATASET / 'manifest.json').read_bytes()).hexdigest()
            return ModelRegistry(BASE).register(final_checkpoint, BASE_SHA256, dataset_sha, gate_report,
                                                export if isinstance(export, dict) and 'error' not in export else None)
        step('registry_experimental', register)
    record['finished_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    save()


if __name__ == '__main__':
    main()
