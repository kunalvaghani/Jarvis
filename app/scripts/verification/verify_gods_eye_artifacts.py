"""Assert Prompt27 artifact/accounting consistency and relocated local doc links."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]
OUT = BASE/'artifacts/jarvis-audit'; MOD = OUT/'modules/27-gods-eye'
PRE = BASE/'.jarvis-runtime/jarvis-audit/module27-pre'


def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    changed, pairs, frozen = (read(MOD/n) for n in ('files-changed.json', 'source-hashes.json', 'full-start-source-hashes.json'))
    assert all(sha(BASE/r['path'])==r['sha256'] for r in changed)
    for row in pairs:
        old = PRE/('root-README.md' if row['path']=='../README.md' else row['path'].replace('/', '__'))
        assert sha(old)==row['before'] and sha(BASE/row['path'])==row['after']
    assert all(sha(BASE/p)==h for p,h in frozen.items())
    rows = [json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==len({r['id'] for r in rows})==1184
    module = [r for r in rows if r['id'].startswith('JRV-27-')]
    assert Counter(r['status'] for r in module)=={'PASS':20,'BLOCKED':12}
    assert not any(r['status']=='FAIL' for r in rows)
    nodes = list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    assert nodes and not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    assert {r['id'] for r in module}=={json.loads(s)['id'] for s in (MOD/'tests.jsonl').read_text().splitlines()}
    broken=[]; count=0
    docs=[BASE.parent/'README.md', BASE/'README.md', BASE/'docs/system-map.md', BASE/'docs/gods-eye.md', OUT/'final-report.md']+list(MOD.glob('*.md'))
    for doc in docs:
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\n]*?)\)', doc.read_text(encoding='utf-8')):
            target=raw.strip().strip('<>').split('#')[0]
            if not target or re.match(r'^[a-zA-Z][\w+.-]*:', target): continue
            count+=1
            if not (doc.parent/unquote(target)).exists(): broken.append(dict(doc=str(doc), target=target))
    assert not broken, broken
    generated = read(MOD/'generated-files.json')
    # This verifier creates its own receipt after all other artifacts pass.
    assert all((BASE/p).is_file() for p in generated if p!=(MOD/'artifact-verification.json').relative_to(BASE).as_posix())
    result=dict(date='2026-10-16 IST', changed_hashes=len(changed), preimage_pairs=len(pairs), frozen_files=len(frozen),
                full_source_changes=[], full_nodes=len(nodes), catalog_unique_ids=1184, module27={'PASS':20,'BLOCKED':12},
                relative_links_checked=count, broken_links=broken, generated_files_checked=len(generated),
                scope='Executed artifact consistency checks, not live globe acceptance')
    (MOD/'artifact-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__=='__main__': main()


