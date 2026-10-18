"""Phase 5 measurements and privacy trace.

The cloud provider is a recording fake (MOCK): no real Groq request is made. Everything
else is real: the privacy gate, the AST screen, Docker sandbox verification of advice
code, the failure router, UI Automation capture and structured replay on the disposable
Win32 fixture window. The trace lists every adversarial case, why it was refused and
whether anything would have been sent.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import uuid

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

GENERIC = {'category': 'algorithm', 'provenance': 'synthetic',
           'statement': 'Given a list of integers, return the length of the longest strictly increasing subsequence.',
           'question': 'What is an efficient approach, and can you give one pure function implementing it?',
           'constraints': 'n up to 100000', 'examples': [{'input': [[10, 9, 2, 5, 3, 7, 101, 18]], 'output': 4},
                                                         {'input': [[0, 1, 0, 3, 2, 3]], 'output': 4}]}
ADVERSARIAL = {
    'windows_path': {'statement': 'Sort the rows in C:\\Users\\someone\\Documents\\budget.xlsx by amount and total groups.'},
    'fake_credential': {'statement': 'Use api_key=sk-FAKE0123456789abcdefghij to rank items by score and return the top ones.'},
    'internal_module_name': {'statement': 'Improve how skill_memory ranks guides when the planner asks for relevant entries.'},
    'source_snippet': {'statement': 'def rank(items):\n    return sorted(items)\nfor x in data:\n    total = x + 1\nreturn total'},
    'log_excerpt': {'statement': 'Traceback (most recent call last): File "a.py", line 3 -- fix the ordering of my tasks.'},
    'email_address': {'question': 'Email the answer to someone@example.com and also read my emails from yesterday please.'},
    'private_url': {'statement': 'Optimise the schedule stored at https://internal.example/plan for the next quarter.'},
    'personal_context': {'statement': 'Using my calendar and my private messages, plan the best order for my errands tomorrow.'},
    'unclassified_provenance': {'provenance': 'user_project'},
}


class RecordingAdapter:
    def __init__(self, reply):
        self.reply, self.sent = reply, []

    def ready(self, wait_seconds=0):
        return True

    def complete(self, messages, output, **kwargs):
        self.sent.append(messages)
        return {'content': self.reply}


class Guardian:
    def snapshot(self, fresh=False):
        return {'state': 'HEALTHY'}


def summary(values):
    values = sorted(values)
    return {'n': len(values), 'p50_ms': round(statistics.median(values), 2), 'max_ms': round(values[-1], 2)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    out = Path(parser.parse_args(argv).out)
    if out.exists():
        raise SystemExit('Refusing to overwrite preserved measurements: ' + str(out))
    from jarvis.cloud_architect import CloudArchitect, privacy_gate
    from jarvis.deliberation import FailureRouter
    options = {'enabled': True, 'groq': {'enabled': True, 'account_plan': 'free', 'free_tier_confirmed': True,
                                         'dedicated_quota_confirmed': True}}
    failures = [{'strategy': s, 'verified_failure': True, 'cause': 'test_failed'} for s in ('a', 'b', 'c')]
    result = {'schema_version': 1, 'measured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'provider': 'MOCK recording adapter (no real cloud request)'}
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        trace, gate_ms = [], []
        for name, change in ADVERSARIAL.items():
            agent = CloudArchitect(base, options, RecordingAdapter('advice'), Guardian())
            agent.consent.grant('request:bench', 5)
            started = time.perf_counter()
            decision = agent.consult('p-' + name, {**GENERIC, **change}, failures, 3, 'bench')
            gate_ms.append((time.perf_counter() - started) * 1000)
            trace.append({'case': name, 'status': decision['status'], 'reasons': decision.get('reasons', []),
                          'outbound_requests': len(agent.adapter.sent)})
        result['privacy_trace'] = trace
        result['adversarial_cases_leaked'] = sum(row['outbound_requests'] for row in trace)
        timings = []
        for _ in range(20):
            started = time.perf_counter()
            privacy_gate(GENERIC, base)
            timings.append((time.perf_counter() - started) * 1000)
        result['privacy_gate_generic'] = summary(timings)
        result['refusal_path'] = summary(gate_ms)
        good = ('```python\nimport bisect\ndef lis(values):\n    tails = []\n    for v in values:\n'
                '        i = bisect.bisect_left(tails, v)\n        if i == len(tails):\n            tails.append(v)\n'
                '        else:\n            tails[i] = v\n    return len(tails)\n```')
        agent = CloudArchitect(base, options, RecordingAdapter(good), Guardian())
        agent.consent.grant('request:bench', 5)
        started = time.perf_counter()
        verdict = agent.consult('p-good', GENERIC, failures, 3, 'bench')
        result['advice_sandbox_verification'] = {'status': verdict['status'], 'ms': round((time.perf_counter() - started) * 1000, 1),
                                                 'outbound_payload_keys': sorted(json.loads(agent.adapter.sent[0][1]['content']))}
        router = FailureRouter(base)
        started = time.perf_counter()
        for number in range(200):
            router.route(f't{number}', {'reason': 'could not find the Export button'}, {})
        result['failure_routing_per_call_ms'] = round((time.perf_counter() - started) * 1000 / 200, 4)
        result['demonstration'] = demonstration(base)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'privacy_trace'}, indent=1))


def demonstration(base):
    import win32gui
    from pywinauto import Desktop
    from jarvis.demonstration import DemonstrationSession

    def launch():
        title = 'Jarvis UIA Fixture ' + uuid.uuid4().hex[:8]
        process = subprocess.Popen([sys.executable, str(BASE / 'tests/fixtures/uia_fixture_app.py'), title])
        handle, deadline = 0, time.monotonic() + 15
        while not handle and time.monotonic() < deadline:
            handle = win32gui.FindWindow('JarvisUiaFixture', title)
            time.sleep(.05)
        return process, handle
    process, handle = launch()
    replay_process = None
    try:
        window = Desktop(backend='uia').window(handle=handle).wrapper_object()
        button = next(c for c in window.descendants() if c.element_info.name == 'Apply')
        rect = button.rectangle()
        session = DemonstrationSession(base, lambda *a: None)
        session.request('Apply', handle)
        button.iface_invoke.Invoke()  # stands in for the user's physical click (MOCK input); UIA effect is real
        started = time.perf_counter()
        step = session.process((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2, 0x0201, 0)
        capture_ms = (time.perf_counter() - started) * 1000
        replay_process, replay_handle = launch()
        started = time.perf_counter()
        replayed = session.replay(replay_handle, step)
        replay_ms = (time.perf_counter() - started) * 1000
        return {'capture_ms_including_400ms_settle': round(capture_ms, 1), 'replay_ms': round(replay_ms, 1),
                'replay_verified': replayed['verified'], 'provider': replayed['provider'],
                'stored_selector_fields': sorted(step['selector'])}
    finally:
        process.kill()
        if replay_process:
            replay_process.kill()


if __name__ == '__main__':
    main()
