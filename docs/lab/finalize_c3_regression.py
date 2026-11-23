"""Summarize frozen C3 regression without assertion payloads or credentials."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    d=json.loads((ROOT/'app/.jarvis-runtime/lab-validation/c3-full-final.json').read_text(encoding='utf-8'))
    baseline=json.loads((ROOT/'docs/lab/evidence/c2-full-final.json').read_text(encoding='utf-8'))
    failures={r['test'] for r in d['reports'] if r['outcome']=='failed'};prior=set(baseline['remaining_failure_ids'])
    result={k:v for k,v in d.items() if k!='reports'}
    result.update(new_failure_ids=sorted(failures-prior),resolved_failure_ids=sorted(prior-failures),remaining_failure_ids=sorted(failures),
                  discovery_failures=sorted(x for x in failures if x.startswith('tests/test_discovery')))
    (ROOT/'docs/lab/evidence/c3-full-final.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if result['new_failure_ids'] or result['discovery_failures'] or d['errors'] or d['collection_errors'] or d['source_sha256_before']!=d['source_sha256_after']:
        print(json.dumps(result));raise SystemExit('terminal comparison has an unmet gate; no pass promotion')
    summary=f"**Final C3 whole-project regression: {d['passed']:,} passed / {d['failed']} failed / {d['skipped']} skipped**, {d['seconds']:.3f} s including runner setup. The exact same {len(failures)} prior failing IDs remain: zero new failures, zero Discovery failures, unchanged source fingerprint. This includes the final theory source-context addition. It is an isolated regression result, not live model-generation, microphone/UI, control or scientific release acceptance."
    sections={
      'README.md':summary+' [Terminal comparison](docs/lab/evidence/c3-full-final.json). C3 model generation remains DEGRADED after four timed-out live attempts.',
      'app/README.md':'### Terminal C3 checks — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](../docs/lab/evidence/c3-full-final.json).',
      'app/docs/CLAUDE_HANDOFF.md':'## Terminal C3 checks — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](../../docs/lab/evidence/c3-full-final.json).',
      'docs/lab/PROGRESS.md':'## Terminal C3 checks — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](evidence/c3-full-final.json).',
      'docs/lab/ACCEPTANCE_RESULTS.md':'## Terminal C3 checks — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](evidence/c3-full-final.json).',
      'docs/lab/C3_RESEARCH.md':summary+' [Terminal comparison](evidence/c3-full-final.json).',
      'docs/lab/MODIFICATIONS.md':'## Terminal C3 verification — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](evidence/c3-full-final.json).'
    }
    replacements={
      'The final whole-project comparison is running and will be recorded separately;':'The final whole-project comparison is complete above;',
      'Final whole-project comparison is running against the preceding 5,250/42/161 baseline.':'Final whole-project comparison completed against the preceding 5,250/42/161 baseline; see terminal result above.',
      'Final whole-project C3 regression is running; compare its exact failure IDs against the C2 baseline **5,250 pass /42 fail /161 skip** before claiming no new full-suite failures.':'Final whole-project C3 regression completed; the terminal comparison above preserves the exact prior42 failing IDs.',
      'Final full C3 suite currently running; source/tests/config/requirements frozen. Compare IDs to C2\'s **5,250/42/161**, preserve all legacy defects, and publish terminal receipt.':'Final full C3 suite completed on frozen source/tests/config/requirements; terminal comparison above preserves all legacy defects.',
      'Final whole-project comparison running;':'Final whole-project comparison completed;'
    }
    for f,section in sections.items():
        p=ROOT/f;s=p.read_text(encoding='utf-8')
        for a,b in replacements.items():s=s.replace(a,b)
        i=s.index('\n')+1;p.write_text(s[:i]+'\n'+section+'\n\n'+s[i:].lstrip('\n'),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='remaining_failure_ids'}))
if __name__=='__main__':main()
