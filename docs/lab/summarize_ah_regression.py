"""Publish counts/identifiers only, retaining failures, skips and source provenance.

This never certifies autonomous science or live control from pytest results.
"""
import argparse
import json
from pathlib import Path
from run_checks import source_fingerprint

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT/'app/.jarvis-runtime/lab-validation'
PUBLIC=ROOT/'docs/lab/evidence'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--typecheck',default='')
    args=parser.parse_args()
    for value in (args.receipt,args.output):
        if Path(value).name!=value or not value.endswith('.json'):raise ValueError('one JSON filename required')
    if args.typecheck and Path(args.typecheck).name!=args.typecheck:raise ValueError('one typecheck receipt filename required')
    data=json.loads((PRIVATE/args.receipt).read_text(encoding='utf-8'))
    baseline=json.loads((PUBLIC/'e-full-final.json').read_text(encoding='utf-8'))
    old=set(baseline['remaining_failure_ids'])
    call={r['test']:r['outcome'] for r in data['reports'] if r['phase']=='call'}
    fixed=sorted(identity for identity in old if call.get(identity)=='passed')
    remaining=sorted(old-set(fixed))
    failures=sorted({r['test'] for r in data['reports'] if r['outcome']=='failed'})
    current=source_fingerprint()
    stable=data['source_sha256_before']==data['source_sha256_after']
    matches=data['source_sha256_after']==current
    typecheck=None
    if args.typecheck:
        typecheck=json.loads((PRIVATE/args.typecheck).read_text(encoding='utf-8'))
    passed=(data['exit_code']==0 and data['failed']==0 and data['errors']==0
            and not data['collection_errors'] and not remaining and stable and matches)
    result={k:data[k] for k in ('date_local','passed','failed','skipped','errors','exit_code',
                              'seconds','source_sha256_before','source_sha256_after','isolation')}
    result.update({'source_stable':stable,'matches_current_source':matches,
        'current_source_sha256':current,'original_failure_count':len(old),'resolved_original_ids':fixed,
        'remaining_original_ids':remaining,'current_failure_ids':failures,
        'failure_diagnostics':[r for r in data['reports'] if r['outcome']=='failed'],
        'regression_gate_passed':passed,'skips_are_unexecuted':True,
        'typecheck':typecheck,'all_eight_autonomous_scenarios_passed':False,
        'scope':'Guarded project regression only; no live A-H, PC/browser latency, microphone, physical or release acceptance.',
        'private_receipt':'app/.jarvis-runtime/lab-validation/'+args.receipt})
    (PUBLIC/args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','failed','skipped','errors','source_stable',
        'matches_current_source','original_failure_count','remaining_original_ids','regression_gate_passed')}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
