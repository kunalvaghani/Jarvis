"""Owned workbook/readback, fake-send and fake-hook journals. No live E2E claim."""
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
from types import ModuleType
from unittest.mock import Mock

OUT = Path(__file__).resolve().parent
APP = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')
os.chdir(APP)
sys.path.insert(0, str(APP))
BASE = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
from jarvis import app_adapters, demonstration
from tests import test_phase03_living_skills as living
from tests import test_phase08_integration as flows
INSTALL = Path('D:/Kunals GitHub Repo/Jarvis/app')
app_adapters.APP = INSTALL
living.SKILLS = INSTALL / '.venv-skills/Scripts/python.exe'

journals = []
def run(identifier, label, function):
    calls = []
    def profile(frame, event, arg):
        module = frame.f_globals.get('__name__', '')
        if event == 'call' and module.startswith('jarvis.'):
            name = module + '.' + frame.f_code.co_name
            if not calls or name != calls[-1]: calls.append(name)
    start = time.perf_counter()
    sys.setprofile(profile)
    try:
        observed = function()
    finally:
        sys.setprofile(None)
    journals.append({'id': identifier, 'input': label, 'classification': 'owned fixture / simulated boundaries',
        'actual_python_component_calls': calls, 'observed_postconditions': observed,
        'elapsed_seconds': time.perf_counter() - start, 'status': 'PASS'})

with tempfile.TemporaryDirectory(prefix='jarvis-p37-followup-') as raw:
    root = Path(raw)
    def workbook_journey():
        folder = root / 'workbook'; folder.mkdir()
        env = living.env.__wrapped__(folder)
        flows.test_P08_flow_A_api_first_capture_degrade_fix_lessons_and_bounded_diagnosis(env, folder)
        readback = json.loads(subprocess.check_output([str(living.SKILLS), '-c',
            "import openpyxl,json,sys;b=openpyxl.load_workbook(sys.argv[1],data_only=False);s=b['Budget'];print(json.dumps({'A1':s['A1'].value,'A2':s['A2'].value,'sheets':b.sheetnames}))",
            str(env.docs / 'renamed.xlsx')], text=True))
        assert readback['A1'] == 9 and readback['A2'] == '=A1*2'
        from jarvis.reasoning_bank import ReasoningBank
        kinds = sorted({row['kind'] for row in ReasoningBank(folder, embedder=lambda *a: None).items()})
        return {'independent_worker_readback': readback, 'stored_lesson_kinds': kinds,
            'api_strategy': 'xlsx.openpyxl (asserted in actual flow)', 'captured_and_fixed_skill_assertions': True,
            'limitations': 'Model author and consent callbacks simulated; no Excel GUI, voice, macro/signature or outcome-improvement claim.'}
    run('P37-E5AF-XLSX', 'Prefer API; edit workbook; capture provisional skill; degrade and FIX; retrieve lesson kinds', workbook_journey)

    def send_journey():
        from jarvis.actions import Actions
        from jarvis.commands import Command
        from jarvis.task_state import TaskState
        events, calls = [], []
        actions = Actions({'files_root': 'files', 'apps': {}}, root / 'send', lambda *a: events.append(a))
        def uncertain(goal, cancelled):
            calls.append('mock send')
            actions.task_state.checkpoint('uncertain_external_write', action='send', target='owned-mock')
            return 'Finished. Message sent.'
        actions.brain.run = uncertain
        try:
            actions.start(); actions.submit(Command('task', 'send a synthetic fixture message')); actions.queue.join()
            current = actions.task_state.snapshot()
            restored = TaskState(root / 'send')
            blocker = restored.resume_blocker(restored.snapshot())
            assert current['status'] == 'paused' and ('spoken_reply', current['result']) in events
            assert blocker and len(calls) == 1
            return {'durable_status': current['status'], 'returned_speech_event': current['result'],
                'restart_blocker': blocker, 'mock_send_attempts': len(calls), 'real_sends': 0,
                'limitations': 'Brain output simulated; speech event not speaker playback; no real service crash.'}
        finally: actions.close()
    run('P37-E5AF-SEND', 'Queued mock send becomes uncertain; finish; restart and inspect', send_journey)

    def cloud_journey():
        folder = root / 'cloud'; folder.mkdir()
        flows.test_P08_D8_1_consult_requires_the_approval_card_and_treats_advice_as_untrusted(folder)
        return {'assertions_passed': ['three distinct local failures', 'denied consent zero sends',
            'approved generic payload one recording-fake request', 'actions_taken zero', 'repeat consult no second send'],
            'real_cloud_requests': 0, 'limitations': 'Caller-declared synthetic provenance remains an open semantic privacy boundary.'}
    run('P37-E5AF-CLOUD', 'Three failures; deny then approve abstract advisory; repeat', cloud_journey)

(OUT / 'workflow-journals.jsonl').write_text('\n'.join(json.dumps(row) for row in journals) + '\n', encoding='utf-8')

# Fixed source/fixture comparison: observer exception cleanup, no physical hook.
source = subprocess.check_output(['git', 'show', BASE + ':app/jarvis/demonstration.py'], cwd=APP).decode('utf-8')
old = ModuleType('jarvis._prompt37_baseline')
exec(compile(source, '<pinned-demonstration>', 'exec'), old.__dict__)
rng = random.Random(37)
rows = []
with tempfile.TemporaryDirectory(prefix='jarvis-p37-followup-bench-') as raw:
    root = Path(raw)
    for pair in range(30):
        order = [('pinned', old), ('current', demonstration)]; rng.shuffle(order)
        for revision, module in order:
            hook = Mock()
            session = module.DemonstrationSession(root / f'{pair}-{revision}', lambda *a: None, hook_factory=lambda q: hook)
            session.state['status'] = 'recording'; session.start_hook()
            session.events.put((1, 2, 513, 0, 0))
            session.process = Mock(side_effect=RuntimeError('synthetic observation failure'))
            start = time.perf_counter_ns()
            try: session.pump()
            except RuntimeError: pass
            elapsed = time.perf_counter_ns() - start
            clean = session.hook is None and hook.stop.call_count == 1
            persisted = json.loads(session.path.read_text())['status'] if session.path.exists() else 'absent'
            rows.append({'pair': pair, 'revision': revision, 'elapsed_ns': elapsed,
                'cleanup_before_harness': clean, 'persisted_status': persisted})
            if session.hook is not None: session.stop('failed')  # baseline fixture cleanup, outside timing
with (OUT / 'benchmarks.csv').open('w', newline='', encoding='utf-8') as file:
    writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
(OUT / 'benchmark-provenance.json').write_text(json.dumps({'base_sha': BASE, 'pinned_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
    'current_source_sha256': hashlib.sha256((APP / 'jarvis/demonstration.py').read_bytes()).hexdigest(),
    'seed': 37, 'pairs': 30, 'fixture': 'one queued fake event; observer RuntimeError; fake owned hook',
    'timing_scope': 'pump call including current durable cleanup; no E2E latency or performance improvement claim',
    'baseline_cleanup_successes': sum(r['cleanup_before_harness'] for r in rows if r['revision'] == 'pinned'),
    'current_cleanup_successes': sum(r['cleanup_before_harness'] for r in rows if r['revision'] == 'current')}, indent=2), encoding='utf-8')
print('Three owned/simulated journals and 30 pinned/current cleanup pairs written.')
