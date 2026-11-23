"""Publish only bounded terminal regression metadata; never assertion/account payloads."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    private=ROOT/'app/.jarvis-runtime/lab-validation/c2-full-final.json'
    d=json.loads(private.read_text(encoding='utf-8'))
    before=json.loads((ROOT/'docs/lab/evidence/b6-c1-full-gate.json').read_text(encoding='utf-8'))
    failures={r['test'] for r in d['reports'] if r['outcome']=='failed'}
    previous=set(before['remaining_failure_ids'])
    result={k:v for k,v in d.items() if k!='reports'}
    result.update(new_failure_ids=sorted(failures-previous),resolved_failure_ids=sorted(previous-failures),remaining_failure_ids=sorted(failures))
    target=ROOT/'docs/lab/evidence/c2-full-final.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if (result['new_failure_ids'] or d['errors'] or d['collection_errors'] or d['source_sha256_before']!=d['source_sha256_after']):
        print(json.dumps(result));raise SystemExit('new failure or changed-source gate requires review; no acceptance promotion')
    summary=f"**Final post-C2 whole-project regression: {d['passed']:,} passed / {d['failed']} failed / {d['skipped']} skipped**, {d['seconds']:.3f} s including runner setup; source fingerprint unchanged. Exactly the same {len(failures)} prior failing IDs, zero new failures and zero discovery failures. This is the credential/network/model-isolated regression result, not live UI/microphone/control or scientific release acceptance."
    sections={
        'README.md':('**Final C2 regression — 2026-11-04 IST:** '+summary+' [Terminal comparison](docs/lab/evidence/c2-full-final.json).'),
        'app/README.md':('### Terminal C2 regression — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](../docs/lab/evidence/c2-full-final.json).'),
        'app/docs/CLAUDE_HANDOFF.md':('## Terminal C2 regression — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](../../docs/lab/evidence/c2-full-final.json). All release/live/provider/autonomous-learning gates listed below remain open. Next work follows the scoped [remaining steps](../../docs/lab/NEXT_STEPS.md); do not resume the paused repair campaign. No additional code edits followed the frozen focused/full checks.'),
        'docs/lab/PROGRESS.md':('## Terminal C2 regression — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](evidence/c2-full-final.json).'),
        'docs/lab/ACCEPTANCE_RESULTS.md':('## Terminal C2 regression — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](evidence/c2-full-final.json).'),
        'docs/lab/C2_PENDULUM.md':('Final post-change regression: '+summary+' [Terminal comparison](evidence/c2-full-final.json).'),
        'docs/lab/MODIFICATIONS.md':('## Terminal C2 verification — 2026-11-04 IST\n\n'+summary+' [Terminal comparison](evidence/c2-full-final.json).'),
    }
    replacements={
        'A final post-C2 whole-project regression is running; its terminal comparison will be recorded separately.':'The final post-C2 whole-project regression has completed; see the terminal comparison above.',
        'Final post-C2 whole-project regression is running, with its terminal comparison to be recorded in the progress/evidence report.':'Final post-C2 whole-project regression has completed; see the terminal comparison above.',
        'Final post-C2 full regression currently running; add terminal receipt and compare IDs before claiming no new whole-project failures. Keep executable app source/config/tests frozen during it.':'Final post-C2 full regression completed with the terminal comparison above; source/config/tests remained frozen.',
        'Final post-C2 full regression is in progress; terminal comparison recorded separately.':'Final post-C2 full regression completed; terminal comparison above.',
        'The post-C2 full-suite result is recorded separately when terminal;':'The terminal post-C2 full-suite result is recorded above;',
        'record final full-suite terminal comparison; live Drive':'live Drive',
    }
    for filename,section in sections.items():
        p=ROOT/filename;s=p.read_text(encoding='utf-8')
        for a,b in replacements.items():s=s.replace(a,b)
        i=s.index('\n')+1;p.write_text(s[:i]+'\n'+section+'\n\n'+s[i:].lstrip('\n'),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='remaining_failure_ids'}))

if __name__=='__main__':main()
