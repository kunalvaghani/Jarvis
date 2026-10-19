"""AZR-style proposer with learnability scoring, using local models only (Pillar D).

The proposer (default local ``qwen3.5:9b``) writes a *task*, never an answer: a deduction scenario
(initial state + calls) or an induction program with inputs. The independent oracle then validates
it and computes the answer: the simulation executes calls; induction programs are statically
screened and executed twice in the sandbox (AZR integrity, safety and determinism checks).
Learnability follows AZR: r_propose = 1 - mean solve rate over G solver rollouts, and 0 when
the task is never or always solved. Proposals that fail validation receive the AZR format
penalty (-1) and are kept only in the rejection log, never in a dataset.
"""
import json
import random
import urllib.request

from .azr_tasks import (APPS, TOOLS, canonical, check_abduction, check_deduction, execute, extract_code, parse_json_answer,
                        render_prompt, screen_program, with_dependencies)

OLLAMA = 'http://127.0.0.1:11434/api/generate'


def ollama(model, prompt, temperature=0.0, seed=0, num_predict=512, system=None, timeout=600):
    body = {'model': model, 'prompt': prompt, 'stream': False, 'think': False,
            'options': {'temperature': temperature, 'seed': seed, 'num_predict': num_predict}}
    if system:
        body['system'] = system
    request = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())['response']


PROPOSE_DEDUCTION = ('Propose one new practice scenario for a simulated computer. Reply with JSON only: '
                     '{"initial": {"files": {"folder/name.txt": "short text"}, "apps": [], "clipboard": ""}, '
                     '"calls": [{"id": "s1", "tool": "...", "args": {...}}]}. Use 2-6 calls with these tools and exact '
                     'argument names: ' + ', '.join(f'{name}({", ".join(spec[0])})' for name, spec in TOOLS.items()) +
                     '. Apps must be among: ' + ', '.join(APPS) + '. Paths are short like docs/notes.txt. '
                     'Make it tricky but unambiguous. Earlier examples: {references}')
PROPOSE_INDUCTION = ('Propose one small pure Python function f(x) and 8 different inputs for it. x is a list of integers '
                     'or a short string. No imports, no while loops, no randomness. Reply with JSON only: '
                     '{"message": "one-line description", "source": "def f(x):\\n    ...", "inputs": [...]}. '
                     'Earlier examples: {references}')


def validate_deduction(proposal):
    """Oracle validation: schema, tools, then execute; the answer is computed, never taken from the model."""
    initial = proposal.get('initial')
    calls = proposal.get('calls')
    if not isinstance(initial, dict) or not isinstance(calls, list) or not 1 <= len(calls) <= 8:
        raise ValueError('schema')
    files = initial.get('files', {})
    if (not isinstance(files, dict) or len(files) > 6 or any(not isinstance(k, str) or not isinstance(v, str)
                                                           or len(k) > 60 or len(v) > 120 for k, v in files.items())):
        raise ValueError('files')
    apps = initial.get('apps', [])
    if not isinstance(apps, list) or any(a not in APPS for a in apps):
        raise ValueError('apps')
    state = canonical({'files': files, 'apps': apps, 'clipboard': str(initial.get('clipboard', ''))[:120]})
    clean = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict) or call.get('tool') not in TOOLS or not isinstance(call.get('args'), dict):
            raise ValueError('call')
        if set(call['args']) != set(TOOLS[call['tool']][0]) or not all(isinstance(v, str) and len(v) <= 120
                                                                        for v in call['args'].values()):
            raise ValueError('arguments')
        clean.append({'id': f's{index + 1}', 'tool': call['tool'], 'args': call['args']})
    first = execute(state, clean)
    if execute(state, clean) != first:
        raise ValueError('nondeterministic')
    return {'mode': 'deduction', 'seed': None, 'initial': state, 'calls': clean, 'answer': first}


def abduction_from(deduction):
    """A deduction scenario that runs to completion also yields an abduction task (desired = final state)."""
    if deduction['answer']['halted']:
        return None
    desired = {k: deduction['answer'][k] for k in ('files', 'apps', 'clipboard')}
    if desired == deduction['initial']:
        return None
    plan = with_dependencies([{**c, 'deps': []} for c in deduction['calls']])
    task = {'mode': 'abduction', 'seed': None, 'initial': deduction['initial'], 'desired': desired, 'reference_plan': plan}
    if not check_abduction(task, json.dumps(plan))['correct']:
        return None
    return task


def validate_induction(proposal, base, run_programs):
    source = proposal.get('source')
    inputs = proposal.get('inputs')
    message = str(proposal.get('message', ''))[:160]
    if not isinstance(source, str) or not isinstance(inputs, list) or not 6 <= len(inputs) <= 12:
        raise ValueError('schema')
    screen_program(source)
    if any(not (isinstance(v, str) and len(v) <= 60 or isinstance(v, list) and len(v) <= 10
                and all(type(i) is int and -10 ** 6 < i < 10 ** 6 for i in v)) for v in inputs):
        raise ValueError('inputs')
    unique = list({json.dumps(v): v for v in inputs}.values())
    # Outputs come from sandboxed execution (twice), not from the proposer.
    probe = run_programs(base, [{'id': 'probe', 'source': source, 'cases': [{'input': v, 'output': None} for v in unique]}])
    row = probe['probe']
    if row.get('error') or not row.get('cases') or not row.get('deterministic', True):
        raise ValueError('execution failed: ' + str(row.get('error') or row.get('screen')))
    return {'program': source, 'message': message, 'inputs': unique}


class Proposer:
    def __init__(self, base, proposer='qwen3.5:9b', solver='qwen3.5:0.8b', rollouts=4, seed=0):
        self.base, self.proposer, self.solver, self.rollouts = base, proposer, solver, rollouts
        self.rng = random.Random(seed)
        self.rejections = []

    def learnability(self, task):
        """AZR: r_propose = 0 if mean solve rate is 0 or 1, else 1 - mean solve rate (G solver rollouts)."""
        from .azr_tasks import SYSTEM
        solved = []
        for rollout in range(self.rollouts):
            text = ollama(self.solver, render_prompt(task), temperature=.7, seed=1000 + rollout, num_predict=600, system=SYSTEM)
            check = check_deduction(task, text) if task['mode'] == 'deduction' else check_abduction(task, text)
            solved.append(bool(check['correct']))
        rate = sum(solved) / len(solved)
        return {'solve_rate': rate, 'r_propose': 0.0 if rate in (0.0, 1.0) else round(1 - rate, 4), 'rollouts': len(solved)}

    def propose_deduction(self, references):
        prompt = PROPOSE_DEDUCTION.replace('{references}', json.dumps(references[:2]))
        text = ollama(self.proposer, prompt, temperature=.8, seed=self.rng.randint(1, 10 ** 6), num_predict=700)
        try:
            task = validate_deduction(parse_json_answer(text))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            self.rejections.append({'mode': 'deduction', 'reason': str(exc)[:80], 'format_reward': -1})
            return None
        task['provenance'] = {'proposer': self.proposer, 'answer_source': 'deterministic simulation'}
        return task

    def propose_induction(self, references, run_programs, visible=4):
        prompt = PROPOSE_INDUCTION.replace('{references}', json.dumps(references[:2]))
        text = ollama(self.proposer, prompt, temperature=.8, seed=self.rng.randint(1, 10 ** 6), num_predict=500)
        try:
            proposal = parse_json_answer(text)
            checked = validate_induction(proposal, self.base, run_programs)
        except (ValueError, TypeError, KeyError, AttributeError, SyntaxError, RuntimeError) as exc:
            self.rejections.append({'mode': 'induction', 'reason': str(exc)[:80], 'format_reward': -1})
            return None
        # Execute once more in the sandbox to obtain outputs (never trusting the proposer).
        rows = run_programs(self.base, [{'id': 'outputs', 'source': checked['program'],
                                          'cases': [{'input': v, 'output': None} for v in checked['inputs']]}])
        if rows['outputs'].get('error'):
            self.rejections.append({'mode': 'induction', 'reason': 'output pass failed', 'format_reward': -1})
            return None
        outputs = [case.get('output') for case in rows['outputs']['cases']]
        if len(outputs) != len(checked['inputs']) or any(o is None for o in outputs):
            self.rejections.append({'mode': 'induction', 'reason': 'non-JSON output', 'format_reward': -1})
            return None
        cases = [{'input': v, 'output': o} for v, o in zip(checked['inputs'], outputs)]
        return {'mode': 'induction', 'seed': None, 'family': 'proposed', 'k': None, 'message': checked['message'],
                'visible': cases[:visible], 'hidden': cases[visible:], 'reference_source': extract_code(checked['program']),
                'provenance': {'proposer': self.proposer, 'answer_source': 'sandbox execution (twice) of the proposed program'}}
