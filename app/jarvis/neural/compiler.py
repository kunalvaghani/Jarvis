"""Request -> per-goal execution graph. Deterministic templates first; no model call to plan simple requests.

Each workflow is a small typed template. ``compile_goal`` returns None when no template fits, and the caller
falls back to the legacy planner neuron, so a request the brain does not know yet still works as before.
Templates are checked against the capability graph before they run (``execution.check``).
"""
from __future__ import annotations

from pathlib import Path
import re
import uuid
from typing import Any, Callable, Dict, List, Optional

from .execution import Bind, Plan, Step

RESEARCH = re.compile(r'^\s*(?:please\s+|jarvis,?\s+)?(?:research|look\s+up|find\s+out|search\s+(?:the\s+web|online|'
                      r'the\s+internet)\s+(?:for|about))\s+(?P<query>.{3,300}?)[\s.?!]*$', re.I)
WRITES = re.compile(r'\b(?:save|write|create|make|open|send|post|email|delete|install|run|play|buy|order)\b', re.I)
BUGFIX = re.compile(r'\bfix\b.{0,80}\bbugs?\b|\bbugs?\b.{0,40}\bfix\b', re.I)
# Overlapping (lookahead): "in calc.py in the calc-bug folder" must also try "calc-bug".
FOLDER = re.compile(r'(?=\b(?:in|inside|of)\s+(?:the\s+|my\s+)?([\w.() -]{1,60}?)\s+folder\b)', re.I)
NOT_FOLDERS = {'test', 'my test', 'jarvis test', 'the test'}


def _const(journal: Any, value: Any, kind: str) -> Bind:
    import json
    return Bind(const=journal.put(json.dumps(value), kind))


def resolve_folder(goal: str, config: Any) -> Optional[Path]:
    from .adapters import allowed_roots
    roots = allowed_roots(config)
    for match in FOLDER.finditer(goal):
        name = match.group(1).strip()
        if name.lower() in NOT_FOLDERS:
            continue
        for root in roots:
            candidate = (root / name).resolve()
            if candidate.is_dir() and root in candidate.parents:
                return candidate
    return None


def research(goal: str, journal: Any, config: Any) -> Optional[List[Step]]:
    match = RESEARCH.match(goal)
    if not match or WRITES.search(match.group('query')):
        return None
    query = match.group('query')
    return [
        Step(step_id='search', neuron='tool.web_search@v1', bind={'query': _const(journal, query, 'Query')},
             max_attempts=2),
        Step(step_id='pick', neuron='skill.research.pick_source@v1', bind={'results': Bind(step='search', port='results')}),
        Step(step_id='read', neuron='tool.scrape_web@v1', bind={'url': Bind(step='pick', port='url')}, max_attempts=2),
        Step(step_id='analyse', neuron='skill.research.analyse@v1', max_attempts=2,
             bind={'query': _const(journal, query, 'Query'), 'page': Bind(step='read', port='page')}),
        Step(step_id='check', neuron='verifier.report_grounded@v1', repairs='analyse',
             bind={'report': Bind(step='analyse', port='report'), 'page': Bind(step='read', port='page')}),
        Step(step_id='answer', neuron='motor.report@v1',
             bind={'report': Bind(step='analyse', port='report'), 'verdict': Bind(step='check', port='verdict')}),
    ]


def bug_fix(goal: str, journal: Any, config: Any) -> Optional[List[Step]]:
    if not BUGFIX.search(goal):
        return None
    folder = resolve_folder(goal, config)
    if folder is None:
        return None
    scope = f'fix the code in {folder.name}: run its tests on a scratch copy and write the checked fix'
    return [
        Step(step_id='inspect', neuron='skill.code.inspect@v1', bind={'folder': _const(journal, str(folder), 'FolderPath')}),
        Step(step_id='patch', neuron='skill.code.patch@v1', max_attempts=3,
             bind={'repo': Bind(step='inspect', port='repo'), 'goal': _const(journal, goal, 'Goal')}),
        Step(step_id='trial', neuron='skill.code.test@v1', approval_scope=scope,
             bind={'repo': Bind(step='inspect', port='repo'), 'patch': Bind(step='patch', port='patch')}),
        Step(step_id='trial_check', neuron='verifier.tests_pass@v1', repairs='patch',
             bind={'report': Bind(step='trial', port='report')}),
        Step(step_id='apply', neuron='skill.code.apply@v1', approval_scope=scope,
             bind={'repo': Bind(step='inspect', port='repo'), 'patch': Bind(step='patch', port='patch'),
                   'verdict': Bind(step='trial_check', port='verdict')}),
        Step(step_id='final', neuron='skill.code.test@v1', approval_scope=scope,
             bind={'repo': Bind(step='apply', port='repo')}),
        Step(step_id='final_check', neuron='verifier.tests_pass@v1', bind={'report': Bind(step='final', port='report')}),
        Step(step_id='summary', neuron='skill.code.summarise@v1',
             bind={'patch': Bind(step='patch', port='patch'), 'verdict': Bind(step='final_check', port='verdict')}),
        Step(step_id='answer', neuron='motor.report@v1',
             bind={'report': Bind(step='summary', port='report'), 'verdict': Bind(step='final_check', port='verdict')}),
    ]


CREATE = re.compile(r'^\s*(?:please\s+)?create\s+(?:a\s+)?(?:new\s+)?(?:text\s+)?file\s+(?:called|named)\s+'
                    r'(?P<name>[\w.() -]{1,80}?\.(?:txt|md|csv|json|log))\s+(?P<where>.{0,120}?)\s*'
                    r'(?:containing|with(?: the text)?|that says)\s+(?:exactly\s*)?:?\s*(?P<text>.+?)\s*$', re.I | re.S)
TEST_FOLDER = re.compile(r'\b(?:my\s+|the\s+)?(?:jarvis\s+)?test\s+folder\b', re.I)


def create_text(goal: str, journal: Any, config: Any) -> Optional[List[Step]]:
    match = CREATE.match(goal)
    if not match:
        return None
    from .adapters import allowed_roots
    where = match.group('where')
    folder = allowed_roots(config)[0] if TEST_FOLDER.search(where) else resolve_folder(goal, config)
    if folder is None or not folder.is_dir():
        return None
    text = match.group('text').strip()
    return [
        Step(step_id='write', neuron='tool.create_file@v1',
             bind={'folder': _const(journal, str(folder), 'FolderPath'), 'name': _const(journal, match.group('name'), 'Text'),
                   'text': _const(journal, text, 'FileText')}),
        Step(step_id='check', neuron='verifier.text_file_saved@v1',
             bind={'path': Bind(step='write', port='path'), 'expected': _const(journal, text, 'FileText')}),
        Step(step_id='answer', neuron='motor.report@v1',
             bind={'report': _const(journal, f'I created {match.group("name")} in {folder.name} with exactly that text.',
                                    'Report'), 'verdict': Bind(step='check', port='verdict')}),
    ]


WORKFLOWS: Dict[str, Callable[[str, Any, Any], Optional[List[Step]]]] = {
    'file.create_text': create_text,
    'code.bug_fix': bug_fix,
    'research.answer': research,
}
GOAL_VERIFIER = {'code.bug_fix': 'final_check', 'research.answer': 'check', 'file.create_text': 'check'}


def compile_goal(goal: str, journal: Any, config: Any, graph_version: int = 0) -> Optional[Plan]:
    for name, template in WORKFLOWS.items():
        steps = template(goal, journal, config)
        if steps:
            return Plan(goal_id='g-' + uuid.uuid4().hex[:16], goal=goal, workflow=name, steps=steps,
                        goal_verifier=GOAL_VERIFIER[name], answer_step='answer', graph_version=graph_version,
                        deadline_s=1800 if name == 'code.bug_fix' else 600)
    return None
