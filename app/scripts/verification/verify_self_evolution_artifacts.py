"""Verify Prompt20 evidence, hashes, complete catalog accounting and README/report links."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];OUT=BASE/'artifacts/jarvis-audit'
MOD=OUT/'modules/20-self-evolution';PRE=BASE/'.jarvis-runtime/jarvis-audit/module20-pre'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    changed=read(MOD/'files-changed.json');pairs=read(MOD/'source-hashes.json');frozen=read(MOD/'full-start-source-hashes.json')
    assert all(sha(BASE/r['path'])==r['sha256'] for r in changed)
    for r in pairs:
        name='root-README.md' if r['path']=='../README.md' else r['path'].replace('/','__')
        assert sha(PRE/name)==r['before'] and sha(BASE/r['path'])==r['after']
    assert all(sha(BASE/p)==h for p,h in frozen.items())
    rows=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==len({r['id'] for r in rows})==1184
    module=[r for r in rows if r['id'].startswith('JRV-20-')]
    assert len(module)==32 and sum(r['status']=='PASS' for r in module)==28
    assert {r['id'] for r in module if r['status']=='BLOCKED'}=={'JRV-20-002','JRV-20-003','JRV-20-006','JRV-20-011'}
    assert not any(r['status']=='FAIL' for r in rows)
    assert {r['id'] for r in module}=={json.loads(s)['id'] for s in (MOD/'tests.jsonl').read_text(encoding='utf-8').splitlines()}
    nodes=list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    assert nodes and not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    docs=[BASE.parent/'README.md',BASE/'README.md',BASE/'docs/system-map.md',BASE/'docs/self-evolution.md',BASE/'docs/anticipation.md',OUT/'final-report.md']+list(MOD.glob('*.md'))
    count=0;broken=[]
    for doc in docs:
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\n]*?)\)',doc.read_text(encoding='utf-8')):
            target=raw.strip().strip('<>').split('#')[0]
            if not target or re.match(r'^[a-zA-Z][\w+.-]*:',target):continue
            count+=1
            if not (doc.parent/unquote(target)).exists():broken.append({'doc':doc.relative_to(BASE.parent).as_posix(),'target':target})
    assert not broken,broken
    result={'date':'2026-10-16 IST','file_hashes_verified':len(changed),'preimage_pairs_verified':len(pairs),
      'frozen_runtime_test_files_verified':len(frozen),'source_changes_during_final_full_run':[],
      'catalog_unique_ids':1184,'module20_catalog_passed':28,'module20_blocked':4,'full_nodes':len(nodes),
      'full_skipped':sum(n.find('skipped') is not None for n in nodes),'relative_links_checked':count,'broken_links':broken,
      'scope':'Executed hash/artifact/accounting assertions; not live production acceptance.'}
    (MOD/'artifact-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
