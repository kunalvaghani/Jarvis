import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

out = Path(__file__).resolve().parent
links = []
for path in out.glob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if '://' not in link:
            assert (path.parent / link.split('#')[0]).exists(), (path, link)
            links.append(link)
skips = [{'id': case.get('classname') + '::' + case.get('name'),
          'reason': case.find('skipped').get('message')}
         for case in ET.parse(out / 'neighbors.xml').findall('.//testcase') if case.find('skipped') is not None]
source = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7')
assert subprocess.check_output(['git', 'diff', '--name-only'], cwd=source, text=True) == ''
subprocess.run(['git', 'diff', '--check'], cwd=out.parents[5], check=True)
report = json.loads((out / 'validation.json').read_text(encoding='utf-8'))
report.update({'packet_links_checked': len(links), 'tracked_source_clean': True, 'explicit_skips': skips})
(out / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
