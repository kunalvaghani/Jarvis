"""Evidence-driven planning admission. No timers, model calls, or action replay."""
import hashlib
import json
import re
import time

from .task_recovery import action_key

STATES = frozenset({'UNDERSTAND', 'PLAN', 'EXECUTE', 'OBSERVE', 'VERIFY',
                    'REPLAN', 'COMPLETE', 'BLOCKED'})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def acceptance(goal):
    clauses = re.findall(r'^\s*\d+[.)]\s*(.+)$', goal, re.M)
    # The original objective is always retained: decomposition never replaces it.
    return [{'text': text[:6000], 'verified': False} for text in [goal, *clauses][:41]]


def literal_requirement(text):
    """Recognize only exact numbered file instructions; ambiguous clauses use the verifier."""
    name = r'([\w.-]+\.(?:txt|md|json|csv|tsv|yaml|yml|ini|toml|log))'
    for pattern, action, fields in (
        (r'Create (?:file )?' + name + r' containing (.+)', 'create_file', ('value', 'content')),
        (r'Modify (?:file )?' + name + r': replace (.+?) with (.+)', 'modify_file', ('value', 'find', 'content')),
        (r'Read (?:file )?' + name + r'\.?', 'read_file', ('value',))):
        match = re.fullmatch(pattern, text.strip(), re.I)
        if match:
            return {'action': action, **dict(zip(fields, match.groups()))}
    return None


class AdaptivePlanningController:
    def __init__(self, goal, persist=lambda value: None):
        self.persist = persist
        self.started = time.monotonic()
        self.ledger = {'version': 1, 'objective': goal, 'state': 'UNDERSTAND',
                       'acceptance': acceptance(goal), 'completed': [], 'remaining': [],
                       'evidence': [], 'blockers': [], 'decisions': [], 'requests': [],
                       'planning_cycles': 0, 'repeated_decisions': 0, 'plan_oscillations': 0,
                       'meaningful_changes': 0, 'model_seconds': 0.0,
                       'first_action_seconds': None, 'goal_verified': False}
        self._progress = digest([])
        self._plans = []
        self._verified = []
        self.save()

    def save(self):
        self.persist(self.ledger)

    def transition(self, state, reason):
        if state not in STATES:
            raise ValueError('Invalid adaptive planning state')
        self.ledger['state'] = state
        self.ledger['decisions'] = (self.ledger['decisions'] +
            [{'state': state, 'reason': reason[:200]}])[-40:]
        if state == 'EXECUTE' and self.ledger['first_action_seconds'] is None:
            self.ledger['first_action_seconds'] = time.monotonic() - self.started
        if state == 'BLOCKED':
            self.ledger['blockers'] = [reason[:500]]
        self.save()

    def progress(self, remaining, completed):
        verified = [row for row in completed if row.get('verified') is True
                    and row.get('confirmed', True) is not False]
        self._verified = verified
        fingerprint = digest([action_key(row) for row in verified])
        if fingerprint != self._progress:
            self.ledger['meaningful_changes'] += 1
            self.ledger['requests'] = []
            self._plans = []
            self._progress = fingerprint
        # Full arguments/results remain in TaskState.plan, not duplicated here.
        self.ledger['completed'] = [digest(action_key(row)) for row in verified]
        self.ledger['remaining'] = [digest(action_key(row)) for row in remaining]
        self.save()

    def admit(self, operation, data):
        context = {key: data.get(key) for key in ('goal', 'screen', 'completed',
                   'remaining', 'failures', 'plan_validation_error', 'last_result')}
        for field in ('completed', 'remaining', 'failures'):
            rows = context.get(field)
            if isinstance(rows, list):
                context[field] = [{'action': action_key(row), 'verified': row.get('verified') is True,
                                   'attempted': row.get('attempted') is True}
                                  for row in rows if isinstance(row, dict)]
        key = digest(context)  # Prompt wording/conversation growth is not new evidence.
        if key in self.ledger['requests']:
            self.ledger['repeated_decisions'] += 1
            self.transition('OBSERVE', 'Repeated planning context; fresh observation required')
            return False
        self.ledger['requests'] = (self.ledger['requests'] + [key])[-40:]
        self.ledger['planning_cycles'] += 1
        self.transition('PLAN' if operation == 'plan' else 'REPLAN',
                        'New evidence, dependency or correction context')
        return True

    def proposal(self, result, seconds):
        self.ledger['model_seconds'] += seconds
        if isinstance(result, dict) and isinstance(result.get('steps'), list):
            key = digest([action_key(row) for row in result['steps'] if isinstance(row, dict)])
            if len(self._plans) >= 2 and key == self._plans[-2] and key != self._plans[-1]:
                self.ledger['plan_oscillations'] += 1
            self._plans = (self._plans + [key])[-40:]
        self.save()

    def ready(self, remaining, completed, failures):
        """Only fully literal file chains qualify; UI/connector state needs reasoning.

        This is a relative-benefit rule: with verified prerequisites and explicit
        file operands, another global plan supplies no missing dispatch input.
        Normal scope validation, approvals, readback and final verification still run.
        """
        if not remaining or not completed or completed[-1].get('confirmed') is False:
            return False
        if completed[-1].get('verified') is not True:
            return False
        if any(row.get('action') not in {'create_file', 'modify_file', 'read_file'}
               or not row.get('value') or not row.get('folder') or not row.get('expected')
               or row.get('action') == 'modify_file' and not row.get('find')
               for row in remaining):
            return False
        forbidden = {action_key(row) for row in [*completed, *failures]}
        return not any(action_key(row) in forbidden for row in remaining)

    def verify_goal(self, evidence):
        if not evidence:
            raise ValueError('Whole-goal verification needs evidence')
        if self.ledger['remaining']:
            self.transition('BLOCKED', 'Verified goal conflicts with remaining work')
            return False
        position = 0
        for criterion in self.ledger['acceptance'][1:]:
            requirement = literal_requirement(criterion['text'])
            if requirement is None:
                continue
            found = next((index for index in range(position, len(self._verified))
                          if all(self._verified[index].get(key) == value for key, value in requirement.items())
                          and self._verified[index].get('confirmed', True) is not False), None)
            if found is None:
                self.transition('BLOCKED', 'A literal acceptance criterion has no matching verified action: ' + criterion['text'][:100])
                return False
            position = found + 1
        self.ledger['goal_verified'] = True
        self.ledger['blockers'] = []
        self.ledger['evidence'] = (self.ledger['evidence'] + [digest(evidence)])[-40:]
        for criterion in self.ledger['acceptance']:
            criterion['verified'] = True
        self.transition('COMPLETE', 'Fresh whole-goal verifier accepted the original objective')
        return True
