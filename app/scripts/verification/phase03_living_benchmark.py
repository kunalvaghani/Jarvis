"""Phase 3 measurements: skill telemetry, ranked context, CAPTURED and MCP synthesis.

Real SQLite store, SkillMemory, ToolRegistry/openpyxl adapters and Docker MCP runtime
on temporary fixtures; the `author` that supplies the MCP spec is a fixed fixture
(stands in for the local model). No account, network or desktop action.
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
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def summary(values):
    values = sorted(values)
    return {'n': len(values), 'p50_ms': round(statistics.median(values), 3), 'p95_ms': round(values[int((len(values) - 1) * .95)], 3)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    out = Path(parser.parse_args(argv).out)
    if out.exists():
        raise SystemExit('Refusing to overwrite preserved measurements: ' + str(out))
    from jarvis.skill_memory import SkillMemory
    from jarvis.skill_evolution import SkillEvolution
    from jarvis.tools import ToolRegistry
    from jarvis import mcp_synthesis
    result = {'schema_version': 1, 'measured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'sections': {}}
    with tempfile.TemporaryDirectory() as root:
        root = Path(root)
        base, docs = root / 'base', root / 'docs'
        base.mkdir()
        docs.mkdir()
        memory = SimpleNamespace(vault=root, base=base, enabled=True, hermes_skills_enabled=False)
        started = time.perf_counter()
        skills = SkillMemory(memory, BASE / 'skills')
        result['sections']['cold_load_with_store_ms'] = round((time.perf_counter() - started) * 1000, 3)
        task = {'id': 'a' * 32}
        skills.task_id_provider = lambda: task['id']
        store = skills.store
        skill = skills.catalog[0]['skill_id']
        writes = []
        for number in range(200):
            started = time.perf_counter()
            store.event(skill, 'selected', f'{number:032x}')
            writes.append((time.perf_counter() - started) * 1000)
        duplicate = []
        for number in range(50):
            started = time.perf_counter()
            store.event(skill, 'selected', f'{number:032x}')
            duplicate.append((time.perf_counter() - started) * 1000)
        result['sections']['event_insert'] = summary(writes)
        result['sections']['duplicate_event_ignored'] = summary(duplicate)
        result['sections']['selected_count_after_duplicates'] = store.metrics(skill)['selected_count']
        contexts = []
        for goal in ('play a song on spotify', 'fix the failing unit test in my python project',
                     'fill the login form in chrome', 'research the latest rust release notes') * 10:
            skills._metrics_cache = (float('-inf'), {})
            started = time.perf_counter()
            skills.context(goal)
            contexts.append((time.perf_counter() - started) * 1000)
        result['sections']['context_with_living_ranking_uncached'] = summary(contexts)
        actions = SimpleNamespace(base=base, allowed_tools=None, report=lambda *a: None, task_state=None, config={},
                                  skills=skills, _task_folder=lambda name, cancelled: str(docs), _approve=lambda *a: None)
        registry = ToolRegistry(actions)
        skills_python = BASE / '.venv-skills/Scripts/python.exe'
        for name in ('ledger.xlsx', 'fixture.xlsx'):
            subprocess.run([str(skills_python), '-c', "import openpyxl,sys\nb=openpyxl.Workbook();s=b.active;s.title='Data';"
                            "s['A1']=1;b.save(sys.argv[1])", str(docs / name)], check=True, timeout=120)

        def step(name, operation, **content):
            return {'action': 'office_xlsx', 'value': name, 'folder': 'docs', 'content': json.dumps({'operation': operation, **content})}
        trace = []
        for item in (step('ledger.xlsx', 'write', sheet='Data', cells={'A1': 5}), step('ledger.xlsx', 'read')):
            trace.append({**item, 'call_id': registry.execute(item, lambda: False).call_id, 'verified': True})
        started = time.perf_counter()
        captured = SkillEvolution(skills, registry).capture(
            {'task_id': 'b' * 32, 'goal': 'record quarterly totals in the ledger', 'status': 'completed'}, trace,
            [step('fixture.xlsx', 'write', sheet='Data', cells={'A1': 7}), step('fixture.xlsx', 'read')])
        result['sections']['captured_with_real_validation_ms'] = round((time.perf_counter() - started) * 1000, 1)
        result['sections']['captured_skill'] = captured['name']
        status = mcp_synthesis.image_status()
        if status['available']:
            spec = {'name': 'sha256_text', 'description': 'Return the SHA-256 hex digest of UTF-8 text.',
                    'parameters': {'text': 'str'}, 'returns': 'str', 'mechanism': ['hashlib'],
                    'implementation': 'return hashlib.sha256(text.encode("utf-8")).hexdigest()',
                    'tests': [{'arguments': {'text': 'abc'}, 'expected': 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'},
                              {'arguments': {'text': 1}, 'error': True}]}
            started = time.perf_counter()
            synthesized = mcp_synthesis.synthesize(actions, 'compute a sha256 fingerprint for text', lambda need: spec)
            result['sections']['mcp_synthesis_end_to_end_ms'] = round((time.perf_counter() - started) * 1000, 1)
            calls = []
            for number in range(3):
                started = time.perf_counter()
                registry.execute({'action': 'mcp_call', 'value': synthesized['server'], 'content': json.dumps(
                    {'name': 'sha256_text', 'arguments': {'text': str(number)}})}, lambda: False)
                calls.append((time.perf_counter() - started) * 1000)
            result['sections']['mcp_generated_call_including_container_start'] = summary(calls)
            result['sections']['containers_left'] = mcp_synthesis.reap(synthesized['server'])
        else:
            result['sections']['mcp'] = 'BLOCKED: ' + status['reason']
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['sections'], indent=1))


if __name__ == '__main__':
    main()
