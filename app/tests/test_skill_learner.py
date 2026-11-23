"""Skill learner (jarvis/skill_learner.py): stage safely, understand, integrate, verify, report."""
import io
import json
from pathlib import Path
import tempfile
import zipfile

import pytest

from jarvis import skill_learner as sl

LONG = '\n\n'.join(f'## Step {n}\n\nDo part {n} carefully. ' + 'Detail sentence. ' * 40 for n in range(30))


def write(root, files):
    for name, text in files.items():
        path = Path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


SKILL = """---
name: PDF Tools
description: >
  Merge, split and extract text
  from PDF files.
---
# PDF tools

Use pypdf to merge files.
"""
SERVER = """from mcp.server.fastmcp import FastMCP
mcp = FastMCP("weather")

@mcp.tool()
def forecast(city: str) -> str:
    return "sunny"

if __name__ == "__main__":
    mcp.run()
"""


class FakeSkills:
    """SkillMemory's surface: catalog, errors, refresh, context (same validation of name/description/size)."""

    def __init__(self, custom):
        self.custom, self.catalog, self.skill_errors, self._guide_stamp = custom, [], [], None
        self.memory = type('M', (), {'enabled': True})()

    def refresh(self):
        import re
        self.catalog, self.skill_errors = [], []
        for path in sorted(Path(self.custom).glob('*/SKILL.md')):
            body = path.read_text(encoding='utf-8')
            name = re.search(r'(?m)^name: ([a-z0-9-]{1,64})$', body)
            desc = re.search(r'(?m)^description: (.+)$', body)
            if len(body.encode('utf-8')) > 8000 or not name or not desc or name[1] != path.parent.name:
                self.skill_errors.append(path.parent.name + ': invalid guide')
                continue
            self.catalog.append({'name': name[1], 'description': desc[1], 'origin': 'Custom'})

    def context(self, goal):
        words = set(goal.lower().split())
        hits = [c for c in self.catalog if words & set(c['description'].lower().split())]
        return {'skills': [{'name': c['name']} for c in hits[:2]]}


class Actions:
    def __init__(self, custom):
        self.skills = FakeSkills(custom)
        self.events = []
        self.memory = None

    def report(self, kind, value):
        self.events.append((kind, value))


@pytest.fixture
def home(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setattr(sl, 'STAGING', Path(folder) / 'staging')
        monkeypatch.setattr(sl, 'CUSTOM', Path(folder) / 'custom-skills')
        monkeypatch.setattr(sl, 'APP', Path(folder))
        yield Path(folder)


def test_archives_cannot_escape_and_secrets_are_never_copied(home):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        archive.writestr('pack/../../evil.txt', 'x')
        archive.writestr('pack/.env', 'KEY=1')
        archive.writestr('pack/tool/SKILL.md', SKILL)
    zip_path = home / 'pack.zip'
    zip_path.write_bytes(raw.getvalue())
    staged = sl.stage(zip_path, home / 'out')
    assert not (home / 'evil.txt').exists() and not list((home / 'out').rglob('.env'))
    assert Path(staged['root']).name == 'pack'  # one top folder becomes the root
    assert any('unsafe' in item for item in staged['left_out']) and any('.env' in item for item in staged['left_out'])


def test_front_matter_folded_description_and_condensing():
    meta, body = sl.frontmatter(SKILL)
    assert meta['name'] == 'PDF Tools' and meta['description'] == 'Merge, split and extract text from PDF files.'
    guide, condensed = sl.jarvis_guide('long-guide', 'A long one.', LONG)
    assert condensed and len(guide.encode('utf-8')) <= sl.GUIDE_LIMIT and 'ORIGINAL_SKILL.md' in guide


def test_inventory_finds_skills_servers_and_code_without_running_anything(home):
    write(home / 'src', {'skills/pdf/SKILL.md': SKILL, 'skills/pdf/scripts/merge.py': 'print(1)',
                         'server/weather.py': SERVER, 'lib/util.py': 'def f():\n    return 1\n'})
    found = sl.inventory(home / 'src')
    assert found['skills'] == ['skills/pdf/SKILL.md']
    assert [s['entry'] for s in found['servers']] == ['server/weather.py']  # not the skill's own script
    assert found['code_files'] == 2  # weather.py and util.py; the skill's script belongs to the skill


def test_skills_are_installed_converted_and_checked(home):
    write(home / 'pack', {'pdf/SKILL.md': SKILL, 'big/SKILL.md': '---\nname: big\ndescription: Big guide for '
                                                                  'reports.\n---\n' + LONG,
                          'pdf/scripts/merge.py': 'print(1)'})
    actions = Actions(home / 'custom-skills')
    report = sl.learn(actions, home / 'pack')
    names = {s['name']: s for s in report['skills']}
    assert set(names) == {'pdf-tools', 'big'}
    assert names['big']['condensed'] and (home / 'custom-skills/big/references/ORIGINAL_SKILL.md').is_file()
    assert (home / 'custom-skills/pdf-tools/scripts/merge.py').is_file()
    assert all(s['verified'] for s in report['skills'])
    assert 'Learned from pack: 2 skills' in report['summary']
    assert any(e[0] == 'media_card' and e[1]['phase'] == 'learned' for e in actions.events)
    again = sl.learn(actions, home / 'pack')  # same content: not integrated twice
    assert again.get('repeat') and len(list((home / 'custom-skills').iterdir())) == 2


def test_a_guide_that_does_not_load_is_removed_again(home, monkeypatch):
    write(home / 'pack', {'pdf/SKILL.md': SKILL})
    actions = Actions(home / 'custom-skills')
    monkeypatch.setattr(sl, 'verify_skill', lambda a, r: (False, 'invalid guide'))
    report = sl.learn(actions, home / 'pack')
    assert report['skills'] == [] and not (home / 'custom-skills/pdf-tools').exists()
    assert 'invalid guide' in report['problems'][0]


def test_servers_and_code_go_to_their_owners(home, monkeypatch):
    write(home / 'srv', {'weather.py': SERVER, 'requirements.txt': 'httpx>=0.27\n'})
    write(home / 'lib', {'README.md': '# Text tools\nConvert text.', 'tools/convert.py': 'def go(x):\n    return x\n'})
    calls = []
    monkeypatch.setattr(sl, 'integrate_server', lambda a, root, server, name, c: calls.append(name) or {
        'name': name, 'tools': [{'name': 'forecast', 'description': 'Weather forecast', 'arguments': {'city': 'string'}}],
        'packages': ['httpx>=0.27', 'mcp']})
    learned = []
    monkeypatch.setattr(sl, 'learn_code', lambda a, root, label, digest, c, origin=None: learned.append(label) or {
        'name': 'local/lib', 'purpose': 'Converts text.', 'use_when': 'converting text'})
    actions = Actions(home / 'custom-skills')
    server_report = sl.learn(actions, home / 'srv')
    code_report = sl.learn(actions, home / 'lib')
    assert calls == ['srv'] and 'forecast: Weather forecast' in server_report['summary']
    assert learned == ['lib'] and 'Converts text.' in code_report['summary']


def test_server_packages_include_the_sdk(home):
    write(home / 'srv', {'weather.py': SERVER, 'requirements.txt': 'httpx>=0.27\n-e .\n# note\n'})
    assert sl.server_packages(home / 'srv', home / 'srv/weather.py') == ['httpx>=0.27', 'mcp']


def test_only_real_paths_become_learning_tasks(home):
    (home / 'pack').mkdir()
    found = sl.parse_command(f'learn the skills in {home / "pack"}')
    assert found is not None and found.kind == 'task' and found.extra == 'skill_learn'
    assert sl.parse_command('learn the skills in D:\\does\\not\\exist') is None
    assert sl.parse_command('learn to cook pasta') is None


def test_a_declined_run_can_be_retried_and_a_retry_never_duplicates_skills(home, monkeypatch):
    write(home / 'pack', {'pdf/SKILL.md': SKILL, 'srv.py': SERVER})
    actions = Actions(home / 'custom-skills')

    def declined(*args):
        raise ValueError('Action cancelled; approval was not given.')
    monkeypatch.setattr(sl, 'integrate_server', declined)
    first = sl.learn(actions, home / 'pack')
    assert first['problems'] and [s['name'] for s in first['skills']] == ['pdf-tools']
    monkeypatch.setattr(sl, 'integrate_server', lambda a, root, server, name, c: {
        'name': name, 'kind': 'sdk', 'folder': '', 'packages': [], 'tools': [{'name': 't', 'description': 'Pack tool',
                                                                             'arguments': {}}]})
    second = sl.learn(actions, home / 'pack')
    assert not second.get('repeat') and second['servers'] and not second['problems']
    assert sorted(p.name for p in (home / 'custom-skills').iterdir()) == ['pack-tools', 'pdf-tools']  # no pdf-tools-2
    assert sl.learn(actions, home / 'pack').get('repeat')  # complete now: not done a third time


def test_a_new_server_gets_a_guide_that_names_the_exact_call(home, monkeypatch):
    write(home / 'srv', {'weather.py': SERVER})
    monkeypatch.setattr(sl, 'integrate_server', lambda a, root, server, name, c: {
        'name': name, 'kind': 'sdk', 'folder': '', 'packages': [],
        'tools': [{'name': 'forecast', 'description': 'Weather forecast for a city', 'arguments': {'city': 'string, required'}}]})
    report = sl.learn(Actions(home / 'custom-skills'), home / 'srv')
    guide = (home / 'custom-skills/srv-tools/SKILL.md').read_text(encoding='utf-8')
    assert 'tools: [mcp_call]' in guide and '"name": "forecast"' in guide and 'value `srv`' in guide
    assert report['skills'][0]['companion_of'] == 'srv' and report['skills'][0]['verified']


def test_forgetting_removes_what_a_run_installed_and_asks_first(home, monkeypatch):
    write(home / 'pack', {'pdf/SKILL.md': SKILL})
    actions = Actions(home / 'custom-skills')
    sl.learn(actions, home / 'pack')
    assert (home / 'custom-skills/pdf-tools').is_dir()
    asked = []
    actions._approve = lambda kind, detail, cancelled: asked.append(detail)
    assert sl.parse_command('forget the skills learned from pack').extra == 'skill_unlearn'
    answer = sl.unlearn(actions, 'pack', lambda: False)
    assert asked and 'pdf-tools' in asked[0] and not (home / 'custom-skills/pdf-tools').exists()
    assert 'skill pdf-tools' in answer and sl.parse_command('forget the skills learned from pack') is None
