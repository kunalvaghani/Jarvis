"""Summarize real checks, preserving the non-green broad verdict and source binding."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]


def tests(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter('testcase'))
    failures = [c.get('classname') + '::' + c.get('name') for c in cases
                if c.find('failure') is not None or c.find('error') is not None]
    skips = [c for c in cases if c.find('skipped') is not None]
    return {'total': len(cases), 'passed': len(cases) - len(failures) - len(skips),
            'skipped': len(skips), 'failures': failures,
            'seconds': sum(float(s.get('time', '0')) for s in root.iter('testsuite')),
            'skip_reasons': dict(Counter(c.find('skipped').get('message', '')[:250] for c in skips))}


before = json.loads((HERE / 'before.json').read_text())
after = json.loads((HERE / 'after.json').read_text())
sources = json.loads((HERE / 'source-hashes.json').read_text())
changed = [name for name, digest in sources['source_hashes'].items()
           if hashlib.sha256((BASE / name).read_bytes()).hexdigest() != digest]
final = tests(HERE / 'full-suite-final.xml')
native = tests(HERE / 'demonstration-final.xml')
launcher = json.loads((HERE / 'launcher-check-final.log').read_text(encoding='utf-8-sig').strip())
result = {'date': '2026-10-21', 'scope': 'automated regression/readiness; live acceptance remains partial',
          'full_suite': final, 'affected_suite': tests(HERE / 'final-relevant.xml'),
          'native_fixture_module_after_readiness_fix': native,
          'single_complete_run_clean': not final['failures'],
          'release_acceptance': 'incomplete; live gates and complete-run fixture follow-up remain',
          'test_source_hashes': {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest()
                                for name in ('tests/test_unified_intelligence.py', 'tests/test_phase05_escalation_demonstration.py')},
          'production_files_bound': len(sources['source_hashes']), 'source_mismatches': changed,
          'identical_discovery_queries': before['selections'] == after['selections'],
          'search_p50_reduction_percent': round(100 * (1 - after['timings'][0]['p50_ms'] / before['timings'][0]['p50_ms']), 2),
          'launcher_status': launcher['status'],
          'live_local_probe': json.loads((HERE / 'live-inference.json').read_text())}
(HERE / 'final-summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in {'full_suite', 'affected_suite', 'live_local_probe', 'native_fixture_module_after_readiness_fix'}}))
print(json.dumps({k: v for k, v in final.items() if k != 'skip_reasons'}))
assert not changed and not native['failures'] and result['identical_discovery_queries']
