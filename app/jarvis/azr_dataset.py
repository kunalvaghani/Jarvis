"""Versioned, de-duplicated AZR task datasets with leak-proof train/validation/held-out splits.

* Splits are fixed by **disjoint seed ranges and disjoint structure signatures**: a structure skeleton
  (tool sequence or program family + constant) that appears in one split never appears in another,
  so near-duplicates cannot leak between training and evaluation.
* Exact duplicates are removed by task id (content hash); near-duplicates by signature.
* Every record carries provenance: generator, seed, environment/oracle versions, and how its answer
  was obtained (always the deterministic environment or a Jarvis-authored oracle program, never a model).
* Model answers and their verification are stored next to the tasks; incorrect answers are kept for
  analysis but are never written back as ground truth.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .azr_tasks import ENV_VERSION, ORACLE_VERSION, abduction_task, deduction_task, induction_task, signature, task_id

SCHEMA_VERSION = 1
SPLITS = ('train', 'validation', 'heldout')
# Disjoint seed ranges per split; the held-out range is reserved for the sealed evaluator.
SEED_RANGES = {'train': (10_000, 60_000), 'validation': (60_000, 70_000), 'heldout': (900_000, 910_000)}
GENERATORS = {'deduction': deduction_task, 'abduction': abduction_task, 'induction': induction_task}
# Program families reserved for the held-out split test generalization to unseen induction families.
HELDOUT_FAMILIES = {'initials', 'rotate_k', 'count_k'}


def generate(split, counts, reserved_signatures=frozenset(), max_tries=20000):
    """counts: {mode: n}. Returns curated tasks plus a curation report (duplicates and leakage rejected)."""
    low, high = SEED_RANGES[split]
    tasks, ids, signatures = [], set(), {}
    report = {'split': split, 'exact_duplicates': 0, 'reserved_signature_rejected': 0, 'near_duplicate_rejected': 0}
    for mode, wanted in counts.items():
        made, seed = 0, low + {'deduction': 0, 'abduction': 15_000, 'induction': 30_000}[mode] % (high - low)
        tries = 0
        while made < wanted and tries < max_tries:
            tries += 1
            seed += 1
            if seed >= high:
                seed = low
            if mode == 'induction':
                families = HELDOUT_FAMILIES if split == 'heldout' else None
                task = induction_task(seed, families)
                if split != 'heldout' and task['family'] in HELDOUT_FAMILIES:
                    continue
            else:
                task = GENERATORS[mode](seed)
            identifier, skeleton = task_id(task), signature(task)
            if identifier in ids:
                report['exact_duplicates'] += 1
                continue
            if skeleton in reserved_signatures:
                report['reserved_signature_rejected'] += 1
                continue
            if signatures.get(skeleton, 0) >= (3 if mode == 'induction' else 1):
                report['near_duplicate_rejected'] += 1
                continue
            ids.add(identifier)
            signatures[skeleton] = signatures.get(skeleton, 0) + 1
            tasks.append({'schema_version': SCHEMA_VERSION, 'id': identifier, 'split': split, 'signature': skeleton,
                          'task': task, 'provenance': {
                              'generator': 'jarvis.azr_tasks.' + GENERATORS[mode].__name__, 'seed': task['seed'],
                              'env_version': ENV_VERSION, 'oracle_version': ORACLE_VERSION,
                              'answer_source': 'deterministic simulation' if mode != 'induction'
                              else 'Jarvis-authored template program executed twice'}})
            made += 1
        report[mode] = made
    return tasks, report


def build(counts_by_split):
    """Generate held-out first, then validation, then train, each excluding earlier signatures."""
    datasets, reports, reserved = {}, {}, set()
    for split in ('heldout', 'validation', 'train'):
        tasks, report = generate(split, counts_by_split[split], frozenset(reserved))
        datasets[split], reports[split] = tasks, report
        reserved |= {t['signature'] for t in tasks}
    leaks = {}
    for a in SPLITS:
        for b in SPLITS:
            if a < b:
                shared = {t['signature'] for t in datasets[a]} & {t['signature'] for t in datasets[b]}
                shared_ids = {t['id'] for t in datasets[a]} & {t['id'] for t in datasets[b]}
                leaks[a + '/' + b] = {'signatures': len(shared), 'ids': len(shared_ids)}
    return datasets, {'reports': reports, 'leakage': leaks}


def write(folder, datasets, meta):
    folder = Path(folder)
    if folder.exists():
        raise FileExistsError('Refusing to overwrite a versioned dataset: ' + str(folder))
    folder.mkdir(parents=True)
    hashes = {}
    for split, tasks in datasets.items():
        body = ''.join(json.dumps(t, sort_keys=True) + '\n' for t in tasks)
        (folder / (split + '.jsonl')).write_text(body, encoding='utf-8')
        hashes[split] = hashlib.sha256(body.encode()).hexdigest()
    manifest = {'schema_version': SCHEMA_VERSION, 'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'env_version': ENV_VERSION, 'oracle_version': ORACLE_VERSION, 'sha256': hashes,
                'counts': {s: len(t) for s, t in datasets.items()}, **meta}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    return manifest


def load(folder, split):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    body = (folder / (split + '.jsonl')).read_text(encoding='utf-8')
    if hashlib.sha256(body.encode()).hexdigest() != manifest['sha256'][split]:
        raise ValueError('Dataset file does not match its manifest hash: ' + split)
    return [json.loads(line) for line in body.splitlines() if line.strip()]
