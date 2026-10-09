"""Opt-in comparison: real planners, same bounded browser executor and goals."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time

from jarvis.brain import BrainClient, validate_plan
from jarvis.browser_automation import BrowserAutomation
from jarvis.fast_workflows import compile_workflow
from jarvis.hermes import HermesClient, REVISION
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory
from jarvis.ui_controls import label_key


def checked_steps(proposal, expected):
    if proposal.get('question'):
        raise ValueError('Planner requested clarification for a complete benchmark goal.')
    steps = validate_plan(proposal)
    found = []
    for step in steps:
        if step['action'] in {'browse', 'open', 'browser_navigate'} and step['value'].casefold() in {'youtube', 'https://www.youtube.com/', 'https://youtube.com'}:
            found.append({'action': 'navigate', 'value': 'youtube'})
        elif step['action'] == 'media_search' and step.get('platform') == 'youtube' and step['value'].casefold() == expected[0]['value'].casefold():
            found.append({'action': 'search', 'value': expected[0]['value']})
        elif step['action'] == 'select' and len(expected) == 2 and label_key(step['value']) in {'first video', '1 video', 'first result', '1 result'}:
            found.append({'action': 'select_video', 'value': '', 'position': 1})
        else:
            raise ValueError('Planner proposed a step outside the exact public benchmark goal.')
    effective = [s['action'] for s in found if s['action'] != 'navigate']
    if effective != ['search'] + (['select_video'] if len(expected) == 2 else []):
        raise ValueError('Planner omitted or reordered a required benchmark step.')
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--route', choices=['all', 'direct', 'hermes', 'native_qwen'], default='all')
    parser.add_argument('--output', default='artifacts/reports/hermes-comparison.json')
    parser.add_argument('--cases', type=int, choices=[1, 2, 3], default=3)
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required: opens an owned browser and may start public video playback')
    base = Path(__file__).resolve().parents[2]
    config = json.loads((base / 'config/config.json').read_text(encoding='utf-8'))
    memory = ObsidianMemory(base, config['memory'])
    memory.skills = SkillMemory(memory)
    options = deepcopy(config['brain'])
    options['hermes']['enabled'] = False
    clients = {'hermes': HermesClient(base, options), 'native_qwen': BrainClient(base, options)}
    browser = BrowserAutomation(config['apps'], base)
    tools = [{'action': 'media_search', 'description': 'Search YouTube; value exact query, platform youtube'},
             {'action': 'select', 'description': 'Select an explicit first video result; value first video'},
             {'action': 'browse', 'description': 'Open YouTube; value youtube, browser chrome'}]
    goals = ['search YouTube for robot tutorials', 'search YouTube for Python basics',
             'open YouTube and search Python tutorial and play first video'][:args.cases]
    report = {'date': '2026-10-01', 'scope': 'Real local planning plus real owned-Chrome actions and deterministic independent result checks. Same public goals, model and executor; excludes STT/TTS. Not standalone Hermes computer_use or full Jarvis vision/replan loop.',
              'model': options['planner'], 'hermes_revision': REVISION, 'hermes_context': 64000,
              'native_context': 16384, 'order': 'direct then Hermes then native Qwen per case', 'runs': []}
    path = base / args.output
    if path.resolve().parent != (base / 'artifacts').resolve() or path.suffix != '.json':
        raise ValueError('Use a JSON result file directly in artifacts.')
    try:
        for case, goal in enumerate(goals, 1):
            expected = compile_workflow(goal, config['apps'])
            for route in (('direct', 'hermes', 'native_qwen') if args.route == 'all' else (args.route,)):
                row = {'case': case, 'route': route, 'goal': goal, 'cold_worker': case == 1 and route != 'direct'}
                report['runs'].append(row)
                start = time.monotonic()
                print(json.dumps({'starting': case, 'route': route}), flush=True)
                try:
                    if route == 'direct':
                        steps = [{'action': 'search', 'value': expected[0]['value']}]
                        if len(expected) == 2:
                            steps.append({'action': 'select_video', 'value': '', 'position': 1})
                        row['planning_seconds'] = round(time.monotonic() - start, 3)
                    else:
                        proposal = clients[route].request('plan', lambda: False, goal=goal, apps=['youtube'], tools=tools,
                                screen={'summary': 'Jarvis-owned Chrome is available; public YouTube search task.'},
                                memory_context=memory.task_context(goal), skill_context=memory.skills.context(goal))
                        row['planning_seconds'] = round(time.monotonic() - start, 3)
                        steps = checked_steps(proposal, expected)
                    row['plan_matches_goal'] = True
                    exec_start = time.monotonic()
                    for step in steps:
                        result = browser.request(step['action'], value=step['value'], position=step.get('position'), new_task=step['action'] in {'navigate', 'search'})
                        if step['action'] != 'navigate' and result.get('verified') is not True:
                            raise ValueError('Requested result was not independently verified.')
                    row['execution_seconds'] = round(time.monotonic() - exec_start, 3)
                    row['success'] = True
                except Exception as exc:
                    row['success'] = False
                    row['error'] = str(exc)[:500]
                row['total_seconds'] = round(time.monotonic() - start, 3)
                # Pause only this benchmark's owned video window, without replaying any selection.
                try:
                    observed = browser.request('inspect')
                    row['final_public_page'] = observed.get('url', '')
                    row['player_diagnostic'] = observed.get('player')
                except Exception:
                    pass
                if 'watch?' in browser.last_url:
                    try:
                        state = browser.request('control', value='status')
                        if state.get('state', {}).get('paused') is False:
                            browser.request('control', value='pause')
                    except Exception:
                        pass
                path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
                print(json.dumps(row), flush=True)
    finally:
        for client in clients.values():
            client.close()
        browser.close()
    print(json.dumps({'finished': True, 'report': str(path)}), flush=True)


if __name__ == '__main__':
    main()
