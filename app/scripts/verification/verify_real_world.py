"""Live acceptance tasks: actual models, repository reads, file writes and APIs.

Run from the app directory. Only the new test workspace is editable. A temporary
owned Ollama server is started if unavailable and shut down after the run; shared
servers and desktop applications are never stopped. No mocked model/tool results.
"""
from jarvis.paths import APP_ROOT, artifact_path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import requests

from jarvis.agent_session import AgentSession, OllamaProvider
from jarvis.brain import BrainClient
from jarvis.coder import Coder
from jarvis.task_state import TaskState
from jarvis.tools import ToolRegistry

BASE = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-at', type=int, default=1, help='Run remaining tasks in a new workspace, without replaying writes')
    parser.add_argument('--tasks', help='Optional comma-separated task numbers for a focused rerun in a new workspace')
    parser.add_argument('--repair-from', help='Copy a generated artifact app into a fresh workspace and test a feedback-guided JSON-output repair')
    args = parser.parse_args()
    selected = {int(number) for number in args.tasks.split(',')} if args.tasks else set(range(1, 14))
    if not selected <= set(range(1, 14)):
        parser.error('--tasks accepts numbers 1 through 13')
    repair_source = None
    if args.repair_from:
        repair_source = Path(args.repair_from).resolve(strict=True)
        if not repair_source.is_relative_to(BASE / 'artifacts') or not repair_source.is_dir():
            parser.error('--repair-from must be a generated app under this application artifacts directory')
        selected = {13}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = artifact_path(BASE, 'real-world-' + stamp)
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / 'expense_app'
    workspace.mkdir()
    (workspace / 'pyproject.toml').write_text('[project]\nname="expense-report-acceptance"\nversion="0.1.0"\n')
    # Add task-specific guidance; ancestor repository instructions still apply.
    (workspace / 'AGENTS.md').write_text('Use Python standard library only. Preserve source data. Implement all requested files. Never claim tests ran without results.\n')
    if repair_source:
        for name in ('ledger.py', 'main.py', 'README.md'):
            source = repair_source / name
            if source.is_symlink() or not source.is_file():
                parser.error('Repair source must contain three ordinary generated files')
            shutil.copyfile(source, workspace / name)
    report = {'date': datetime.now(timezone.utc).isoformat(), 'model': 'qwen3.5:4b',
              'scope': 'Live component/agent acceptance; no microphone or desktop interaction',
              'runner_pid': os.getpid(), 'tasks': []}
    if repair_source:
        report.update(mode='feedback-guided repair in a fresh copy', repair_source=str(repair_source))
    report_path = output / 'results.json'
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    def task(number, name, goal, run):
        if number < args.start_at or number not in selected:
            return None
        print(f'TASK {number}: {name}', flush=True)
        start = time.monotonic()
        row = {'number': number, 'name': name, 'goal': goal}
        try:
            evidence = run(goal)
            row.update(status='passed', evidence=evidence)
        except Exception as exc:
            row.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:1500])
        row['seconds'] = round(time.monotonic() - start, 2)
        report['tasks'].append(row)
        save()
        print(json.dumps(row, ensure_ascii=True), flush=True)
        return row
    provider = OllamaProvider()
    def inspect(goal, required, terms, session=None):
        session = session or AgentSession(output, BASE)
        before = len(session.history)
        answer = session.run(goal, provider, max_steps=7)
        calls = [row['tool'] for row in session.history[before:] if row['event'] == 'tool.completed']
        missing = [term for term in terms if term.casefold() not in answer.casefold()]
        if not set(required) <= set(calls) or missing:
            raise ValueError('Acceptance evidence missing; tools=' + str(calls) + '; missing terms=' + str(missing) + '; answer=' + answer[:1200])
        return {'answer': answer, 'tools': calls, 'session_id': session.identifier}
    owned = None
    client = requests.Session()
    client.trust_env = False
    brain = None
    try:
        try:
            client.get('http://127.0.0.1:11434/api/tags', timeout=3).raise_for_status()
            report['ollama'] = 'existing server reused'
        except requests.ConnectionError:
            executable = shutil.which('ollama')
            if not executable:
                raise ValueError('Ollama executable unavailable')
            log = (output / 'ollama.log').open('wb')
            environment = dict(os.environ, OLLAMA_HOST='127.0.0.1:11434', OLLAMA_NUM_PARALLEL='1')
            owned = subprocess.Popen([executable, 'serve'], env=environment, stdout=log, stderr=log,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            report['owned_ollama_pid'] = owned.pid
            for _ in range(40):
                try:
                    client.get('http://127.0.0.1:11434/api/tags', timeout=2).raise_for_status()
                    break
                except (requests.ConnectionError, requests.Timeout):
                    time.sleep(.25)
            else:
                raise ValueError('Owned Ollama server did not become ready')
            report['ollama'] = 'temporary owned server started for authorized live tests'
        tags = client.get('http://127.0.0.1:11434/api/tags', timeout=3).json()
        report['available_models'] = [item['name'] for item in tags.get('models', [])]
        save()
        task(1, 'Understand real tool registry',
             'Read jarvis/tools.py and explain why delete_file and run_command require approval. Cite those names and distinguish tool dispatch from goal verification.',
             lambda goal: inspect(goal, ['read_file'], ['delete_file', 'run_command', 'approval']))
        task(2, 'Inspect actual recovery identity',
             'Read jarvis/task_recovery.py and explain action_key and why the folder and content fields matter when preventing repeated actions.',
             lambda goal: inspect(goal, ['read_file'], ['action_key', 'folder', 'content']))
        task(3, 'Discover project architecture',
             'Use repository_map to inspect this project and identify the responsibilities of agent_session.py, agent_context.py and mcp_bridge.py. Cite these filenames.',
             lambda goal: inspect(goal, ['repository_map'], ['agent_session.py', 'agent_context.py', 'mcp_bridge.py']))
        task(4, 'Audit repository guidance and skills',
             'Read jarvis/agent_context.py and explain instruction_context, selected_skills and both .agents/skills and .jarvis/skills discovery paths.',
             lambda goal: inspect(goal, ['read_file'], ['instruction_context', 'selected_skills', '.agents/skills', '.jarvis/skills']))
        task(5, 'Audit real MCP security',
             'Read jarvis/mcp_bridge.py and explain trusted and enabled configuration, allow_tools, per-call approval, protocol 2025-11-25, timeout and no automatic retry.',
             lambda goal: inspect(goal, ['read_file'], ['allow_tools', '2025-11-25', 'approval', 'timeout']))
        task(6, 'Inspect working tree and recent commits together',
             'Use read_batch to run git_status and git_log independently for this real project. Report observed modifications and recent commit subjects; cite the literal identifiers git_status and git_log.',
             lambda goal: inspect(goal, ['read_batch'], ['git_status', 'git_log']))
        root_session = AgentSession(output, BASE)
        task(7, 'Read and remember exact configuration',
             'Read runtime_manifest.json. Name the HTTP library appearing in both main_imports and brain_imports, and the exact capability for approved MCP stdio tools. Remember the library name and capability for a follow-up.',
             lambda goal: inspect(goal, ['read_file'], ['requests', 'approved_mcp_stdio_tools'], root_session))
        def resume(goal):
            restored = AgentSession(output, BASE, root_session.identifier)
            return inspect(goal, [], ['requests', 'approved_mcp_stdio_tools'], restored)
        task(8, 'Resume persisted live conversation',
             'Based on the previous manifest inspection, repeat the exact HTTP library and MCP capability name you identified. Use prior findings rather than guessing.', resume)
        def fork(goal):
            child = root_session.fork()
            return inspect(goal, [], ['requests', 'approved_mcp_stdio_tools'], child)
        task(9, 'Fork and continue real conversation',
             'In this fork, restate the HTTP library and MCP capability from the earlier manifest finding, and explain what the names mean.', fork)
        def team(goal):
            parent = AgentSession(output, BASE)
            goals = ['Read jarvis/task_recovery.py and explain action_key and uncertain effects.',
                     'Read jarvis/agent_events.py and explain deny_tools and before_tool policy.',
                     'Read jarvis/agent_cli.py and explain session.fork and team.run.']
            rows = parent.research_parallel(goals, provider, max_steps=5)
            for row, terms in zip(rows, [('action_key',), ('deny_tools', 'before_tool'), ('session.fork', 'team.run')]):
                if not row['ok'] or any(term not in row.get('answer', '') for term in terms):
                    raise ValueError('Research agent failed acceptance: ' + json.dumps(rows)[:1500])
                child = AgentSession(output, BASE, row['session_id'])
                if not any(event['event'] == 'tool.completed' for event in child.history):
                    raise ValueError('Research agent answered without source inspection')
            return {'research_agents': rows, 'separate_sessions': len({row['session_id'] for row in rows})}
        task(10, 'Large parallel repository safety investigation',
             'Three independent live agents inspect recovery, deny-policy enforcement and CLI session/teams, using the actual source and separate budgets.', team)
        options = json.loads((BASE / 'config/config.json').read_text())['brain']
        brain = BrainClient(BASE, options)
        original_request = brain.request
        def recorded_request(operation, cancelled, **request):
            result = original_request(operation, cancelled, **request)
            if operation in {'code_plan', 'code_edit'}:
                with (output / 'generated-responses.jsonl').open('a', encoding='utf-8') as saved:
                    saved.write(json.dumps({'operation': operation, 'path': request.get('path'),
                                            'result': result}, ensure_ascii=False) + '\n')
            return result
        brain.request = recorded_request
        state = TaskState(output)
        actions = SimpleNamespace(base=output, config={}, task_state=state,
            brain=SimpleNamespace(client=brain), report=lambda kind, message: print(kind + ': ' + str(message)[:300], flush=True),
            _task_folder=lambda folder, cancelled: workspace)
        registry = ToolRegistry(actions)
        def notes(goal):
            path = workspace / 'meeting_notes.txt'
            path.write_bytes(b'Budget review\r\n')
            registry.execute({'action': 'append_file', 'value': path.name, 'folder': str(workspace),
                              'content': 'Action: compare food and transport totals.\r\n'}, lambda: False)
            read = registry.execute({'action': 'read_file', 'value': path.name, 'folder': str(workspace)}, lambda: False)
            expected = b'Budget review\r\nAction: compare food and transport totals.\r\n'
            if path.read_bytes() != expected:
                raise ValueError('Real file bytes/line endings differ')
            return {'readback': read.evidence, 'sha256': hashlib.sha256(expected).hexdigest()}
        task(11, 'Append and read back actual meeting notes', 'Append a precise action item, preserve CRLF and verify exact disk bytes.', notes)
        def web(goal):
            result = registry.execute({'action': 'scrape_web', 'value': 'https://docs.python.org/3/library/json.html',
                                       'content': '{"query":"json.loads"}'}, lambda: False)
            if 'No literal match for ' in result.evidence or 'json.loads' not in result.evidence:
                raise ValueError('Live official documentation scrape omitted json.loads')
            report['web_fetch'] = {'url': 'https://docs.python.org/3/library/json.html',
                                   'fetched_chars': len(result.evidence), 'found_json_loads': True}
            save()
            answer = brain.request('tool_text', lambda: False, tool='think', goal='In two sentences, explain json.loads versus json.load from this actual Python documentation.', context=result.evidence)['text']
            if 'json.loads' not in answer or 'json.load' not in answer:
                raise ValueError('Live model failed documentation comparison: ' + answer[:1000])
            return {'url': 'https://docs.python.org/3/library/json.html', 'fetched_chars': len(result.evidence), 'answer': answer}
        task(12, 'Research official Python JSON documentation', 'Retrieve the live official page using Jarvis scrape_web and compare load/loads with the local model.', web)
        big_goal = ('Create main.py, ledger.py and README.md as a complete standard-library CSV expense reporting app. '
            'ledger.py defines read_totals(path) returning {"total":"0.00","by_category":{}} with two-decimal strings; '
            'read CSV columns category,amount using csv and Decimal, preserve quoted fields, reject nonfinite amounts, '
            'accept negative refunds, map blank category to uncategorized, '
            'empty data returns zero and empty categories, invalid amount raises ValueError mentioning row number, '
            'missing columns raises ValueError. main.py accepts one positional CSV path, prints only the report JSON '
            'on success, errors print to stderr and exit nonzero. README.md explains usage. No installation or network. '
            'Order ledger.py before main.py for shared interfaces. Preserve source CSV files.')
        if repair_source:
            big_goal = ('Modify main.py to import json and print json.dumps(result) instead of printing the Python dictionary. '
                'Actual CLI tests failed because stdout used single-quoted Python dictionary syntax, not JSON. '
                'Preserve ledger.read_totals, the main function, positional CSV argument, stderr errors and nonzero error exits. '
                'Output only JSON on success. No other files need modification; README already specifies JSON output.')
        def build(goal):
            state.start(goal, 'code_task', workspace)
            result = Coder(actions, brain).run(workspace, goal)
            cases = [
                ('ordinary', 'category,amount\nfood,10.00\nfood,2.50\ntransport,20.00\n', {'total': '32.50', 'by_category': {'food': '12.50', 'transport': '20.00'}}),
                ('refund', 'category,amount\nfood,10.00\nfood,-3.00\n', {'total': '7.00', 'by_category': {'food': '7.00'}}),
                ('precision', 'category,amount\nfood,0.10\nfood,0.20\n', {'total': '0.30', 'by_category': {'food': '0.30'}}),
                ('blank-category', 'category,amount\n,5.00\n', {'total': '5.00', 'by_category': {'uncategorized': '5.00'}}),
                ('empty', 'category,amount\n', {'total': '0.00', 'by_category': {}}),
                ('invalid', 'category,amount\nfood,nonsense\n', None),
                ('missing-header', 'category,cost\nfood,2\n', None),
                ('quoted-category', 'category,amount\n"food, dining",12.50\n', {'total': '12.50', 'by_category': {'food, dining': '12.50'}}),
                ('missing-header-empty', 'category,cost\n', None),
                ('nonfinite-amount', 'category,amount\nfood,NaN\n', None),
            ]
            evidence = []
            for name, source, expected in cases:
                csv_path = workspace / (name + '.csv')
                csv_path.write_text(source, encoding='utf-8')
                before = csv_path.read_bytes()
                run = subprocess.run([sys.executable, str(workspace / 'main.py'), str(csv_path)],
                    cwd=workspace, capture_output=True, text=True, timeout=10, check=False,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    good = (run.returncode != 0 and bool(run.stderr.strip())) if expected is None else (
                        run.returncode == 0 and json.loads(run.stdout) == expected)
                except ValueError:
                    good = False
                good = good and csv_path.read_bytes() == before
                evidence.append({'case': name, 'passed': good, 'exit_code': run.returncode,
                                 'stdout': run.stdout[:1000], 'stderr': run.stderr[:1000]})
            report['build_cases'] = evidence
            save()
            if not (workspace / 'README.md').is_file() or not all(case['passed'] for case in evidence):
                raise ValueError('Generated app acceptance failed: ' + json.dumps(evidence))
            state.finish('completed', result)
            return {'coding_result': result, 'files': ['ledger.py', 'main.py', 'README.md'], 'functional_cases': evidence}
        task(13, 'Large task: build and execute multi-file expense application', big_goal, build)
        report['summary'] = {'passed': sum(row['status'] == 'passed' for row in report['tasks']),
                             'failed': sum(row['status'] == 'failed' for row in report['tasks']),
                             'total': len(report['tasks'])}
        save()
        print('REPORT: ' + str(report_path), flush=True)
        print(json.dumps(report['summary']), flush=True)
    finally:
        if brain:
            brain.close()
        client.close()
        if owned and owned.poll() is None:
            owned.terminate()
            try:
                owned.wait(timeout=5)
            except subprocess.TimeoutExpired:
                owned.kill()
                owned.wait(timeout=5)
        report['owned_ollama_stopped'] = bool(owned and owned.poll() is not None)
        save()
    if any(row['status'] == 'failed' for row in report['tasks']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
