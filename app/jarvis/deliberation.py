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
import re
import time
from datetime import datetime, timezone
from pathlib import Path

# Goal-text signals that make an action high-risk regardless of its command kind.
HIGH_RISK_TEXT = re.compile(
    r"\b(delete|erase|wipe|format|rm\s+-rf|drop\s+(?:table|database)|uninstall|deploy|release to prod|"
    r"production|push to (?:main|master|prod)|force[- ]push|pay|purchase|buy|transfer (?:money|funds)|"
    r"wire|invoice|credential|password|api[- ]?key|secret|private key|token|ssh key|disable (?:firewall|"
    r"antivirus|defender)|grant (?:access|permission)|chmod\s+777|overwrite everything|factory reset)\b",
    re.I)
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


class Deliberation:
    """The decision engine. One instance lives on Actions; it never acts on its own."""

    def __init__(self, actions, options=None):
        self.actions = actions
        self.options = options or {}
        self.enabled = self.options.get("enabled", True)
        self.assertiveness = self.options.get("assertiveness", "when_it_matters")
        self.voice_threshold = float(self.options.get("voice_confidence_threshold", 0.6))
        self.ask_min_risk = self.options.get("ask_min_risk", "high")
        self.max_alternatives = int(self.options.get("max_alternatives", 3))
        self.ledger_max = int(self.options.get("ledger_max", 500))
        self.timeout_seconds = float(self.options.get("timeout_seconds", 20))
        base = Path(getattr(actions, "base", "."))
        self.ledger_path = base / ".jarvis-runtime" / "deliberation" / "decisions.jsonl"
        self._by_id = {}

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
            reversible, external = True, False
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
            stats = getattr(cognition, "stats", {}) or {}
            task_stat = stats.get("task", {})
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
        value = model_confidence if isinstance(model_confidence, (int, float)) else 0.5
        value = max(0.0, min(1.0, float(value)))
        cognition = getattr(self.actions, "cognition", None)
        stats = getattr(cognition, "stats", {}) if cognition is not None else {}
        task_stat = (stats or {}).get("task", {})
        if task_stat.get("attempts", 0) >= 3:
            rate = task_stat.get("successes", 0) / max(1, task_stat.get("attempts", 1))
            value = 0.6 * value + 0.4 * rate
        if has_question:
            value -= 0.25
        if risk == "high":
            value -= 0.1
        return round(max(0.05, min(0.99, value)), 2)

    # --- opinion formation -----------------------------------------------------------------------------------------
    def form_opinion(self, goal, command, cancelled, exclude=None):
        """Return a structured opinion. Uses the local model; falls back to a heuristic."""
        risk = self.classify_risk(command)
        context = self._context(goal)
        model = self._model_opinion(goal, context, cancelled, exclude) if self.enabled else None
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
        prior = getattr(brain, "timeout_seconds", None)
        try:
            if isinstance(prior, (int, float)) and prior:
                brain.timeout_seconds = min(prior, self.timeout_seconds)
            result = brain.request("deliberate", cancelled, **data)
        except Exception:
            return None
        finally:
            if isinstance(prior, (int, float)):
                try:
                    brain.timeout_seconds = prior
                except Exception:
                    pass
        return result if isinstance(result, dict) else None

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
        if APPROVE.match(stripped):
            return {"verdict": "approve", "note": stripped}
        if VAGUE.match(stripped):
            return {"verdict": "vague", "note": stripped}
        if REJECT.match(stripped):
            return {"verdict": "reject", "note": stripped}
        return {"verdict": "refine", "note": stripped}

    # --- decision ledger (traceable record) ------------------------------------------------------------------------
    def record(self, opinion, decision, chosen, approval):
        entry = {
            "id": "dec_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "goal": opinion.get("goal", "")[:300],
            "recommendation": opinion.get("recommendation", "")[:300],
            "alternatives": [a.get("approach", "")[:120] for a in opinion.get("alternatives", [])],
            "confidence": opinion.get("confidence"),
            "risk": opinion.get("risk"),
            "chosen": (chosen or "")[:300],
            "approval": approval,
            "source": opinion.get("source"),
            "outcome": None,
        }
        self._append(entry)
        self._by_id[entry["id"]] = entry
        return entry["id"]

    def record_outcome(self, decision_id, ok, detail=""):
        if not decision_id:
            return
        self._append({"id": decision_id, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "outcome": {"ok": bool(ok), "detail": str(detail)[:300]}})

    def _append(self, entry):
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            if self.ledger_path.is_file():
                lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
            lines.append(json.dumps(entry, ensure_ascii=False))
            if len(lines) > self.ledger_max:
                lines = lines[-self.ledger_max:]
            tmp = self.ledger_path.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(self.ledger_path)
        except OSError:
            pass

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
