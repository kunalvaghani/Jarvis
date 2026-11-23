"""Exact test-ID comparison with the historical 5,456-pass checkpoint."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT/'app/.jarvis-runtime/lab-validation'


def main():
    old=json.loads((PRIVATE/'ah-consolidated-full-2026-11-05.json').read_text(encoding='utf-8'))
    new=json.loads((PRIVATE/'scenario-a-full-final-2026-11-06.json').read_text(encoding='utf-8'))
    before={r['test']:r['outcome'] for r in old['reports'] if r['phase']=='call'}
    after={r['test']:r['outcome'] for r in new['reports'] if r['phase']=='call'}
    passes={k for k,v in before.items() if v=='passed'}
    missing=sorted(passes-after.keys())
    failed=sorted(k for k in passes if after.get(k)=='failed')
    skipped_ids={r['test'] for r in new['reports'] if r['outcome']=='skipped'}
    skipped=sorted(passes & skipped_ids)
    result={'date':'2026-11-06','baseline_passed':old['passed'],'current_passed':new['passed'],
        'baseline_skipped':old['skipped'],'current_skipped':new['skipped'],
        'previous_passes_missing':missing,'previous_passes_now_failed':failed,'previous_passes_now_skipped':skipped,
        'new_passed_test_ids':sorted(k for k,v in after.items() if v=='passed' and k not in before),
        'source_sha256':new['source_sha256_after'],'skips_are_unexecuted':True,
        'scope':'Regression only, not real asset acquisition, full A, all A-H or physical validation'}
    (ROOT/'docs/lab/evidence/scenario-a-coverage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('baseline_passed','current_passed','previous_passes_missing','previous_passes_now_failed','previous_passes_now_skipped')}))
    return int(bool(missing or failed or skipped))


if __name__=='__main__':raise SystemExit(main())
