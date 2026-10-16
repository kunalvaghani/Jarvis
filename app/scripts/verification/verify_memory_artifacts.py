"""Validate Prompt16 artifact hashes, exact ledger and local report links."""
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'artifacts/jarvis-audit'
MOD=OUT/'modules/16-memory'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module16-pre'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    changed=read(MOD/'files-changed.json')
    assert all(sha(BASE/r['path'])==r['sha256'] for r in changed)
    pairs=read(MOD/'source-hashes.json')
    for row in pairs:
        name='root-README.md' if row['path']=='../README.md' else row['path'].replace('/','__')
        assert sha(PRE/name)==row['before'] and sha(BASE/row['path'])==row['after']
    frozen=read(MOD/'full-start-source-hashes.json')
    assert all(sha(BASE/p)==h for p,h in frozen.items())
    rows=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==len({r['id'] for r in rows})==1184
    module=[r for r in rows if r['id'].startswith('JRV-16-')]
    assert len(module)==32 and sum(r['status']=='PASS' for r in module)==28
    assert {r['id'] for r in module if r['status']=='BLOCKED'}=={'JRV-16-004','JRV-16-006','JRV-16-011','JRV-16-032'}
    assert not any(r['status']=='FAIL' for r in rows)
    nodes=list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    assert not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    docs=[BASE.parent/'README.md',BASE/'README.md',BASE/'docs/system-map.md',BASE/'docs/memory-apis-alerts.md',OUT/'final-report.md']+list(MOD.glob('*.md'))
    checked=0;broken=[]
    for doc in docs:
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\n]*?)\)',doc.read_text(encoding='utf-8')):
            raw=raw.strip().strip('<>');target=raw.split('#')[0]
            if not target or re.match(r'^[a-zA-Z][\w+.-]*:',target):continue
            checked+=1
            if not (doc.parent/urllib.parse.unquote(target)).exists():broken.append({'doc':str(doc),'target':target})
    assert not broken,broken
    result={'date':'2026-10-16 IST','file_hashes_verified':len(changed),'preimage_pairs_verified':len(pairs),
        'frozen_source_test_files_verified':len(frozen),'source_changes_during_final_full_run':[],
        'catalog_unique_ids':1184,'module16_passed':28,'module16_blocked':4,
        'full_nodes':len(nodes),'full_skipped':sum(n.find('skipped') is not None for n in nodes),
        'relative_links_checked':checked,'broken_links':broken,'scope':'Artifact/hash/accounting assertions, not additional live feature acceptance.'}
    (MOD/'artifact-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
