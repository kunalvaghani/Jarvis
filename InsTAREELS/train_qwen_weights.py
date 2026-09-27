"""Actual local CUDA/CPU LoRA training. No Hub uploads, cloud jobs or experience recall.

Uses executed passing answers and explicitly attributed checked reference corrections. Project-level held-out
split is fixed before tokenization/training. Every round saves adapter weights.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
MODEL = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
REVISION = 'ea3f2471cf1b1f0db85067f1ef93848e38e88c25'
BASE_SHA256 = 'f9523886352217ded3aeeef552b381af79d568c6d49a4b9e423288cea56b0a44'
SYSTEM = "You are Jarvis, a coding assistant. Return only complete Python source code, without Markdown."


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def prompt(project):
    return ("Write a complete Python JSON CLI. Read one JSON value from sys.stdin and "
            "write exactly one JSON value to stdout. Include all imports. " + project['contract'] +
            "\nExamples: " + json.dumps(project['cases'][:2], ensure_ascii=False))


def dataset(source, out, reference_corrections=False):
    source, out = source.resolve(), out.resolve()
    from jarvis.coding_curriculum import catalogue
    from train_coding import inspect_source, check
    results = json.loads((source / 'results.json').read_text(encoding='utf-8'))
    rows = {r['id']: r for r in catalogue()}
    accepted = []
    for result in results['projects']:
        if not result['passed']:
            continue
        attempt = next(a for a in reversed(result['attempts']) if a['passed'])
        file = source / attempt.get('path', str(Path(result['id']) / f"attempt-{attempt['number']}")) / 'main.py'
        if not file.resolve().is_relative_to(source):
            raise ValueError('Training source escapes curriculum directory')
        content = file.read_text(encoding='utf-8')
        kind, error = inspect_source(content)
        if kind:
            raise ValueError(f"Rejected training source {result['id']}: {error}")
        folder = out / 'dataset-verification' / result['id']
        folder.mkdir(parents=True, exist_ok=False)
        (folder / 'main.py').write_text(content, encoding='utf-8')
        checks = check(folder, rows[result['id']]['cases'])
        if not all(c['passed'] for c in checks):
            raise ValueError(f"Training source failed re-verification: {result['id']}")
        accepted.append({**rows[result['id']], 'content': content,
                         'sha256': hashlib.sha256(content.encode()).hexdigest()})
    rng = random.Random(20260927)
    rng.shuffle(accepted)
    heldout = accepted[:14]
    training = sorted(accepted[14:], key=lambda p: (p['level'], p['id']))
    corrected=[]
    if reference_corrections:
        from jarvis.coding_training_data import reference_source
        for result in results['projects']:
            if result['passed']:
                continue
            project=rows[result['id']]
            content=reference_source(project['name'])
            kind,error=inspect_source(content)
            if kind:
                raise ValueError(f"Rejected reference correction {project['id']}: {error}")
            folder=out/'dataset-verification'/project['id']
            folder.mkdir(parents=True,exist_ok=False)
            (folder/'main.py').write_text(content,encoding='utf-8')
            checks=check(folder,project['cases'])
            dump(folder/'verification.json',checks)
            if not all(c['passed'] for c in checks):
                raise ValueError(f"Reference correction failed checks: {project['id']}")
            corrected.append({**project,'content':content,'sha256':hashlib.sha256(content.encode()).hexdigest(),
                              'target_origin':'trusted local reference correction; oracle consistency, not independent validation'})
        training=sorted(training+corrected,key=lambda p:(p['level'],p['id']))
    data={'training':training,'heldout':heldout,
          'excluded_failed_projects':[] if corrected else [p['id'] for p in results['projects'] if not p['passed']]}
    if corrected:
        data['reference_corrected_projects']=[p['id'] for p in corrected]
    dump(out/'dataset.json',data)
    return training, heldout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=BASE / 'artifacts/coding-curriculum-20260927T101300Z')
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--device', choices=('cuda','cpu'), default='cuda')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--resume', type=Path, help='Continue optimizer, RNG and adapter from a completed round checkpoint')
    parser.add_argument('--initialize-adapter',type=Path,help='Warm-start weights on a deliberately expanded dataset with fresh optimizer state')
    parser.add_argument('--reference-corrections',action='store_true',help='Add case-checked reference-derived corrections for the 31 failed projects')
    parser.add_argument('--jarvis-variant',action='store_true',help='Train both CLI prompts and the actual Jarvis code-edit request format')
    args = parser.parse_args()
    if not 1 <= args.rounds <= 20:
        parser.error('--rounds must be between 1 and 20')
    if args.resume and args.initialize_adapter:
        parser.error('--resume and --initialize-adapter are mutually exclusive')
    out = args.output or BASE / 'artifacts' / ('qwen-weight-training-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    os.environ.update(HF_HOME=str(BASE / 'models/hf-training-cache'), USE_TF='0', USE_FLAX='0', HF_HUB_DISABLE_XET='1')
    if (BASE/'models/qwen-jarvis-base/model.safetensors').is_file():
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    report = {'status': 'preparing', 'base_model': MODEL, 'method': 'supervised local LoRA gradient training',
              'started': datetime.now(timezone.utc).isoformat(), 'rounds': [], 'output': str(out)}
    dump(out / 'results.json', report)
    try:
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import LoraConfig, get_peft_model, PeftModel
        from train_coding import inspect_source, check
        device = args.device
        if device == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable: refusing an unannounced CPU training fallback')
        torch.set_num_threads(8)
        random.seed(42)
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        revision = REVISION
        modeldir = BASE / 'models/qwen-jarvis-base'
        if not (modeldir/'model.safetensors').is_file():
            snapshot_download(MODEL, revision=revision, local_dir=modeldir,
                              allow_patterns=['*.json', '*.safetensors', '*.txt', '*.md', 'LICENSE*'])
        digest = hashlib.sha256()
        with (modeldir/'model.safetensors').open('rb') as stream:
            while block := stream.read(1024*1024):
                digest.update(block)
        if digest.hexdigest() != BASE_SHA256:
            raise ValueError('Base model checksum does not match pinned upstream Qwen revision')
        report['base_sha256'] = digest.hexdigest()
        training, heldout = dataset(args.source, out, args.reference_corrections)
        if args.jarvis_variant:
            data=json.loads((out/'dataset.json').read_text(encoding='utf-8'))
            data['prompt_variants']=['cli','jarvis_code_edit']
            dump(out/'dataset.json',data)
        examples=[(p,variant) for p in training for variant in ([False,True] if args.jarvis_variant else [False])]
        tokenizer = AutoTokenizer.from_pretrained(modeldir, local_files_only=True)
        tokenizer.pad_token = tokenizer.eos_token
        dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if device == 'cuda' else torch.float32
        base = AutoModelForCausalLM.from_pretrained(modeldir, torch_dtype=dtype,
                                                   attn_implementation='sdpa', local_files_only=True).to(device)
        report.update(base_revision=revision, device=device, gpu=torch.cuda.get_device_name() if device == 'cuda' else None, precision=str(dtype), training_projects=len(training),training_examples=len(examples),
                      heldout_projects=len(heldout), dataset_sha256=hashlib.sha256((out/'dataset.json').read_bytes()).hexdigest())
        max_length = 1536
        def encode(p,jarvis_variant=False):
            user=prompt(p)
            if jarvis_variant:
                from qwen_jarvis_coder import request_prompt
                user=request_prompt({'goal':user,'path':'main.py','reason':'Implement the requested JSON CLI','current':'',
                     'references':[],'repository_instructions':[],'selected_skills':[],'previous':None,'validation_error':None})
            messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]
            prefix = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            complete = tokenizer.apply_chat_template(messages + [{'role': 'assistant', 'content': p['content']}], tokenize=False)
            ids = tokenizer(complete, add_special_tokens=False)['input_ids']
            prefixids = tokenizer(prefix, add_special_tokens=False)['input_ids']
            if len(ids) > max_length:
                raise ValueError(f"{p['id']} has {len(ids)} tokens; never silently truncate training targets")
            if ids[:len(prefixids)] != prefixids:
                raise ValueError('Chat template boundary does not match completion')
            return {'input_ids': torch.tensor([ids], device=device),
                    'attention_mask': torch.ones((1, len(ids)), dtype=torch.long, device=device),
                    'labels': torch.tensor([[-100]*len(prefixids) + ids[len(prefixids):]], device=device)}
        # Validate all lengths before allocating adapters or performing any gradient step.
        for p in training + heldout:
            encode(p)
        if args.jarvis_variant:
            for p in training:
                encode(p,True)
        def evaluate(model, name):
            model.eval()
            model.config.use_cache = True
            losses, projects = [], []
            with torch.no_grad():
                for p in heldout:
                    losses.append(float(model(**encode(p)).loss))
                    if device == 'cuda':
                        # Release large teacher-forced vocabulary/logit buffers before
                        # generation to avoid WDDM paging on the 4 GB laptop GPU.
                        torch.cuda.empty_cache()
                    text = tokenizer.apply_chat_template([{'role':'system','content':SYSTEM},
                            {'role':'user','content':prompt(p)}], tokenize=False, add_generation_prompt=True)
                    tokens = tokenizer(text, return_tensors='pt').to(device)
                    result = model.generate(**tokens, do_sample=False, max_new_tokens=1024,
                                            pad_token_id=tokenizer.pad_token_id)
                    raw = tokenizer.decode(result[0, tokens.input_ids.shape[1]:], skip_special_tokens=True)
                    folder = out / name / p['id']
                    folder.mkdir(parents=True, exist_ok=False)
                    (folder / 'response.txt').write_text(raw, encoding='utf-8')
                    match = re.search(r'```(?:python)?\s*\n(.*?)```', raw, re.S)
                    content = match.group(1) if match else raw
                    (folder/'main.py').write_text(content, encoding='utf-8')
                    try:
                        kind, error = inspect_source(content)
                        if kind:
                            raise ValueError(f'{kind}: {error}')
                        cases = check(folder, p['cases'])
                        item = {'id':p['id'], 'passed':all(c['passed'] for c in cases), 'cases':cases}
                    except (SyntaxError, ValueError) as exc:
                        item = {'id':p['id'], 'passed':False, 'error':str(exc)}
                    projects.append(item)
                    dump(folder/'verification.json', item)
                    print(json.dumps({'evaluation': name, 'project':p['id'], 'passed':item['passed']}), flush=True)
            result = {'heldout_loss':sum(losses)/len(losses), 'projects_passed':sum(p['passed'] for p in projects),
                      'projects_total':len(projects), 'projects':projects}
            dump(out/name/'evaluation.json', result)
            return result
        report['status'] = 'baseline_evaluation'
        dump(out/'results.json', report)
        prior_adapter=args.resume or args.initialize_adapter
        prior_report = prior_adapter.parent/'results.json' if prior_adapter else None
        prior = json.loads(prior_report.read_text(encoding='utf-8')) if prior_report and prior_report.is_file() else {}
        prior_data_path=prior_report.parent/'dataset.json' if prior_report else None
        prior_data=json.loads(prior_data_path.read_text(encoding='utf-8')) if prior_data_path and prior_data_path.is_file() else {}
        if (prior.get('status') == 'complete' and prior_data.get('heldout') == heldout and
                prior.get('base_sha256') == report['base_sha256'] and prior.get('precision') == report['precision']):
            report['baseline'] = prior['baseline']
            report['baseline_reference'] = str(prior_report)
        else:
            report['baseline'] = evaluate(base, 'baseline')
        adapter=args.resume or args.initialize_adapter
        if adapter:
            model = PeftModel.from_pretrained(base, adapter, is_trainable=True)
            report['initialized_from']=str(adapter.resolve())
        else:
            model = get_peft_model(base, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                       target_modules=['q_proj','k_proj','v_proj','o_proj'], task_type='CAUSAL_LM'))
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        model.enable_input_require_grads()
        params = [p for p in model.parameters() if p.requires_grad]
        report['trainable_parameters'] = sum(p.numel() for p in params)
        before = [p.detach().float().cpu().clone() for p in params]
        optimizer = torch.optim.AdamW(params, lr=2e-4)
        scaler = torch.amp.GradScaler('cuda', enabled=dtype == torch.float16)
        completed = 0
        if args.resume:
            state = torch.load(args.resume/'training-state.pt', map_location='cpu', weights_only=True)
            if state['dataset_sha256'] != report['dataset_sha256'] or state['base_revision'] != revision:
                raise ValueError('Resume dataset/base revision mismatch')
            optimizer.load_state_dict(state['optimizer'])
            if state['scaler'] and scaler.is_enabled():
                scaler.load_state_dict(state['scaler'])
            torch.set_rng_state(state['rng'])
            if device == 'cuda':
                torch.cuda.set_rng_state_all(state['cuda_rng'])
            completed = state['completed_rounds']
        for roundno in range(completed + 1, completed + args.rounds + 1):
            report['status'] = 'training'
            dump(out/'results.json', report)
            model.train()
            model.config.use_cache = False
            losses = []
            optimizer.zero_grad(set_to_none=True)
            # Fixed easy-to-hard order each round; no held-out project used in updates.
            for i,(p,variant) in enumerate(examples):
                divisor = min(4, len(examples) - (i//4)*4)
                with torch.autocast(device, dtype=dtype, enabled=device == 'cuda'):
                    loss = model(**encode(p,variant)).loss
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite loss; refusing to persist invalid weights')
                scaler.scale(loss/divisor).backward()
                losses.append(float(loss.detach()))
                if (i+1)%4 == 0 or i+1 == len(examples):
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(params, 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
                print(json.dumps({'round':roundno, 'project':p['id'], 'prompt_variant':'jarvis_code_edit' if variant else 'cli','loss':losses[-1]}), flush=True)
            checkpoint = out/f'round-{roundno}'
            model.peft_config['default'].base_model_name_or_path = MODEL
            model.save_pretrained(checkpoint, safe_serialization=True, save_embedding_layers=False)
            tokenizer.save_pretrained(checkpoint)
            torch.save({'optimizer':optimizer.state_dict(), 'scaler':scaler.state_dict(),
                        'rng':torch.get_rng_state(), 'cuda_rng':torch.cuda.get_rng_state_all() if device == 'cuda' else [],
                        'completed_rounds':roundno, 'dataset_sha256':report['dataset_sha256'],
                        'base_revision':revision}, checkpoint/'training-state.pt')
            delta = sum(float((p.detach().float().cpu()-old).abs().sum()) for p,old in zip(params,before))
            if not delta > 0:
                raise RuntimeError('No adapter parameters changed')
            evaluated = evaluate(model, f'round-{roundno}-evaluation')
            report['rounds'].append({'round':roundno, 'training_loss':sum(losses)/len(losses),
                'parameter_absolute_delta':delta, 'checkpoint':str(checkpoint),
                'adapter_sha256':hashlib.sha256((checkpoint/'adapter_model.safetensors').read_bytes()).hexdigest(),
                **evaluated})
            dump(out/'results.json', report)
        prior_rounds = prior.get('rounds',[]) if prior_data.get('heldout') == heldout and prior.get('base_sha256') == report['base_sha256'] else []
        candidates=[*prior_rounds,*report['rounds']]
        best = max(candidates, key=lambda r:(r['projects_passed'], -r['heldout_loss']))
        report['selected_heldout_passes']=best['projects_passed']
        report['last_training_checkpoint']=report['rounds'][-1]['checkpoint']
        report.update(status='complete', completed=datetime.now(timezone.utc).isoformat(),
            best_checkpoint=best['checkpoint'], peak_vram_bytes=torch.cuda.max_memory_allocated() if device == 'cuda' else 0,
            promotion_eligible=best['projects_passed'] > report['baseline']['projects_passed'] and
                               best['heldout_loss'] < report['baseline']['heldout_loss'])
        report['status'] = 'exporting_merged_model'
        dump(out/'results.json', report)
        model.load_adapter(best['checkpoint'], adapter_name='selected')
        model.set_adapter('selected')
        merged = model.merge_and_unload(safe_merge=True, adapter_names=['selected'])
        from safetensors import safe_open
        key = 'model.layers.0.self_attn.q_proj.weight'
        with safe_open(modeldir/'model.safetensors', framework='pt', device='cpu') as source:
            original = source.get_tensor(key).float()
        merged_delta = float((merged.state_dict()[key].detach().float().cpu()-original).abs().sum())
        if not merged_delta > 0:
            raise RuntimeError('Merged model sample projection remained unchanged')
        report['merged_projection_absolute_delta'] = merged_delta
        merged_folder = out/'merged-model'
        merged.save_pretrained(merged_folder, safe_serialization=True, max_shard_size='2GB')
        tokenizer.save_pretrained(merged_folder)
        shutil.copy2(modeldir/'LICENSE', merged_folder/'LICENSE')
        digest = hashlib.sha256()
        with (merged_folder/'model.safetensors').open('rb') as stream:
            while block := stream.read(1024*1024):
                digest.update(block)
        report.update(status='complete', merged_model=str(merged_folder), merged_sha256=digest.hexdigest())
        # Selection report is reviewable; promotion into production is separate.
        dump(out/'results.json', report)
        print(json.dumps({k:report[k] for k in ('status','best_checkpoint','promotion_eligible')}), flush=True)
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        dump(out/'results.json', report)
        raise


if __name__ == '__main__':
    main()
