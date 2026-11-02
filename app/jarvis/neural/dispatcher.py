"""The durable dispatcher: signals fire neurons; every firing is journaled before it acts.

One goal runs as waves: every step whose inputs are ready fires (in parallel, up to four; steps that drive the
desktop share one lock). Each firing:

1. passes the hard gate again (eligibility can change while a goal runs);
2. asks the user once per approval scope when the neuron changes the world (denied = the goal stops);
3. claims its idempotency key in the outbox *before* acting: a key already done is reused, never re-run; a key
   left pending by a crash is replayed only for read-only neurons, otherwise the goal stops as ``uncertain``;
4. runs its adapter, stores outputs as artifacts, emits ``neuron.succeeded`` with references (not payloads).

A failed verifier sends its Verdict back to the producer it names (bounded by that producer's ``max_attempts``).
Every loop has a deadline, attempt limits and a stop reason. A goal is ``verified`` only when its goal-verifier
step passed; anything else is reported as what it is.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .contracts import Signal
from .execution import Plan, Step, check, plan_dict
from .journal import SecretPayload
from .policy import Context, eligibility

DESKTOP = threading.Lock()  # One hand on the mouse and keyboard at a time, across goals.
MAX_PARALLEL = 4


class NotStarted(Exception):
    """An adapter failed before it changed anything (safe to report as a plain failure)."""


class Stop(Exception):
    def __init__(self, state: str, reason: str) -> None:
        super().__init__(reason)
        self.state, self.reason = state, reason


@dataclass
class Env:
    """What adapters may use. ``approve(scope, summary)`` is the existing approval flow (never auto-yes)."""
    actions: Any = None
    cancelled: Callable[[], bool] = lambda: False
    approve: Callable[[str, str], bool] = lambda scope, summary: False
    config: Any = None
    approved: Set[str] = field(default_factory=set)
    notes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Outcome:
    goal_id: str
    state: str          # verified | failed | cancelled | refused | uncertain | blocked | denied | deadline
    stop_reason: str
    answer: str = ''
    verdict: Optional[Dict[str, Any]] = None
    steps: Dict[str, str] = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def verified(self) -> bool:
        return self.state == 'verified'


Adapter = Callable[[Any, Dict[str, Any], Env], Dict[str, Any]]


class Dispatcher:
    def __init__(self, graph: Any, journal: Any, adapters: Dict[str, Adapter]) -> None:
        self.graph, self.journal, self.adapters = graph, journal, adapters

    # Public -------------------------------------------------------------------------------------------------
    def run(self, plan: Plan, env: Env, resume: bool = False) -> Outcome:
        started = time.monotonic()
        problems = check(plan, self.graph)
        if problems:
            return Outcome(plan.goal_id, 'blocked', 'the plan does not fit the capability graph: ' + '; '.join(problems))
        state: Dict[str, str] = {s.step_id: 'waiting' for s in plan.steps}
        outputs: Dict[str, Dict[str, Any]] = {}
        attempts: Dict[str, int] = {s.step_id: 1 for s in plan.steps}
        feedback: Dict[str, Any] = {'__generation': 0}  # repairs so far: part of every idempotency key
        if resume:
            self._restore(plan, state, outputs, attempts, feedback)
        else:
            self.journal.open_goal(plan.goal_id, plan.goal, plan.graph_version, plan_dict(plan))
            self._emit(plan, 'goal.created', note=plan.workflow)
        env.notes.setdefault('started', time.time() - 1)
        ctx = Context(goal=plan.goal, config=env.config,
                      allowed_tools=getattr(env.actions, 'allowed_tools', None)
                      if isinstance(getattr(env.actions, 'allowed_tools', None), (set, frozenset)) else None)
        try:
            self._loop(plan, env, ctx, state, outputs, attempts, feedback, started)
            verdict = self._verdict(outputs.get(plan.goal_verifier))
            if not verdict or not verdict.get('passed'):
                raise Stop('failed', 'the goal check did not pass')
            answer = str((outputs.get(plan.answer_step) or {}).get('answer', ''))
            self.journal.close_goal(plan.goal_id, 'verified', 'goal verifier passed')
            self._emit(plan, 'goal.verified', evidence=tuple(verdict.get('evidence', [])[:10]))
            return self._learn(plan, env, Outcome(plan.goal_id, 'verified', 'goal verifier passed', answer, verdict,
                                                  dict(state), round(time.monotonic() - started, 2)))
        except Stop as stop:
            self.journal.close_goal(plan.goal_id, stop.state, stop.reason)
            self._emit(plan, 'goal.cancelled' if stop.state == 'cancelled' else 'goal.failed', note=stop.reason)
            last = self._verdict(outputs.get(plan.goal_verifier))
            return self._learn(plan, env, Outcome(plan.goal_id, stop.state, stop.reason, '', last, dict(state),
                                                  round(time.monotonic() - started, 2)))

    def _learn(self, plan: Plan, env: Env, outcome: Outcome) -> Outcome:
        try:
            from .learning import observe
            observe(self.journal, plan, outcome, env.notes.get('seconds'))
        except Exception:
            pass  # Learning is never allowed to change or break a goal's result.
        return outcome

    # Loop ---------------------------------------------------------------------------------------------------
    def _loop(self, plan: Plan, env: Env, ctx: Context, state: Dict[str, str], outputs: Dict[str, Dict[str, Any]],
              attempts: Dict[str, int], feedback: Dict[str, Any], started: float) -> None:
        waves = 0
        while state[plan.answer_step] != 'done':
            waves += 1
            if waves > 4 * len(plan.steps) * 5:
                raise Stop('failed', 'wave limit reached (a loop without progress)')
            if env.cancelled():
                raise Stop('cancelled', 'the user stopped the task')
            if time.monotonic() - started > plan.deadline_s:
                raise Stop('deadline', f'the {plan.deadline_s:.0f} s deadline passed')
            ready = [s for s in plan.steps if state[s.step_id] == 'waiting'
                     and all(state[p] == 'done' for p in plan.parents(s))]
            if not ready:
                raise Stop('failed', 'no step can run (a dependency failed)')
            for step in ready:
                state[step.step_id] = 'running'
            with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(ready))) as pool:
                futures = {s.step_id: pool.submit(self._fire, plan, s, env, ctx, outputs, attempts[s.step_id],
                                                  feedback.get(s.step_id), feedback['__generation'])
                           for s in ready}
                results: Dict[str, Any] = {}
                for step_id, future in futures.items():
                    try:
                        results[step_id] = future.result()
                    except Stop as stop:
                        state[step_id] = 'failed'
                        raise stop
                    except Exception as error:  # adapter failure that did not change anything
                        results[step_id] = error
            for step in ready:
                result = results[step.step_id]
                if isinstance(result, Exception):
                    if attempts[step.step_id] < step.max_attempts and self._read_only(step):
                        attempts[step.step_id] += 1
                        state[step.step_id] = 'waiting'
                        continue
                    state[step.step_id] = 'failed'
                    raise Stop('failed', f'{step.step_id} failed: {type(result).__name__}: {result}'[:400])
                outputs[step.step_id] = result
                state[step.step_id] = 'done'
                verdict = self._verdict(result)
                if verdict is not None and not verdict.get('passed'):
                    self._repair(plan, step, verdict, state, attempts, feedback, outputs)

    def _repair(self, plan: Plan, step: Step, verdict: Dict[str, Any], state: Dict[str, str],
                attempts: Dict[str, int], feedback: Dict[str, Any], outputs: Dict[str, Dict[str, Any]]) -> None:
        problems = '; '.join(str(p) for p in verdict.get('problems', [])[:3]) or 'no detail'
        producer = step.repairs
        if producer is None or attempts[producer] >= plan.step(producer).max_attempts:
            tries = attempts[producer] if producer else 1
            raise Stop('failed', f'{step.step_id} did not pass after {tries} attempt(s): {problems}'[:600])
        self._emit(plan, 'verification.failed', task_id=step.step_id, target=plan.step(producer).neuron,
                   note=f'repair attempt {attempts[producer] + 1}: {problems}'[:400])
        self._reset(plan, producer, verdict, state, attempts, feedback, outputs)

    @staticmethod
    def _reset(plan: Plan, producer: str, verdict: Dict[str, Any], state: Dict[str, str], attempts: Dict[str, int],
               feedback: Dict[str, Any], outputs: Dict[str, Dict[str, Any]]) -> None:
        attempts[producer] += 1
        feedback[producer] = verdict
        feedback['__generation'] += 1
        for step_id in [producer] + plan.descendants(producer):
            state[step_id] = 'waiting'
            outputs.pop(step_id, None)

    # One firing ---------------------------------------------------------------------------------------------
    def _fire(self, plan: Plan, step: Step, env: Env, ctx: Context, outputs: Dict[str, Dict[str, Any]],
              attempt: int, verdict: Optional[Dict[str, Any]], generation: int = 0) -> Dict[str, Any]:
        neuron = self.graph.neurons[step.neuron]
        gate = eligibility(neuron, ctx)
        if not gate.eligible:
            self._emit(plan, 'neuron.blocked', task_id=step.step_id, target=neuron.node_id,
                       note='; '.join(gate.reasons))
            raise Stop('blocked', f'{neuron.node_id} is not eligible: ' + '; '.join(gate.reasons))
        # Tool neurons run through ToolRegistry/Actions, whose own approval rules apply unchanged (legacy parity);
        # the brain asks itself only for its own neurons that change the world.
        if neuron.gated and neuron.kind != 'tool':
            scope = step.approval_scope or neuron.capability
            if scope not in env.approved:
                self._emit(plan, 'approval.needed', task_id=step.step_id, target=neuron.node_id, note=scope)
                if env.cancelled() or not env.approve(scope, f'{neuron.description} ({neuron.node_id})'):
                    self._emit(plan, 'approval.denied', task_id=step.step_id, target=neuron.node_id, note=scope)
                    raise Stop('denied', f'approval was not given for: {scope}')
                env.approved.add(scope)
                self._emit(plan, 'approval.granted', task_id=step.step_id, target=neuron.node_id, note=scope)
        key = f'{plan.goal_id}:{step.step_id}:{attempt}:{generation}'
        fired = Signal(type='neuron.fired', goal_id=plan.goal_id, task_id=step.step_id, target_node=neuron.node_id,
                       graph_version=plan.graph_version, attempt=attempt, max_attempts=max(attempt, step.max_attempts),
                       idempotency_key=key)
        prior = self.journal.claim(key, plan.goal_id, neuron.node_id, fired.event_id)
        if prior is not None:
            if prior['state'] == 'done' and prior['result_ref']:
                return self._load_bundle(prior['result_ref'])  # Already done before a restart: never twice.
            if not self._read_only(step):
                raise Stop('uncertain', f'{step.step_id} may have acted before a crash; not repeated '
                                        '(check the result, then ask again)')
        self.journal.emit(fired)
        inputs = {port: self._resolve(bind, outputs) for port, bind in step.bind.items()}
        if verdict is not None and any(p.name == 'verdict' for p in neuron.inputs):
            inputs['verdict'] = verdict
        adapter = self.adapters.get(neuron.node_id)
        if adapter is None:
            self.journal.settle(key, 'failed', detail='no adapter')
            raise Stop('blocked', f'{neuron.node_id} has no adapter yet')
        lock = DESKTOP if neuron.side_effect_class == 'ui_or_media_state' else None
        try:
            if lock is not None:
                lock.acquire()
            began = time.monotonic()
            try:
                result = adapter(neuron, inputs, env)
                env.notes.setdefault('seconds', {})[step.step_id] = round(time.monotonic() - began, 2)
            finally:
                if lock is not None:
                    lock.release()
        except NotStarted as error:
            self.journal.settle(key, 'failed', detail=str(error))
            self._emit(plan, 'neuron.failed', task_id=step.step_id, target=neuron.node_id, note=str(error))
            raise
        except Stop:
            self.journal.settle(key, 'failed', detail='stopped')
            raise
        except Exception as error:
            uncertain = not self._read_only(step)
            self.journal.settle(key, 'uncertain' if uncertain else 'failed', detail=f'{type(error).__name__}: {error}')
            self._emit(plan, 'neuron.failed', task_id=step.step_id, target=neuron.node_id,
                       note=f'{type(error).__name__}: {error}'[:300])
            if uncertain:
                raise Stop('uncertain', f'{step.step_id} failed after it may have acted: {error}'[:400])
            raise
        missing = [p.name for p in neuron.outputs if p.required and p.name not in result]
        if missing:
            self.journal.settle(key, 'failed', detail=f'missing outputs {missing}')
            raise NotStarted(f'{neuron.node_id} returned no {missing}')
        try:
            bundle = self.journal.put({port: self.journal.put(json.dumps(value, default=str), None)
                                       for port, value in result.items()}, 'bundle')
        except SecretPayload as error:
            self.journal.settle(key, 'failed', detail='secret in output')
            raise Stop('refused', f'{step.step_id} produced something that looks secret; it is not passed on') from error
        self.journal.settle(key, 'done', bundle)
        self.journal.emit(Signal(type='neuron.succeeded', goal_id=plan.goal_id, task_id=step.step_id,
                                 source_node=neuron.node_id, payload_ref=bundle, graph_version=plan.graph_version,
                                 causal_parent_event_id=fired.event_id, attempt=attempt,
                                 max_attempts=max(attempt, step.max_attempts), idempotency_key=key + ':ok'))
        verdict_out = self._verdict(result)
        if verdict_out is not None and verdict_out.get('passed'):
            self._emit(plan, 'verification.passed', task_id=step.step_id, target=neuron.node_id,
                       evidence=tuple(str(e)[:200] for e in verdict_out.get('evidence', [])[:5]))
        return result

    # Helpers ------------------------------------------------------------------------------------------------
    def _read_only(self, step: Step) -> bool:
        return bool(self.graph.neurons[step.neuron].side_effect_class == 'read_only')

    def _resolve(self, bind: Any, outputs: Dict[str, Dict[str, Any]]) -> Any:
        if bind.const is not None:
            text = self.journal.get(bind.const)
            return json.loads(text) if text is not None else None
        return outputs[bind.step][bind.port]

    def _load_bundle(self, ref: str) -> Dict[str, Any]:
        refs = json.loads(self.journal.get(ref) or '{}')
        return {port: json.loads(self.journal.get(r) or 'null') for port, r in refs.items()}

    @staticmethod
    def _verdict(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        verdict = (result or {}).get('verdict')
        return verdict if isinstance(verdict, dict) and 'passed' in verdict else None

    def _restore(self, plan: Plan, state: Dict[str, str], outputs: Dict[str, Dict[str, Any]],
                 attempts: Dict[str, int], feedback: Dict[str, Any]) -> None:
        """Rebuild a goal after a restart by replaying its signals in order: finished steps are not run again,
        and repairs happen exactly as they did (same attempts, same generation, same idempotency keys)."""
        for signal in self.journal.signals(plan.goal_id, limit=5000):
            step_id = signal.get('task_id')
            if step_id not in state:
                continue
            if signal['type'] == 'neuron.succeeded' and signal.get('payload_ref'):
                outputs[step_id] = self._load_bundle(signal['payload_ref'])
                state[step_id] = 'done'
            elif signal['type'] == 'verification.failed':
                producer = plan.step(step_id).repairs
                verdict = self._verdict(outputs.get(step_id))
                if producer is not None and verdict is not None:
                    self._reset(plan, producer, verdict, state, attempts, feedback, outputs)

    def _emit(self, plan: Plan, kind: str, task_id: Optional[str] = None, target: Optional[str] = None,
              note: str = '', evidence: Tuple[str, ...] = ()) -> None:
        self.journal.emit(Signal(type=kind, goal_id=plan.goal_id, task_id=task_id, target_node=target,  # type: ignore[arg-type]
                                 graph_version=plan.graph_version, note=note[:400], evidence_refs=evidence))


def resume_open_goals(dispatcher: Dispatcher, env_for: Callable[[Dict[str, Any]], Env]) -> List[Outcome]:
    """After a crash: continue every open goal from its journal (read-only steps replay, writes never do)."""
    done = []
    for row in dispatcher.journal.open_goals():
        if not row.get('plan'):
            continue
        try:
            plan = Plan.model_validate(json.loads(row['plan']))
        except ValueError:
            dispatcher.journal.close_goal(row['goal_id'], 'failed', 'the journaled plan no longer validates')
            continue
        done.append(dispatcher.run(plan, env_for(row), resume=True))
    return done
