"""JCAE decisions: what (if anything) to do about an attended problem, and learning from what happened.

Q(a) = ExpectedBenefit - ExecutionCost - InterruptionCost - RiskCost, maximised over the
actions this layer is *allowed* to take. 'ignore' (Q = 0) is always allowed, so silence
wins whenever nothing is clearly worth doing. Allowed actions never include an effectful
command: the most this layer can do on its own is submit a read-only investigation to the
existing scheduler. Everything else is a suggestion the user accepts through the normal
command path, where existing approvals still apply.
"""
import math
import time
from .awareness_model import entropy

ACTIONS = ('ignore', 'remember', 'monitor', 'investigate', 'notify_silent', 'speak', 'ask', 'request_approval',
           'execute_authorized')
AUTONOMY = ('observe', 'suggest', 'investigate')
# Fraction of a problem's value each response can realise; tunable heuristics, not measured constants.
EFFECT = {'ignore': 0., 'remember': .05, 'monitor': .12, 'investigate': .6, 'notify_silent': .3, 'speak': .45,
          'ask': .5, 'request_approval': .65, 'execute_authorized': .75}
EXECUTION = {'investigate': .08, 'execute_authorized': .1, 'monitor': .01, 'remember': .005}


class ExperienceEvaluator:
    """Beta(1,1) usefulness per (situation, response) plus versioned policy parameters with rollback."""

    def __init__(self, store, clock=time.time):
        self.store, self.clock = store, clock

    def mean(self, situation, action):
        useful, useless = self.store.experience(situation, action)
        return (useful + 1) / (useful + useless + 2), useful + useless

    def record(self, situation, action, useful, weight=1.):
        self.store.record_experience(situation, action, bool(useful), weight)
        self._track(useful)

    def feedback(self, suggestion, kind):
        """Explicit feedback is strong evidence for this situation only; a plain dismissal is weak evidence."""
        situation, action = suggestion['situation'], suggestion['action']
        if kind == 'helpful':
            self.record(situation, action, True, 1.)
        elif kind == 'wrong':
            self.record(situation, action, False, 1.)
        elif kind == 'dismissed':
            self.record(situation, action, False, .4)  # Busy now is not 'this was incorrect'.
        elif kind == 'reject_similar':
            self.record(situation, action, False, 1.)
            rejected = set(self.store.setting('rejected_situations', default=[]))
            rejected.add(situation)
            self.store.setting('rejected_situations', sorted(rejected))
        else:
            raise ValueError('Unknown feedback')

    def rejected(self, situation):
        return situation in set(self.store.setting('rejected_situations', default=[]))

    # --- versioned policy parameters ------------------------------------------------------------------------------
    def policy(self):
        versions = self.store.setting('policy_versions', default=None)
        if not versions:
            versions = [{'version': 1, 'at': self.clock(), 'params': {'attention_threshold': .45, 'interruption_scale': 1.},
                         'reason': 'initial heuristic', 'useful': 0, 'useless': 0}]
            self.store.setting('policy_versions', versions)
        return versions[-1]

    def _track(self, useful):
        versions = self.store.setting('policy_versions', default=None) or [self.policy()]
        versions[-1]['useful' if useful else 'useless'] += 1
        self.store.setting('policy_versions', versions)

    def adapt(self, min_samples=8):
        """Raise the bar after mostly-unhelpful interruptions, lower it after mostly-helpful ones.

        A new version that performs worse than its predecessor (with enough samples) is rolled back.
        """
        versions = self.store.setting('policy_versions', default=None) or [self.policy()]
        current = versions[-1]
        total = current['useful'] + current['useless']
        if len(versions) > 1 and total >= min_samples:
            previous = versions[-2]
            rate = current['useful'] / total
            old_total = previous['useful'] + previous['useless']
            if old_total >= min_samples and rate + .15 < previous['useful'] / old_total:
                versions.pop()
                versions[-1] = {**versions[-1], 'reason': versions[-1]['reason'] + '; restored after regression'}
                self.store.setting('policy_versions', versions)
                return 'rolled_back', versions[-1]
        if total < min_samples:
            return 'insufficient', current
        rate = current['useful'] / total
        params = dict(current['params'])
        if rate < .35:
            params['attention_threshold'] = min(.8, params['attention_threshold'] + .05)
            params['interruption_scale'] = min(2., params['interruption_scale'] * 1.2)
        elif rate > .7:
            params['attention_threshold'] = max(.3, params['attention_threshold'] - .03)
            params['interruption_scale'] = max(.6, params['interruption_scale'] * .9)
        else:
            return 'stable', current
        versions.append({'version': current['version'] + 1, 'at': self.clock(), 'params': params,
                         'reason': f'usefulness {rate:.0%} over {total:.0f} rated suggestions', 'useful': 0, 'useless': 0})
        self.store.setting('policy_versions', versions[-10:])
        return 'updated', versions[-1]


class ProactivePolicyEngine:
    def __init__(self, options, experience):
        self.options, self.experience = options or {}, experience
        self.autonomy = self.options.get('autonomy', 'investigate')
        if self.autonomy not in AUTONOMY:
            raise ValueError('awareness.autonomy must be observe, suggest or investigate')

    def allowed(self, problem, context):
        """Authorization is separate from salience. Anything outside this set cannot be chosen."""
        allowed = {'ignore', 'remember', 'monitor'}
        if context.get('stopped') or not context.get('proactive', True):
            return allowed
        if self.experience.rejected(problem['situation']):
            return allowed  # The user asked not to be told about this kind of situation again.
        allowed.add('notify_silent')
        if self.autonomy == 'observe':
            return allowed
        allowed |= {'speak', 'ask'}
        if problem.get('remedy') and not problem['remedy'].get('read_only'):
            allowed.add('request_approval')
        # Self-generated work never spawns more self-generated work (recursion guard).
        if self.autonomy == 'investigate' and problem.get('origin') != 'cognitive' and context.get('task_budget', 0) > 0:
            if problem.get('investigable') and not problem.get('handled'):
                allowed.add('investigate')
            if problem.get('remedy', {}).get('read_only') and problem['remedy'].get('authorized'):
                allowed.add('execute_authorized')
        # A routine choice is only offered when its 'investigate' branch would itself be allowed.
        if 'ask' in allowed and not (context.get('decisions') and 'investigate' in allowed):
            allowed.discard('ask')
        return allowed

    def evaluate(self, problem, context):
        value = problem['severity'] * (.4 + .6 * problem['relevance']) * (0. if problem.get('handled') else 1.)
        value *= problem.get('confidence', 1.)
        scale = context.get('interruption_scale', 1.)
        busy = .3 if context.get('user_active') else 0.
        blocked = context.get('quiet') or context.get('focus')
        pressure = context.get('resource_pressure', 0.)
        rows = []
        for action in self.allowed(problem, context):
            usefulness, samples = self.experience.mean(problem['situation'], action)
            benefit = value * EFFECT[action] * (2 * usefulness if samples >= 3 else 1.)
            if action == 'remember' and not problem.get('novel', True):
                benefit = 0.
            execution = EXECUTION.get(action, 0.) * (1 + 2 * pressure)
            interruption = {'speak': .3 + busy + (1. if blocked else 0.), 'ask': .25 + busy + (1. if blocked else 0.),
                            'request_approval': .25 + busy + (1. if blocked else 0.),
                            'notify_silent': .06 + (.08 if context.get('focus') else 0.)}.get(action, 0.) * scale
            risk = {'request_approval': .05, 'execute_authorized': .02, 'investigate': .01}.get(action, 0.)
            rows.append({'action': action, 'q': round(benefit - execution - interruption - risk, 4),
                         'benefit': round(benefit, 4), 'execution': round(execution, 4),
                         'interruption': round(interruption, 4), 'risk': risk})
        rows.sort(key=lambda r: (-r['q'], ACTIONS.index(r['action'])))
        return rows

    def choose(self, problem, context):
        rows = self.evaluate(problem, context)
        best = rows[0] if rows and rows[0]['q'] > 0 else {'action': 'ignore', 'q': 0.}
        return best, rows


def information_gain(p, sensitivity=.85, specificity=.85):
    """IG = H(b) - E[H(b | result)] for an investigation modelled as an imperfect binary test."""
    p = .5 if p is None else min(.999, max(.001, p))
    positive = p * sensitivity + (1 - p) * (1 - specificity)
    if positive <= 0 or positive >= 1:
        return 0.
    after_positive = p * sensitivity / positive
    after_negative = p * (1 - sensitivity) / (1 - positive)
    return max(0., entropy(p) - positive * entropy(after_positive) - (1 - positive) * entropy(after_negative))


class CuriosityEngine:
    """Bounded, goal-directed information gathering. Never unlimited experimentation."""

    def __init__(self, options=None, clock=time.time):
        options = options or {}
        self.weight = float(options.get('information_gain_weight', 1.))
        self.daily_budget = int(options.get('daily_budget', 12))
        self.threshold = float(options.get('threshold', .25))
        if self.daily_budget < 0 or self.daily_budget > 200:
            raise ValueError('awareness.curiosity.daily_budget must be 0-200')
        self.clock = clock
        self.spent = []
        self.paused = False

    def value(self, belief, goal_benefit, resource_cost, risk_cost):
        return self.weight * information_gain(belief) + goal_benefit - resource_cost - risk_cost

    def budget_left(self):
        now = self.clock()
        self.spent = [at for at in self.spent if now - at < 86400]
        return 0 if self.paused else max(0, self.daily_budget - len(self.spent))

    def choose(self, candidates, idle):
        """candidates: [{'id', 'belief', 'goal_benefit', 'resource_cost', 'risk_cost', 'goal_directed'}]."""
        if not self.budget_left():
            return None
        scored = []
        for row in candidates:
            if not row.get('goal_directed') and not idle:
                continue  # Undirected exploration only when the user is idle.
            value = self.value(row.get('belief'), row.get('goal_benefit', 0.), row.get('resource_cost', 0.), row.get('risk_cost', 0.))
            if value >= self.threshold:
                scored.append((value, row))
        if not scored:
            return None
        value, best = max(scored, key=lambda pair: pair[0])
        self.spent.append(self.clock())
        return {**best, 'exploration_value': round(value, 4)}


class MetacognitiveEvaluator:
    """Execution success, task success and goal success are recorded separately; they are not the same thing."""

    def assess(self, task, predicted_seconds=None, feedback=None):
        state, checkpoint = task['state'], task.get('checkpoint', {})
        execution = state in {'COMPLETED', 'PARTIAL'} if state in {'COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'} else None
        evidence = bool(checkpoint.get('effects') or checkpoint.get('tests') or
                        (checkpoint.get('task_result') or {}).get('verified'))
        task_success = True if state == 'COMPLETED' and evidence else False if state in {'FAILED', 'CANCELLED'} else None
        goal = {'helpful': True, 'wrong': False}.get(feedback)
        elapsed = checkpoint.get('elapsed_seconds')
        expensive = bool(predicted_seconds and elapsed and elapsed > 3 * predicted_seconds)
        misunderstood = bool(checkpoint.get('clarification') or checkpoint.get('relationship_question'))
        questions = []
        if task_success is None and execution:
            questions.append('Handler returned but no independent evidence verified the result')
        if expensive:
            questions.append(f'Took {elapsed:.0f}s against an estimate of {predicted_seconds:.0f}s')
        if misunderstood:
            questions.append('Needed clarification; the request may have been misunderstood')
        return {'execution_success': execution, 'task_success': task_success, 'goal_success': goal,
                'verified_evidence': evidence, 'expensive': expensive, 'questions': questions}

    @staticmethod
    def reflection_needed(failures, completed_workflow=False, important=False):
        """Expensive reflection only after repeated failures, important decisions or a finished multi-step goal."""
        return failures >= 3 or completed_workflow or important


def compose(problem, action, done=None):
    """A message built from the problem's own structured fields; observed, inferred and unknown stay distinct."""
    observed = [o for o in problem.get('observed', []) if o][:2]
    text = ' '.join(s[0].upper() + s[1:] + ('' if s.endswith('.') else '.') for s in observed)
    for statement, probability in problem.get('inferred', [])[:1]:
        qualifier = 'probably' if probability >= .8 else 'possibly' if probability >= .5 else 'unlikely but possible'
        text += f' That {qualifier} means {statement}.'
    if problem.get('uncertain'):
        text += ' I am not sure ' + problem['uncertain'][0].rstrip('.') + '.'
    if done:
        text += ' ' + done.rstrip('.') + '.'
    elif action in {'ask', 'request_approval', 'speak', 'notify_silent'} and problem.get('recommendation'):
        verb = {'ask': 'Would you like me to', 'request_approval': 'If you approve, I can'}.get(action, 'I can')
        text += f' {verb} {problem["recommendation"].rstrip(".")}' + ('?' if action == 'ask' else '.')
    return text.strip()
