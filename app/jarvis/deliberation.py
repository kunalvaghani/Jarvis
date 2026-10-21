"""Jarvis's deliberation layer: independent reasoning, opinions and decisions.

A single shared decision engine wired at the central task choke point, rather than a
separate feature or a duplicated loop. For a non-trivial task it forms an evidence-based
opinion over the user's existing systems (cognition memory/reliability, skills, capability
routing), classifies risk, estimates confidence, and decides whether to simply proceed,
voice a brief recommendation, or propose-and-wait. It interprets conversational feedback
("go ahead" / "no, try something else" / "you decide") and keeps a traceable decision
ledger whose outcomes are fed back from the cognition loop.

Design constraints honoured here:
- Never blocks a turn: every model call is bounded and falls back to a heuristic opinion.
- Never fabricates confidence or memory: model claims are typed (fact/assumption/
  prediction/preference); unknown preferences are not asserted as fact.
- Never expands authority: high-risk actions still funnel through the existing single
  approval path; this layer advises and sequences, it does not grant permissions.
- "Speak up only when it matters": stays silent on simple/agreed low-risk work.
"""
import json
import math
import re
import time
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Goal-text signals that make an action high-risk regardless of its command kind.
HIGH_RISK_TEXT = re.compile(
    r"\b(delete|erase|wipe|format|rm\s+-rf|drop\s+(?:table|database)|uninstall|deploy|release to prod|"
    r"production|push to (?:main|master|prod)|force[- ]push|pay|purchase|buy|transfer (?:money|funds)|"
    r"wire|invoice|credential|password|api[- ]?key|secret|private key|token|ssh key|disable (?:firewall|"
    r"antivirus|defender)|grant (?:access|permission)|chmod\s+777|overwrite everything|factory reset)\b",
    re.I)
BULK_DESTRUCTIVE = re.compile(r'(?is)\b(?:delete|erase|wipe|format)\b.*\b(?:all|every|everything|and|then)\b')
MODERATE_RISK_TEXT = re.compile(
    r"\b(install|modify|edit|refactor|rename|move|overwrite|migrate|update|configure|commit|merge|"
    r"schedule|write to|change the)\b", re.I)
# A free-text task is "trivial" (skip deliberation) when it is a single obvious imperative.
TRIVIAL_TASK = re.compile(
    r"^(?:please\s+)?(?:open|launch|start|show|play|pause|resume|close|stop|mute|unmute|skip|"
    r"next|previous|volume|screenshot|what|who|when|where|how|why|tell me|read|list|search for)\b", re.I)

APPROVE = re.compile(
    r"^(?:yes|yep|yeah|yup|sure|ok|okay|k|fine|go ahead|go for it|do it|proceed|continue|sounds good|"
    r"that works|works for me|please do|go on|make it so|approved|let'?s do it|perfect|great)\b", re.I)
REJECT = re.compile(
    r"^(?:no|nope|nah|don'?t|do not|stop|cancel(?: that)?|not that|i don'?t (?:like|want)|"
    r"try (?:something|another)|something else|another (?:way|approach|option)|different|not quite|"
    r"i'?d rather not)\b", re.I)
VAGUE = re.compile(
    r"^(?:maybe|whatever(?: you (?:think|want))?|you (?:decide|choose|pick)|do what(?:'?s| is| ?ever)? best|"
    r"i (?:don'?t|dont) (?:know|care|mind)|up to you|your call|either(?: one)?|dunno|not sure|idk|surprise me)\b",
    re.I)


EXPLICIT_APPROVAL = re.compile(APPROVE.pattern + r"(?:[,.! ]*(?:please|thanks|thank you))?[.! ]*\Z", re.I)
RISKY_AMBIGUITY = re.compile(r"\b(?:maybe|perhaps|possibly|not sure|might|do not|don't|never)\b", re.I)


def execution_path(command, runtime=None, apps=None, resuming=False):
    """Select existing executors without inference, I/O or granting authority.

    REFLEX means a known grammar, not permission or verified completion. FAST
    uses the existing lightweight question/simple-task path. DEEP preserves
    planning quality, clarification and progress-aware recovery.
    """
    kind, goal = command.kind, (command.value or '').strip()
    if kind not in {'task', 'code_task', 'ask'}:
        return {'path': 'REFLEX', 'reason': 'registered_command'}
    if resuming or kind == 'code_task':
        return {'path': 'DEEP', 'reason': 'checkpoint_or_code'}
    if kind == 'ask':
        return {'path': 'FAST', 'reason': 'question'}
    if HIGH_RISK_TEXT.search(goal) or RISKY_AMBIGUITY.search(goal):
        return {'path': 'DEEP', 'reason': 'risk_or_ambiguity'}
    runtime = runtime if isinstance(runtime, dict) else {}
    try:
        if runtime.get('direct_execution', False):
            from .direct_execution import compile_steps
            from .brain import explicit_file_plan, explicit_command_plan
            if compile_steps(goal) or explicit_file_plan(goal) or explicit_command_plan(goal):
                return {'path': 'REFLEX', 'reason': 'exact_direct_workflow'}
        if runtime.get('fast_workflows', False):
            from .fast_workflows import compile_workflow
            if compile_workflow(goal, apps or {}):
                return {'path': 'REFLEX', 'reason': 'exact_fast_workflow'}
    except (ValueError, TypeError, KeyError):
        # Recognition is preparation only. Invalid/unknown inputs go through the
        # original validation/clarification path; no action has been attempted.
        return {'path': 'DEEP', 'reason': 'recognition_declined'}
    if len(goal) < 12 or TRIVIAL_TASK.match(goal):
        return {'path': 'FAST', 'reason': 'simple_task'}
    return {'path': 'DEEP', 'reason': 'open_ended_task'}


def ledger_text(value, limit=300):
    """Keep readback local and omit recognized private/credential text."""
    from .cloud_policy import SECRET, PRIVATE, PRIVATE_APP
    text = str(value or '')[:16384].encode('utf-8', errors='replace').decode('utf-8')
    return '[redacted]' if any(p.search(text) for p in (SECRET, PRIVATE, PRIVATE_APP)) else text[:limit]


def valid_opinion(value):
    if not isinstance(value, dict):
        return False
    required = {'understanding', 'recommendation', 'reasoning', 'question', 'confidence', 'agrees_with_user', 'alternatives', 'claims'}
    if not required <= set(value) or set(value) - required - {'model_used'}:
        return False
    if 'model_used' in value and (not isinstance(value['model_used'], str) or not 1 <= len(value['model_used']) <= 150):
        return False  # Worker envelope metadata is advisory and never grants authority.
    for key in ('understanding', 'recommendation', 'reasoning', 'question'):
        if not isinstance(value.get(key, ''), str) or len(value.get(key, '')) > 4000:
            return False
    number = value.get('confidence', .5)
    if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 1:
        return False
    if type(value.get('agrees_with_user', True)) is not bool:
        return False
    for key, allowed, maximum in [('alternatives', {'approach', 'pros', 'cons'}, 4),
                                  ('claims', {'text', 'type'}, 6)]:
        rows = value.get(key, [])
        if not isinstance(rows, list) or len(rows) > maximum:
            return False
        for row in rows:
            if not isinstance(row, dict) or set(row) != allowed or any(not isinstance(v, str) or len(v) > 4000 for v in row.values()):
                return False
            if key == 'claims' and row.get('type') not in {'fact', 'assumption', 'prediction', 'preference'}:
                return False
    return sum(len(value.get(k, '')) for k in ('understanding', 'recommendation', 'reasoning', 'question')) + sum(len(v) for key in ('alternatives','claims') for row in value[key] for v in row.values()) <= 65536


class Deliberation:
    """The decision engine. One instance lives on Actions; it never acts on its own."""

    def __init__(self, actions, options=None):
        self.actions = actions
        self.options = {} if options is None else dict(options)
        if type(self.options.get('enabled', True)) is not bool:
            raise ValueError('Deliberation enabled must be boolean.')
        if self.options.get('assertiveness', 'when_it_matters') not in {'when_it_matters', 'always', 'on_request'}:
            raise ValueError('Invalid deliberation assertiveness.')
        if self.options.get('ask_min_risk', 'high') not in {'low', 'moderate', 'high'}:
            raise ValueError('Invalid deliberation risk threshold.')
        for key, default, lower, upper in [('voice_confidence_threshold', .6, 0, 1), ('timeout_seconds', 20, .1, 120),
                                          ('max_alternatives', 3, 1, 10), ('ledger_max', 500, 1, 10000)]:
            value = self.options.get(key, default)
            if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError('Invalid deliberation setting: ' + key)
            if key in {'max_alternatives', 'ledger_max'} and type(value) is not int:
                raise ValueError('Deliberation count must be integer: ' + key)
        self.enabled = self.options.get("enabled", True)
        self.assertiveness = self.options.get("assertiveness", "when_it_matters")
        self.voice_threshold = float(self.options.get("voice_confidence_threshold", 0.6))
        self.ask_min_risk = self.options.get("ask_min_risk", "high")
        self.max_alternatives = int(self.options.get("max_alternatives", 3))
        self.ledger_max = int(self.options.get("ledger_max", 500))
        self.timeout_seconds = float(self.options.get("timeout_seconds", 20))
        base = Path(getattr(actions, "base", "."))
        self.ledger_path = base / ".jarvis-runtime" / "deliberation" / "decisions.jsonl"
        self.lock = threading.RLock()
        self.last_ledger_error = None
        self.failure_router = FailureRouter(base)  # Phase 5 recovery routing (no recursive escalation)

    def route_failure(self, task_id, failure, context=None):
        """Advisory recovery route for a failed step; the caller still enforces approvals and no-replay."""
        return self.failure_router.route(task_id, failure, context or {})

    # --- risk classification (single source of truth) --------------------------------------------------------------
    def classify_risk(self, command, prediction=None):
        """low | moderate | high, from the world model plus goal-text signals."""
        text = (getattr(command, "value", "") or "")
        kind = getattr(command, "kind", "") or ""
        if HIGH_RISK_TEXT.search(text):
            return "high"
        from .cognition import effect_of, APPROVAL_KINDS
        if kind in APPROVAL_KINDS:
            return "high"
        try:
            _, reversible, external = effect_of(kind)
        except Exception:
            reversible, external = False, False
        if external:
            return "high"
        if prediction is not None and (prediction.get("needs_approval") or prediction.get("reversible") is False):
            return "high"
        # A task/code_task is a planning container; its own reversibility is unknown, so risk
        # comes from the goal text (handled above) and defaults to moderate, not high.
        if kind in {"task", "code_task"}:
            return "moderate"
        if not reversible:
            return "high"
        if MODERATE_RISK_TEXT.search(text):
            return "moderate"
        return "low"

    def _risk_rank(self, risk):
        return {"low": 0, "moderate": 1, "high": 2}.get(risk, 1)

    # --- context + confidence --------------------------------------------------------------------------------------
    def _context(self, goal):
        """Evidence drawn from the systems Jarvis already has; never fabricated."""
        actions, context = self.actions, {}
        cognition = getattr(actions, "cognition", None)
        if cognition is not None:
            try:
                context["memory"] = cognition.recall(goal, 3)
            except Exception:
                pass
            task_stat = self._task_stat()
            if task_stat.get("attempts", 0) >= 3:
                context["task_reliability"] = round(
                    task_stat.get("successes", 0) / max(1, task_stat.get("attempts", 1)), 2)
        skills = getattr(actions, "skills", None)
        if skills is not None:
            try:
                guidance = skills.context(goal) or {}
                names = [r.get("name") for r in guidance.get("skills", []) if isinstance(r, dict)]
                if names:
                    context["relevant_skills"] = names[:4]
            except Exception:
                pass
        return context

    def _confidence(self, model_confidence, risk, has_question):
        """Blend the model's self-estimate with learned reliability and uncertainty penalties."""
        value = model_confidence if type(model_confidence) in (int, float) and math.isfinite(model_confidence) else 0.5
        value = max(0.0, min(1.0, float(value)))
        task_stat = self._task_stat()
        if task_stat.get("attempts", 0) >= 3:
            rate = task_stat.get("successes", 0) / max(1, task_stat.get("attempts", 1))
            value = 0.6 * value + 0.4 * rate
        if has_question:
            value -= 0.25
        if risk == "high":
            value -= 0.1
        return round(max(0.05, min(0.99, value)), 2)

    def _task_stat(self):
        from .cognition import Cognition
        cognition = getattr(self.actions, 'cognition', None)
        if isinstance(cognition, Cognition):
            return cognition.procedure_stats('task')
        stats = getattr(cognition, 'stats', {})
        return Cognition._stat(stats.get('task') if isinstance(stats, dict) else None)

    # --- opinion formation -----------------------------------------------------------------------------------------
    def form_opinion(self, goal, command, cancelled, exclude=None):
        """Return a structured opinion. Uses the local model; falls back to a heuristic."""
        if cancelled():
            raise ValueError('Deliberation cancelled.')
        if not isinstance(goal, str) or len(goal) > 16384:
            raise ValueError('Deliberation goal must be text of at most 16384 characters.')
        risk = self.classify_risk(command)
        context = self._context(goal)
        model = self._model_opinion(goal, context, cancelled, exclude) if self.enabled else None
        if cancelled():
            raise ValueError('Deliberation cancelled.')
        if model is None:
            return self._heuristic_opinion(goal, command, risk, context)
        question = (model.get("question") or "").strip()
        confidence = self._confidence(model.get("confidence"), risk, bool(question))
        alternatives = [a for a in model.get("alternatives", []) if isinstance(a, dict)][: self.max_alternatives]
        agrees = model.get("agrees_with_user")
        agrees = True if agrees is None else bool(agrees)
        return {
            "goal": goal,
            "understanding": (model.get("understanding") or "").strip() or goal,
            "recommendation": (model.get("recommendation") or "").strip(),
            "reasoning": (model.get("reasoning") or "").strip(),
            "alternatives": alternatives,
            "claims": [c for c in model.get("claims", []) if isinstance(c, dict)][:6],
            "confidence": confidence,
            "risk": risk,
            "agrees_with_user": agrees,
            "question": question,
            "source": "model",
        }

    def _model_opinion(self, goal, context, cancelled, exclude):
        brain = getattr(self.actions, "brain", None)
        if brain is None or not hasattr(brain, "request"):
            return None
        data = {"goal": goal, "context": context, "max_alternatives": self.max_alternatives}
        if exclude:
            data["rejected_approaches"] = list(exclude)[:5]
        try:
            result = brain.request("deliberate", cancelled, _timeout_seconds=self.timeout_seconds, **data)
        except Exception:
            return None
        return result if valid_opinion(result) else None

    def _heuristic_opinion(self, goal, command, risk, context):
        """Evidence-based opinion without the model: honest, minimal, never invented."""
        reasons = []
        if "task_reliability" in context:
            reasons.append("similar tasks have succeeded about "
                           + str(round(context["task_reliability"] * 100)) + "% of the time")
        if context.get("relevant_skills"):
            reasons.append("there is matching saved guidance (" + ", ".join(context["relevant_skills"]) + ")")
        # No question is injected for high risk: destructive/consequential actions are confirmed by
        # the existing single approval gate, not by a second question from this layer.
        return {
            "goal": goal,
            "understanding": goal,
            "recommendation": "",
            "reasoning": "; ".join(reasons),
            "alternatives": [],
            "claims": [],
            "confidence": self._confidence(0.5, risk, False),
            "risk": risk,
            "agrees_with_user": True,
            "question": "",
            "source": "heuristic",
        }

    # --- the decision: proceed / note / propose --------------------------------------------------------------------
    def decide(self, opinion):
        """Turn an opinion into an action decision, honouring 'speak up only when it matters'.

        High risk alone does NOT trigger a propose-and-wait: destructive/consequential actions
        are already gated by the single existing approval path, so adding a second confirmation
        here would duplicate approvals. Jarvis proposes-and-waits only when it has something to
        say — a genuine disagreement or a real ambiguity it cannot resolve itself.
        """
        risk, confidence = opinion["risk"], opinion["confidence"]
        if risk == 'high' and RISKY_AMBIGUITY.search(opinion.get('goal', '')):
            return {'propose': True, 'note': False, 'chosen': '', 'risk': risk, 'confidence': confidence,
                    'message': 'Please clarify the intended action and exact scope before I plan any consequential changes.'}
        if risk == 'high' and BULK_DESTRUCTIVE.search(opinion.get('goal','')):
            return {'propose':True,'note':False,'chosen':opinion.get('recommendation',''),
                'risk':risk,'confidence':confidence,'message':
                'This request includes bulk destructive changes. Review the scope and give explicit approval before I plan any action. Go ahead?'}
        disagrees = not opinion["agrees_with_user"] and bool(opinion["recommendation"])
        ambiguous = bool(opinion["question"])
        if self.assertiveness == "on_request":
            propose = ambiguous
            note = False
        elif self.assertiveness == "always":
            propose = ambiguous or disagrees
            note = (not propose) and bool(opinion["recommendation"])
        else:  # "when_it_matters" (default)
            propose = ambiguous or (disagrees and confidence >= self.voice_threshold)
            note = (not propose) and disagrees
        decision = {"propose": propose, "note": note, "message": "", "chosen": opinion["recommendation"],
                    "risk": risk, "confidence": confidence}
        if propose or note:
            decision["message"] = self._phrase(opinion, propose)
        return decision

    def _phrase(self, opinion, propose):
        """Adaptive, conversational — understanding / opinion / why / next, never a rigid template."""
        parts = []
        if opinion["recommendation"]:
            lead = "I'd recommend " if not opinion["agrees_with_user"] else "My plan: "
            parts.append(lead + opinion["recommendation"].rstrip("."))
        elif opinion["understanding"] and opinion["understanding"] != opinion["goal"]:
            parts.append("Here's how I read that: " + opinion["understanding"].rstrip("."))
        if opinion["reasoning"]:
            parts.append("because " + opinion["reasoning"].rstrip("."))
        alt = opinion["alternatives"][0] if opinion["alternatives"] else None
        if alt and alt.get("approach"):
            parts.append("an alternative is " + str(alt["approach"]).rstrip("."))
        text = ". ".join(p for p in parts if p).strip()
        if opinion["question"]:
            text = (text + ". " if text else "") + opinion["question"]
        elif propose:
            text = (text + ". " if text else "") + "Want me to go ahead with that?"
        return text[:600]

    # --- conversational feedback -----------------------------------------------------------------------------------
    def interpret_feedback(self, text):
        """approve | reject | vague | refine, from a reply to a pending recommendation."""
        stripped = (text or "").strip()
        if not stripped:
            return {"verdict": "refine", "note": stripped}
        if EXPLICIT_APPROVAL.fullmatch(stripped):
            return {"verdict": "approve", "note": stripped}
        if VAGUE.match(stripped):
            return {"verdict": "vague", "note": stripped}
        if REJECT.match(stripped):
            return {"verdict": "reject", "note": stripped}
        return {"verdict": "refine", "note": stripped}

    # --- decision ledger (traceable record) ------------------------------------------------------------------------
    def record(self, opinion, decision, chosen, approval):
        entry = {
            "id": "dec_" + uuid.uuid4().hex,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "goal": ledger_text(opinion.get("goal", "")),
            "recommendation": ledger_text(opinion.get("recommendation", "")),
            "alternatives": [ledger_text(a.get("approach", ""), 120) for a in opinion.get("alternatives", [])],
            "confidence": opinion.get("confidence") if type(opinion.get('confidence')) in (int,float) and math.isfinite(opinion['confidence']) else None,
            "risk": opinion.get("risk"),
            "chosen": ledger_text(chosen),
            "approval": approval,
            "source": opinion.get("source"),
            "outcome": None,
        }
        self._append(entry)
        return entry["id"]

    def record_outcome(self, decision_id, ok, detail=""):
        if not decision_id:
            return
        self._append({"id": decision_id, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "outcome": {"ok": bool(ok), "detail": ledger_text(detail)}})

    def _append(self, entry):
        with self.lock:
            self._append_locked(entry)

    def _append_locked(self, entry):
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            from collections import deque
            lines = deque(maxlen=self.ledger_max)
            if self.ledger_path.is_file():
                with self.ledger_path.open(encoding='utf-8') as existing:
                    for line in existing:
                        lines.append(line.rstrip('\n'))
            lines.append(json.dumps(entry, ensure_ascii=True, allow_nan=False))
            tmp = self.ledger_path.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(self.ledger_path)
            self.last_ledger_error = None
        except (OSError, ValueError) as exc:
            self.last_ledger_error = type(exc).__name__

    def decisions(self, limit=20):
        """Read back the most recent decisions for inspection/tests."""
        if not self.ledger_path.is_file():
            return []
        rows = []
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        return rows[-limit:]


# ---- Phase 5: failure classification and recovery routing -------------------------------------------------------------
FAILURE_PATTERNS = (
    ('permission', r'approval|denied|permission|not authori[sz]ed|risky|unsafe|not allowed|refused by (?:policy|the user)'),
    ('missing_tool', r'unsupported tool|tool is outside|not registered|no (?:api|structured) (?:or structured )?method|'
                     r'configure environment|tool unavailable|is not installed|no tool'),
    ('planner_structure', r'\bdag\b|plan rejected|plan validation|invalid plan|schema|exceeds .*budget|steps must|cycle in'),
    ('unknown_ui', r'not found|could not find|cannot find|no (?:visible|named|such) (?:control|button|element|field)|'
                   r'belongs to another control|covers the target|selector is not unique'),
    ('reasoning', r'wrong|incorrect|test(?:s)? failed|does not match|did not match|verification failed|'
                  r'no progress|unexpected (?:result|output)'),
)
ROUTES = {'missing_tool': 'pillar_a_capability_discovery', 'broken_skill': 'pillar_a_fix', 'unknown_ui': 'show_me_once',
          'reasoning': 'local_replan_then_cloud_architect', 'planner_structure': 'pillar_c_evidence',
          'permission': 'stop_request_authorization', 'unknown': 'stop_request_guidance'}
MAX_ESCALATIONS_PER_TASK = 3


def classify_failure(text, context):
    """Deterministic category for a failure reason; a degraded skill outranks generic text."""
    if context.get('skill_degraded'):
        return 'broken_skill'
    lowered = str(text).casefold()
    for category, pattern in FAILURE_PATTERNS:
        if re.search(pattern, lowered):
            return category
    return 'unknown'


class FailureRouter:
    """Routes failures to recovery paths without recursion: one use of each route per task, three escalations max."""

    def __init__(self, base):
        self.root = Path(base) / '.jarvis-runtime' / 'learning-queues'
        self.lock = threading.Lock()
        self.history = {}           # task_id -> routes already taken
        self.weakness = {}          # goal class -> count of reasoning failures
        self.evidence = {}          # task_id -> failure evidence for cloud-architect eligibility (no raw text)
        self.latest_task = None

    @staticmethod
    def evidence_row(category, failure, reason):
        """Generic evidence: a strategy fingerprint, whether the failure is verified, and its cause class."""
        import hashlib
        strategy = hashlib.sha256(json.dumps([str(failure.get('action', '')), str(failure.get('value', ''))]).encode()).hexdigest()[:12]
        verified = failure.get('outcome') == 'not_executed' or bool(re.search(r'verif|test(?:s)? failed|does not match', reason, re.I))
        if category == 'reasoning':
            cause = 'test_failed' if re.search(r'test', reason, re.I) else (
                'verification_failed' if re.search(r'verif', reason, re.I) else 'wrong_output')
        else:
            cause = {'planner_structure': 'plan_invalid', 'permission': 'permission_denied', 'missing_tool': 'tool_unavailable',
                     'unknown_ui': 'tool_unavailable', 'broken_skill': 'tool_unavailable'}.get(category, 'unknown')
        return {'strategy': strategy, 'verified_failure': verified, 'cause': cause, 'category': category}

    def evidence_for(self, task_id=None):
        with self.lock:
            return list(self.evidence.get(str(task_id if task_id is not None else self.latest_task), []))

    def _queue(self, name, row):
        from .reasoning_bank import generic
        self.root.mkdir(parents=True, exist_ok=True)
        clean = {k: generic(v, 300) if isinstance(v, str) else v for k, v in row.items()}
        with (self.root / name).open('a', encoding='utf-8') as output:
            output.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), **clean},
                                    ensure_ascii=False) + '\n')

    def route(self, task_id, failure, context):
        reason = str((failure or {}).get('reason', ''))[:500]
        category = classify_failure(reason, context or {})
        route = ROUTES[category]
        with self.lock:
            taken = self.history.setdefault(str(task_id), [])
            decision = {'category': category, 'route': route, 'escalations': len(taken), 'training_candidate': False}
            rows = self.evidence.setdefault(str(task_id), [])
            rows.append(self.evidence_row(category, failure or {}, reason))
            del rows[:-20]
            self.latest_task = str(task_id)
            decision['distinct_verified_reasoning_failures'] = len(
                {r['strategy'] for r in rows if r['verified_failure'] and r['cause'] in
                 {'wrong_output', 'test_failed', 'plan_invalid', 'no_progress', 'verification_failed'}})
            if category != 'permission' and len(taken) >= MAX_ESCALATIONS_PER_TASK:
                decision.update(route='stop_request_guidance', reason='escalation limit reached for this task')
            elif category != 'permission' and route in taken:
                decision.update(route='stop_request_guidance', reason='this recovery route was already tried for this task')
            taken.append(decision['route'])
            if category == 'planner_structure':
                self._queue('planner-failures.jsonl', {'task_id': str(task_id)[:64], 'reason': reason})
            if category == 'reasoning':
                goal_class = str((context or {}).get('goal_class', 'general'))[:40]
                self.weakness[goal_class] = self.weakness.get(goal_class, 0) + 1
                if self.weakness[goal_class] >= 3:
                    decision['training_candidate'] = True
                    self._queue('training-candidates.jsonl', {'goal_class': goal_class, 'reason': reason,
                                                              'count': self.weakness[goal_class]})
        return decision
