"""Live evaluation: qwen3.5:9b (local Ollama) driving the YouTube connector through Jarvis.

Two modes, both executing every connector call through Jarvis's real
ToolRegistry -> mcp_bridge -> stdio connector -> live YouTube path:

* direct - the model sees the connector's five tools as native Ollama functions.
* jarvis - the model sees what Jarvis's planner offers for the request (capability
  routes + the youtube-media skill guide) and answers in Jarvis's one-step JSON format
  (action/value/content). Playback/browser steps are scored but NOT executed, so the
  run never drives the real browser. This mirrors the planner's format and settings;
  it is not the full Jarvis Brain.

Approval is auto-granted by this harness and every grant is counted.
Usage: python evals/youtube_qwen_eval.py [--model qwen3.5:9b] [--out DIR]
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
APP = next(p for p in ROOT.parents if (p / 'main.py').is_file())
sys.path.insert(0, str(APP))
from jarvis import capabilities  # noqa: E402
from jarvis.agent_tools import TOOLS as AGENT_TOOLS  # noqa: E402
from jarvis.task_state import TaskState  # noqa: E402
from jarvis.tools import SPECS, ToolRegistry  # noqa: E402

PL = 'PLOzDu-MXXLlgKMA3S2FXY_XVyDrukc0si'
NUMBER = re.compile(r'\d[\d,.]*')


def fold(text):
    return re.sub(r'\s+', ' ', str(text)).casefold()


def mentions_title(answer, rows):
    """Grounded when the answer quotes the start of at least one returned title."""
    titles = [r.get('title', '') for r in (rows if isinstance(rows, list) else rows.get('videos', []) if isinstance(rows, dict) else [])]
    return any(len(t) >= 6 and fold(t)[:14] in fold(answer) for t in titles)


def mentions_number(answer, value):
    digits = {n.replace(',', '').split('.')[0] for n in NUMBER.findall(answer)}
    return str(value) in digits


SCENARIOS = [
    dict(id='playlists', prompt='Find me three lofi hip hop playlists on YouTube.', tool='search_playlists',
         args=lambda a: 'lofi' in fold(a.get('query')) and a.get('limit', 5) == 3, grounded=mentions_title),
    dict(id='videos', prompt='Search YouTube for videos about Blender material nodes.', tool='search_videos',
         args=lambda a: 'blender' in fold(a.get('query')) and 'material' in fold(a.get('query')), grounded=mentions_title,
         jarvis_alternative='media_search'),  # Jarvis's existing visible YouTube search is also correct here
    dict(id='duration', prompt='How long is this YouTube video: https://youtu.be/YOJsKatW-Ts ?', tool='video_details',
         args=lambda a: 'YOJsKatW-Ts' in str(a.get('video')),
         grounded=lambda ans, r: isinstance(r, dict) and (mentions_number(ans, r.get('duration_seconds', -1) // 60)
                                                         or mentions_number(ans, r.get('duration_seconds', -1)))),
    dict(id='playlist_contents', prompt='What videos are in the YouTube playlist ' + PL + '? List the first five.',
         tool='playlist_videos', args=lambda a: PL in str(a.get('playlist')), grounded=mentions_title),
    dict(id='fake_link', prompt='Is https://www.youtube.com.evil.example/watch?v=YOJsKatW-Ts a real YouTube link?',
         tool='parse_link', args=lambda a: 'evil.example' in str(a.get('link')), tool_optional=True,
         grounded=lambda ans, r: re.search(r"\b(no|not|isn't|is not|fake|suspicious)\b", ans, re.I) is not None),
    dict(id='uploader_views', prompt='Who uploaded the YouTube video dQw4w9WgXcQ and how many views does it have?',
         tool='video_details', args=lambda a: 'dQw4w9WgXcQ' in str(a.get('video')),
         grounded=lambda ans, r: isinstance(r, dict) and fold(r.get('channel', '?'))[:8] in fold(ans)),
    dict(id='top5', prompt='Show me the top 5 YouTube results for python asyncio tutorial.', tool='search_videos',
         args=lambda a: 'asyncio' in fold(a.get('query')) and a.get('limit', 5) == 5, grounded=mentions_title),
    dict(id='playlist_count', prompt='Find an Arijit Singh playlist on YouTube and tell me how many videos it has.',
         tool='search_playlists', args=lambda a: 'arijit' in fold(a.get('query')),
         grounded=lambda ans, r: isinstance(r, list) and any(mentions_number(ans, row.get('video_count', -1)) for row in r)),
    dict(id='play_playlist', prompt='Play a lofi hip hop playlist on YouTube.', tool='search_playlists',
         args=lambda a: 'lofi' in fold(a.get('query')), grounded=None, playback='browser_navigate'),
    dict(id='pause_negative', prompt='Pause the YouTube video.', tool=None, args=None, grounded=None, playback='media_control'),
]


def ollama(model, messages, **extra):
    body = {'model': model, 'messages': messages, 'stream': False, 'think': False, 'keep_alive': '10m',
            'options': {'temperature': 0.1, 'num_ctx': 8192}, **extra}
    request = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=600) as response:
        reply = json.load(response)
    return reply['message'], time.monotonic() - started


class Jarvis:
    """Temporary Jarvis base with a copy of the real app/.jarvis/mcp.json."""
    def __init__(self, folder):
        (folder / '.jarvis').mkdir()
        (folder / '.jarvis' / 'mcp.json').write_bytes((APP / '.jarvis' / 'mcp.json').read_bytes())
        state = TaskState(folder)
        state.start('qwen YouTube connector evaluation', 'task')
        self.actions = SimpleNamespace(base=folder, task_state=state, report=Mock(), config={}, allowed_tools=None,
                                       _approve=Mock(), skills=None)

    def call(self, name, arguments):
        step = dict(action='mcp_call', value='youtube', content=json.dumps({'name': name, 'arguments': arguments}))
        try:
            evidence = json.loads(ToolRegistry(self.actions).execute(step, lambda: False).evidence)
            return True, evidence['structuredContent']['result']
        except (ValueError, KeyError) as exc:
            return False, str(exc)[:300]


def direct_tools():
    sys.path.insert(0, str(ROOT / 'connectors' / 'apps' / 'youtube'))
    from server import YouTubeConnector
    return [{'type': 'function', 'function': {'name': r['name'], 'description': r['description'],
                                              'parameters': r['inputSchema']}} for r in YouTubeConnector().describe()]


def run_direct(model, scenario, jarvis):
    messages = [{'role': 'system', 'content': 'You are Jarvis. Use the YouTube tools when they help; they are read-only and '
                 'cannot play or pause. Answer only from tool results.'},
                {'role': 'user', 'content': scenario['prompt']}]
    calls, seconds, last = [], 0.0, None
    for _ in range(4):
        message, spent = ollama(model, messages, tools=direct_tools())
        seconds += spent
        messages.append(message)
        if not message.get('tool_calls'):
            return dict(calls=calls, answer=message.get('content', ''), seconds=seconds, last=last)
        for item in message['tool_calls']:
            name, arguments = item['function']['name'], item['function'].get('arguments') or {}
            ok, result = jarvis.call(name, arguments)
            calls.append(dict(tool=name, arguments=arguments, ok=ok))
            last = result if ok else last
            messages.append({'role': 'tool', 'tool_name': name, 'content': json.dumps(result if ok else {'error': result})[:6000]})
    return dict(calls=calls, answer='', seconds=seconds, last=last)


def offered(goal):
    names = []
    for route in capabilities.intents(goal):
        for name in capabilities.ROUTES[route][1]:
            names += [name, *capabilities.PREREQUISITES.get(name, ())]
    descriptions = {spec.name: spec.description for spec in SPECS}
    descriptions.update({name: row[1] for name, row in AGENT_TOOLS.items()})
    seen = []
    for name in names:
        if name not in seen and name in descriptions:
            seen.append(name)
    # Field hints come from Jarvis's own _FIELDS table (the real planner prompt explains fields separately).
    from jarvis.tools import _FIELDS
    fields = {**_FIELDS, 'mcp_call': ({'value', 'content'}, set()), 'mcp_status': ({'value'}, set()),
              'mcp_list_tools': ({'value'}, set())}
    return [{'action': n, 'description': descriptions[n],
             **({'required_fields': sorted(fields[n][0]), 'optional_fields': sorted(fields[n][1])} if n in fields else {})}
            for n in seen]


def guide():
    text = (APP / 'skills' / 'youtube-media' / 'SKILL.md').read_text(encoding='utf-8')
    return text.split('---', 2)[2].strip()


def run_jarvis(model, scenario, jarvis):
    tools = offered(scenario['prompt'])
    schema = {'type': 'object', 'required': ['done', 'steps', 'answer'], 'properties': {
        'done': {'type': 'boolean'}, 'answer': {'type': 'string'},
        'steps': {'type': 'array', 'maxItems': 1, 'items': {'type': 'object', 'required': ['action', 'value'], 'properties': {
            'action': {'type': 'string', 'enum': [t['action'] for t in tools] or ['none']},
            'value': {'type': 'string'}, 'content': {'type': 'string'}, 'platform': {'type': 'string'}}}}}}
    system = ('You are the Jarvis task planner. Return the single next step as JSON, or done=true with the final '
              'spoken answer when the goal is complete. Choose only offered tools.\n\nOffered tools:\n'
              + json.dumps(tools, ensure_ascii=False) + '\n\nSkill guide youtube-media:\n' + guide())
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': 'Goal: ' + scenario['prompt']}]
    steps, seconds, last = [], 0.0, None
    for _ in range(4):
        message, spent = ollama(model, messages, format=schema)
        seconds += spent
        messages.append(message)
        try:
            plan = json.loads(message.get('content') or '{}')
        except ValueError:
            return dict(steps=steps, answer='', seconds=seconds, last=last, invalid=True, offered=[t['action'] for t in tools])
        if plan.get('done') or not plan.get('steps'):
            return dict(steps=steps, answer=plan.get('answer', ''), seconds=seconds, last=last, offered=[t['action'] for t in tools])
        step = plan['steps'][0]
        record = dict(action=step.get('action'), value=step.get('value', ''), content=step.get('content', ''))
        if step.get('action') != 'mcp_call':
            record['executed'] = False  # playback/browser steps are scored, never run by this harness
            steps.append(record)
            return dict(steps=steps, answer=plan.get('answer', ''), seconds=seconds, last=last, offered=[t['action'] for t in tools])
        try:
            call = json.loads(step.get('content') or '{}')
            ok, result = (jarvis.call(call['name'], call.get('arguments', {})) if step.get('value') == 'youtube'
                          else (False, 'unknown MCP server ' + str(step.get('value'))))
        except (ValueError, KeyError, TypeError, AttributeError):
            ok, result, call = False, 'content was not {"name","arguments"} JSON', {}
        record.update(executed=True, ok=ok, tool=call.get('name') if isinstance(call, dict) else None,
                      arguments=call.get('arguments') if isinstance(call, dict) else None)
        steps.append(record)
        last = result if ok else last
        messages.append({'role': 'user', 'content': 'Observation for ' + step['action'] + ': '
                         + json.dumps({'ok': ok, 'result': result}, ensure_ascii=False)[:6000]})
    return dict(steps=steps, answer='', seconds=seconds, last=last, offered=[t['action'] for t in tools])


def answered_without_tool(scenario, run):
    """A correct answer that needed no lookup (e.g. an obviously fake domain) is a pass."""
    return bool(scenario.get('tool_optional') and not run.get('calls') and not run.get('steps')
                and run.get('answer') and scenario['grounded'](run['answer'], None))


def score_direct(scenario, run):
    if answered_without_tool(scenario, run):
        return dict(tool_ok=True, args_ok=True, grounded=True)
    first = run['calls'][0] if run['calls'] else None
    if scenario['tool'] is None:
        return dict(tool_ok=not run['calls'], args_ok=True, grounded=True)
    tool_ok = bool(first) and first['tool'] == scenario['tool']
    args_ok = tool_ok and scenario['args'](first['arguments'])
    grounded = scenario['grounded'] is None or (run['last'] is not None and scenario['grounded'](run['answer'], run['last']))
    return dict(tool_ok=tool_ok, args_ok=args_ok, grounded=grounded and bool(run['answer']) if scenario['grounded'] else True)


def score_jarvis(scenario, run):
    if answered_without_tool(scenario, run):
        return dict(tool_ok=True, args_ok=True, grounded=True)
    steps = run['steps']
    first = steps[0] if steps else {}
    if scenario['tool'] is None:
        ok = first.get('action') == scenario['playback']
        return dict(tool_ok=ok, args_ok=ok and 'pause' in fold(first.get('value')), grounded=True)
    if scenario.get('jarvis_alternative') and first.get('action') == scenario['jarvis_alternative']:
        ok = 'blender' in fold(first.get('value'))
        return dict(tool_ok=ok, args_ok=ok, grounded=ok)
    tool_ok = first.get('action') == 'mcp_call' and first.get('tool') == scenario['tool'] and first.get('ok') is True
    args_ok = tool_ok and scenario['args'](first.get('arguments') or {})
    if scenario.get('playback'):
        nxt = steps[1] if len(steps) > 1 else {}
        urls = {r.get('play_url') for r in run['last'] or [] if isinstance(r, dict)} - {''}
        titles = {fold(r.get('title')) for r in run['last'] or [] if isinstance(r, dict)}
        grounded = (nxt.get('action') == 'browser_navigate' and nxt.get('value') in urls) or (
            nxt.get('action') == 'media_search' and fold(nxt.get('value')) in titles)
    else:
        grounded = run['last'] is not None and bool(run['answer']) and scenario['grounded'](run['answer'], run['last'])
    return dict(tool_ok=tool_ok, args_ok=args_ok, grounded=grounded)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='qwen3.5:9b')
    parser.add_argument('--out', default=str(APP / 'artifacts' / 'jarvis-audit' / 'youtube-connector' / datetime.now().strftime('%Y-%m-%d')))
    parser.add_argument('--only', default='')
    parser.add_argument('--mode', choices=('both', 'direct', 'jarvis'), default='both')
    parser.add_argument('--name', default='qwen-eval.json')
    options = parser.parse_args()
    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    ollama(options.model, [{'role': 'user', 'content': 'Reply OK.'}])  # load the model once; not timed below
    with tempfile.TemporaryDirectory() as folder:
        jarvis = Jarvis(Path(folder))
        for scenario in SCENARIOS:
            if options.only and scenario['id'] not in options.only.split(','):
                continue
            for mode, runner, scorer in (('direct', run_direct, score_direct), ('jarvis', run_jarvis, score_jarvis)):
                if options.mode not in ('both', mode):
                    continue
                if mode == 'direct' and scenario.get('playback'):
                    if scenario['tool'] is not None:
                        continue  # playback needs Jarvis's player tools, which direct mode does not have
                run = runner(options.model, scenario, jarvis)
                score = scorer(scenario, run)
                run.pop('last', None)
                rows.append(dict(scenario=scenario['id'], mode=mode, prompt=scenario['prompt'], **score,
                                 passed=all(score.values()), **run))
                print(f"{mode:6} {scenario['id']:18} tool={score['tool_ok']!s:5} args={score['args_ok']!s:5} "
                      f"grounded={score['grounded']!s:5} {run['seconds']:.1f}s", flush=True)
        approvals = jarvis.actions._approve.call_count
    summary = {'model': options.model, 'date': datetime.now().isoformat(timespec='seconds'), 'approvals_granted_by_harness': approvals,
               'results': {mode: f"{sum(r['passed'] for r in rows if r['mode'] == mode)}/{sum(r['mode'] == mode for r in rows)}"
                           for mode in ('direct', 'jarvis')}, 'runs': rows}
    (out / options.name).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary['results']), 'approvals', approvals, '->', out / options.name)


if __name__ == '__main__':
    main()
