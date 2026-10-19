"""EEVEE-style router/prompt co-evolution for ``jarvis.prompt_router`` (Pillar C, Part C).

Follows the method described in EEVEE (arXiv 2606.11182; Princeton-AI2-Lab/EEVEE, Apache-2.0):
alternate a router phase (prompts fixed) and a prompt phase (router fixed); split the training
partition into a mini-batch half and a validation half; anneal router scoring from
consistency/balance toward accuracy; keep a per-example Pareto front of slot prompts and an
empty-prompt floor (a prompt must beat no prompt). No EEVEE code is copied.

Only the train split (``evolution_eval/train``) is used here. Winners become archive
candidates that the sealed gate re-tests on held-out data; nothing here edits production.
"""
import json
import math
import random
import urllib.request

from .evolution_surfaces import SURFACES, UNSAFE_TEXT, validate
from .prompt_router import ROUTER, SLOT_PROMPTS, SLOTS, route

REFLECTION_LIBRARY = {
    'tool_selection': ('Prefer the dedicated API or adapter tool named for the task over generic UI tools.',
                       'Choose the tool whose name matches the object being changed (file, cell, track, repository).',
                       'Generic input tools such as scroll or type_text are a last resort.'),
    'planning': ('Order steps so prerequisites come first and verify each result before the next step.',),
    'coding': ('Read the relevant files and tests first, change the smallest unit, then run the tests.',),
    'ui_automation': ('Use structured controls by name before coordinates and confirm the window changed.',),
    'knowledge': ('Answer from retrieved sources and say when a source is missing.',),
    'error_recovery': ('Inspect the current state before retrying and never repeat an uncertain write.',),
}


def halves(cases):
    """EEVEE reserves half of the training partition for validation."""
    return cases[0::2], cases[1::2]


def router_score(weights, cases, alpha):
    """Annealed objective: alpha * accuracy + (1 - alpha) * slot-balance (normalized entropy)."""
    routed = [route(case['goal'], weights=weights) for case in cases]
    accuracy = sum(r == case['slot'] for r, case in zip(routed, cases)) / len(cases)
    counts = [routed.count(slot) for slot in SLOTS if routed.count(slot)]
    total = sum(counts)
    entropy = -sum(c / total * math.log(c / total) for c in counts) / math.log(len(SLOTS)) if total else 0.
    return alpha * accuracy + (1 - alpha) * entropy, accuracy


def ollama_solver(model, url='http://127.0.0.1:11434/api/generate', timeout=120):
    """Local-only solver for multiple-choice cases; temperature 0 and a fixed seed."""
    def solve(prompt, case):
        question = case['question'] + '\n' + '\n'.join(f'{k}) {v}' for k, v in case['choices'].items()) + '\nAnswer:'
        body = json.dumps({'model': model, 'system': prompt or 'Answer with a single letter.', 'prompt': question,
                           'stream': False, 'think': False, 'options': {'temperature': 0, 'seed': 7, 'num_predict': 8}}).encode()
        request = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = json.loads(response.read())['response'].strip().upper()
        return next((ch for ch in text if ch in case['choices']), '') == case['answer']
    return solve


def ollama_reflector(model, url='http://127.0.0.1:11434/api/generate', timeout=300):
    """Local-model reflection: one short guidance sentence from failed train examples (no private data)."""
    def reflect(slot, current, failures):
        shown = '\n'.join(f"- {f['question']} (correct: {f['choices'][f['answer']]})" for f in failures[:4])
        prompt = (f'You write one short instruction (under 40 words) that helps a small model choose the right tool. '
                  f'Current instruction: "{current}". Questions it got wrong:\n{shown}\n'
                  'Reply with only the improved instruction.')
        body = json.dumps({'model': model, 'prompt': prompt, 'stream': False, 'think': False,
                           'options': {'temperature': 0, 'seed': 11, 'num_predict': 80}}).encode()
        request = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = json.loads(response.read())['response'].strip().strip('"')
        return ' '.join(text.split())[:600]
    return reflect


class PromptCoEvolution:
    def __init__(self, research, solver=None, reflect=None, rng=None):
        self.research = research
        self.solver = solver
        self.reflect = reflect
        self.rng = rng or random.Random(0)

    # ---- router phase (prompts fixed) --------------------------------------------------------------------------------
    def router_phase(self, rounds=12):
        cases = self.research.gate.data('prompt_routing', 'train')['cases']
        batch, validation = halves(cases)
        best = dict(ROUTER)
        best_score, _ = router_score(best, validation, 1.)
        history = []
        bounds = SURFACES['prompt_router']['bounds']
        for step in range(rounds):
            alpha = .5 + .5 * step / max(1, rounds - 1)  # anneal from balance toward accuracy
            candidate = dict(best)
            key = self.rng.choice(sorted(bounds))
            _, low, high = bounds[key]
            candidate[key] = round(min(high, max(low, candidate[key] + (high - low) * self.rng.choice([-.1, .1, -.2, .2]))), 4)
            validate('prompt_router', candidate)
            mini, _ = router_score(candidate, batch, alpha)
            parent_mini, _ = router_score(best, batch, alpha)
            if mini < parent_mini:
                history.append({'step': step, 'key': key, 'accepted': False, 'reason': 'mini-batch'})
                continue
            score, accuracy = router_score(candidate, validation, 1.)
            accepted = score > best_score
            history.append({'step': step, 'key': key, 'value': candidate[key], 'validation_accuracy': accuracy,
                            'accepted': accepted})
            if accepted:
                best, best_score = candidate, score
        return best, best_score, history

    # ---- prompt phase (router fixed) ---------------------------------------------------------------------------------
    def evaluate_prompt(self, prompt, cases):
        return [bool(self.solver(prompt, case)) for case in cases]

    def prompt_phase(self, slot, rounds=3):
        if self.solver is None:
            raise RuntimeError('Prompt evolution needs a solver (a local model); report as BLOCKED when unavailable.')
        cases = [c for c in self.research.gate.data('prompt_slots', 'train')['cases'] if route(c['question']) == slot]
        if len(cases) < 2:
            return None, {'reason': 'too few routed train cases for slot ' + slot}
        batch, validation = halves(cases)
        floor = self.evaluate_prompt('', validation)  # empty-prompt floor
        front = [('', floor)]
        current = SLOT_PROMPTS.get(slot, '')
        history = []
        library = list(REFLECTION_LIBRARY.get(slot, ()))
        for step in range(rounds):
            outcomes = self.evaluate_prompt(current, batch)
            failures = [case for case, ok in zip(batch, outcomes) if not ok]
            proposal = None
            if self.reflect is not None and failures:
                try:
                    proposal = self.reflect(slot, current, failures)
                except Exception as exc:
                    history.append({'step': step, 'reflection_error': type(exc).__name__})
            if not proposal and library:
                proposal = (current + ' ' + library.pop(0)).strip()
            if not proposal or UNSAFE_TEXT.search(proposal) or not proposal.isascii():
                history.append({'step': step, 'rejected': 'unsafe, empty or non-ASCII proposal'})
                continue
            scores = self.evaluate_prompt(proposal, validation)
            beats_floor = sum(scores) > sum(floor)
            dominated = any(all(a >= b for a, b in zip(other, scores)) and other != scores for _, other in front)
            history.append({'step': step, 'prompt': proposal, 'validation_correct': sum(scores), 'floor': sum(floor),
                            'beats_empty_floor': beats_floor, 'dominated': dominated})
            if beats_floor and not dominated:
                front = [(p, s) for p, s in front if not (all(a >= b for a, b in zip(scores, s)) and scores != s)]
                front.append((proposal, scores))
                current = proposal
        best = max((p for p in front if p[0]), key=lambda item: sum(item[1]), default=None)
        return (best[0] if best else None), {'history': history, 'front': [{'prompt': p, 'correct': sum(s)} for p, s in front],
                                             'cases': len(cases)}

    # ---- hand winners to the gate ------------------------------------------------------------------------------------
    def submit(self, surface, values, statement, cancelled=lambda: False):
        research = self.research
        validate(surface, values)
        seed = research.seed(surface)
        from .evolution_surfaces import digest, distance
        if research.archive.diversity(surface, values, distance) == 0:
            return {'decision': 'duplicate', 'reason': 'already archived'}
        identifier = research.archive.add(surface, values, digest(values), seed['source_commit'], seed['id'],
                                          'eevee_' + surface, {'from': seed['values'], 'to': values}, [SURFACES[surface]['file']],
                                          statement, 'running', None, research.gate.environment())
        return research.evaluate_candidate(identifier, seed, cancelled)
