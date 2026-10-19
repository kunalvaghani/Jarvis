"""Build the versioned AZR dataset: seeded tasks + optional local-proposer tasks, all oracle-verified.

* Held-out tasks are written into the sealed evaluator (``evolution_eval/heldout/azr_tasks.jsonl``);
  train and validation go to ``--out`` (refuses to overwrite).
* Answerability: every induction reference program is executed twice in the sandbox on its visible and
  hidden cases; any task whose reference fails is dropped (and counted).
* Proposer tasks (local ``qwen3.5:9b``) are validated by the oracle, scored for learnability with G local
  solver rollouts, de-duplicated, checked against held-out signatures, and added to train only.
"""
import argparse
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--heldout-out', type=Path, default=BASE / 'evolution_eval' / 'heldout' / 'azr_tasks.jsonl')
    parser.add_argument('--train', type=int, nargs=3, default=[400, 400, 300], metavar=('DED', 'ABD', 'IND'))
    parser.add_argument('--validation', type=int, nargs=3, default=[30, 30, 30])
    parser.add_argument('--heldout', type=int, nargs=3, default=[60, 60, 60])
    parser.add_argument('--proposals', type=int, default=0, help='local proposer attempts per mode (0 disables)')
    args = parser.parse_args(argv)
    if args.heldout_out.exists():
        raise SystemExit('Refusing to overwrite sealed held-out data: ' + str(args.heldout_out))
    from jarvis import azr_dataset
    from jarvis.azr_sandbox import run_programs
    from jarvis.azr_tasks import signature, task_id
    counts = {split: dict(zip(('deduction', 'abduction', 'induction'), values))
              for split, values in (('train', args.train), ('validation', args.validation), ('heldout', args.heldout))}
    datasets, meta = azr_dataset.build(counts)
    dropped = {}
    for split, rows in datasets.items():
        induction = [r for r in rows if r['task']['mode'] == 'induction']
        programs = [{'id': r['id'], 'source': r['task']['reference_source'], 'cases': r['task']['visible'] + r['task']['hidden']}
                    for r in induction]
        verified = {}
        for start in range(0, len(programs), 60):
            verified.update(run_programs(BASE, programs[start:start + 60]))
        bad = {r['id'] for r in induction if not verified[r['id']]['passed']}
        dropped[split] = len(bad)
        datasets[split] = [r for r in rows if r['id'] not in bad]
        for row in datasets[split]:
            if row['task']['mode'] == 'induction':
                row['provenance']['sandbox_verified'] = True
    meta['answerability_dropped'] = dropped
    proposer_report = None
    if args.proposals:
        from jarvis.azr_proposer import Proposer, abduction_from
        proposer = Proposer(BASE, seed=7)
        reserved = {r['signature'] for split in ('heldout', 'validation') for r in datasets[split]}
        known = {r['id'] for split in datasets for r in datasets[split]}
        accepted, scored = [], []
        references = [datasets['train'][0]['task']]
        started = time.monotonic()
        for attempt in range(args.proposals):
            for mode in ('deduction', 'induction'):
                task = proposer.propose_deduction(references) if mode == 'deduction' else \
                    proposer.propose_induction(references, run_programs)
                if task is None:
                    continue
                tasks = [task] + ([abduction_from(task)] if mode == 'deduction' else [])
                for item in filter(None, tasks):
                    item.setdefault('seed', None)
                    identifier, skeleton = task_id(item), signature(item)
                    if identifier in known or skeleton in reserved:
                        proposer.rejections.append({'mode': item['mode'], 'reason': 'duplicate or held-out signature'})
                        continue
                    learn = proposer.learnability(item) if item['mode'] != 'induction' else {'solve_rate': None,
                                                                                            'r_propose': None}
                    scored.append({'mode': item['mode'], **learn})
                    known.add(identifier)
                    accepted.append({'schema_version': azr_dataset.SCHEMA_VERSION, 'id': identifier, 'split': 'train',
                                     'signature': skeleton, 'task': {k: v for k, v in item.items() if k != 'provenance'},
                                     'provenance': {**item.get('provenance', {}), 'learnability': learn,
                                                    'env_version': 1, 'oracle_version': 1}})
        datasets['train'].extend(accepted)
        proposer_report = {'attempts_per_mode': args.proposals, 'accepted': len(accepted), 'rejected': proposer.rejections,
                           'learnability': scored, 'minutes': round((time.monotonic() - started) / 60, 1),
                           'proposer': proposer.proposer, 'solver': proposer.solver, 'rollouts': proposer.rollouts}
        meta['proposer'] = proposer_report
    heldout = datasets.pop('heldout')
    manifest = azr_dataset.write(args.out, datasets, meta)
    args.heldout_out.parent.mkdir(parents=True, exist_ok=True)
    args.heldout_out.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in heldout), encoding='utf-8')
    summary = {'manifest': manifest['counts'], 'heldout': len(heldout), 'leakage': meta['leakage'],
               'answerability_dropped': dropped, 'proposer_accepted': proposer_report and proposer_report['accepted']}
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
