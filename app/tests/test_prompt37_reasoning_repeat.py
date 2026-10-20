"""JRV-37-017 seam journey: real workbook/SQLite/Brain wire, simulated planner.

The planner deliberately ignores lessons. Retrieval is not claimed as improvement.
No network/model/voice/native UI is used; the skills interpreter must already exist.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from jarvis.brain import BrainClient
from jarvis.learning_memory import LearningMemory
from jarvis.tools import ToolRegistry


@pytest.mark.parametrize('enabled', [False, True], ids=['memory-off', 'memory-on'])
def test_JRV_37_017_retrieval_is_not_verified_improvement(tmp_path, monkeypatch, enabled):
    from jarvis import app_adapters, local_embeddings
    app = Path(__file__).resolve().parents[1]
    install = Path(os.environ.get('JARVIS_E2E_DEPENDENCY_APP', str(app)))
    skills = install / '.venv-skills/Scripts/python.exe'
    if not skills.is_file():
        pytest.skip('Existing .venv-skills required; no installation attempted.')
    monkeypatch.setattr(app_adapters, 'APP', install)
    monkeypatch.setattr(local_embeddings, 'embed', lambda *a, **k: None)
    docs = tmp_path / 'docs'
    docs.mkdir()
    workbook = docs / 'budget.xlsx'
    subprocess.run([str(skills), '-c',
        "import openpyxl,sys;b=openpyxl.Workbook();s=b.active;s.title='Data';"
        "s['A1']=1;s['A2']='=A1*2';b.save(sys.argv[1])", str(workbook)],
        check=True, capture_output=True, timeout=30)
    initial_hash = hashlib.sha256(workbook.read_bytes()).hexdigest()
    approvals, requests, rows = [], [], []
    client = BrainClient(tmp_path, {'harness': {'enabled': False}, 'hermes': {'enabled': False}})
    actions = SimpleNamespace(base=tmp_path, config={}, allowed_tools={'office_xlsx'}, skills=None,
        task_state=None, memory=None, brain=SimpleNamespace(client=client), report=lambda *a: None,
        _task_folder=lambda name, cancelled: str(docs),
        _approve=lambda kind, detail, cancelled: approvals.append(kind))
    learning = LearningMemory(actions, {'reasoning_bank': {'enabled': enabled}}).attach()
    registry = ToolRegistry(actions)
    # Recording fake replaces only worker transport. BrainClient request locking,
    # lesson injection, bounded JSON serialization and response parsing stay real.
    class Wire(io.StringIO):
        def flush(self):
            request = json.loads(self.getvalue().splitlines()[-1])
            requests.append(request)
            step = {'action': 'office_xlsx', 'value': 'budget.xlsx', 'folder': 'docs',
                    'content': json.dumps({'operation': 'write', 'sheet': 'Wrong', 'cells': {'A1': 5}})}
            client.responses.put(json.dumps({'result': {'steps': [step]}}))
    client.process = SimpleNamespace(poll=lambda: None, stdin=Wire())
    client.responses = queue.Queue()
    goal = 'office xlsx write workbook cell with independent readback'
    for attempt in range(2):
        start = time.perf_counter()
        plan = client.request('plan', lambda: False, goal=goal)
        step = plan['steps'][0]
        with pytest.raises(ValueError, match='Unknown worksheet') as failure:
            registry.execute(step, lambda: False)
        readback = json.loads(subprocess.check_output([str(skills), '-c',
            "import openpyxl,json,sys;b=openpyxl.load_workbook(sys.argv[1],data_only=False);"
            "s=b['Data'];print(json.dumps({'A1':s['A1'].value,'A2':s['A2'].value,'sheets':b.sheetnames}))",
            str(workbook)], text=True, timeout=30))
        assert readback == {'A1': 1, 'A2': '=A1*2', 'sheets': ['Data']}
        assert hashlib.sha256(workbook.read_bytes()).hexdigest() == initial_hash
        learned = learning.learn_from_task({'task_id': f'owned-repeat-{attempt}', 'goal': goal,
            'status': 'failed', 'conditions': {'app_name': 'workbook'},
            'failures': [{'action': step['action'], 'value': 'workbook', 'reason': str(failure.value)}]})
        rows.append({'attempt': attempt + 1, 'verified_goal_success': False,
            'readback': readback, 'workbook_bytes_unchanged': True, 'learn_result': learned,
            'lesson_count_at_transport': len(requests[-1].get('reasoning_lessons', [])),
            'elapsed_seconds': time.perf_counter() - start})
    assert rows[0]['lesson_count_at_transport'] == 0
    assert rows[1]['lesson_count_at_transport'] == int(enabled)
    if enabled:
        lesson = requests[1]['reasoning_lessons'][0]
        assert lesson['kind'] == 'anti_pattern' and 'Unknown worksheet' in lesson['content']
        assert len(lesson['content']) <= 500 and lesson['trust'] == 'provisional'
        with learning.bank.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM trajectories WHERE outcome='failure'").fetchone()[0] == 2
        assert {item['kind'] for item in learning.bank.items()} == {'anti_pattern'}
    assert approvals == []  # invalid worksheet rejected before write approval
    assert not any(row['verified_goal_success'] for row in rows)
    evidence = os.environ.get('JARVIS_E2E_EVIDENCE_DIR')
    if evidence:
        out = Path(evidence)
        out.mkdir(parents=True, exist_ok=True)
        (out / f'reasoning-repeat-{enabled}.json').write_text(json.dumps({
            'case': 'JRV-37-017', 'memory_enabled': enabled,
            'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=app, text=True).strip(),
            'classification': 'real workbook worker, ToolRegistry, SQLite, LearningMemory, BrainClient wire; fake planner ignores hints',
            'rows': rows, 'outcome_improved': False, 'real_model_requests': 0,
            'scope_limit': 'Task outcome/trajectory supplied by harness; full Actions/Brain orchestration and real planner remain untested.'},
            indent=2), encoding='utf-8')
    # Fake transport has no child process to kill; release its owned buffer only.
    client.process.stdin.close()
    client.process = None
