"""Small, durable record of Jarvis's current task and verified progress.

This is an audit/checkpoint record, not an automatic action replay queue.
"""
from .paths import state_file
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from .experience import recall_tasks
from .task_graph import MAX_TASK_GOAL_CHARS


def _now():
    return datetime.now(timezone.utc).isoformat()


class TaskState:
    def __init__(self, base, *, read_only=False):
        self.on_finish = None
        self.read_only = read_only
        self.base = Path(base)
        self.path = state_file("task_state.json", self.base)
        self.lock = threading.RLock()
        self.data = self._read()
        current = self.data.get("current")
        if isinstance(current, dict) and current.get("status") == "running":
            current["status"] = "interrupted"
            current["updated_at"] = _now()
            current["result"] = "Jarvis stopped before this task was completed. Inspect the last checkpoint before retrying."
            self._write()

    def _read(self):
        if not self.path.is_file():
            return {"version": 1, "current": None, "history": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("history"), list):
                raise ValueError("Unsupported task state format")
            return data
        except (OSError, ValueError, TypeError):
            # Keep malformed state for inspection instead of silently overwriting it.
            raise ValueError(f"Cannot read task state in {self.path}; repair or move it before starting Jarvis.")

    def _write(self):
        if self.read_only:
            return  # Hidden UI verification must not mark a real running task interrupted.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".jarvis-task-", delete=False) as output:
            temporary = Path(output.name)
            json.dump(self.data, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        # Windows scanners/readers may briefly deny atomic replacement. Retry
        # only this known failed metadata commit, never the task/action or write.
        # If another writer changed the destination, or the source vanished,
        # preserve the pending checkpoint and stop rather than overwrite it.
        previous = self.path.read_bytes() if self.path.exists() else None
        for attempt in range(4):
            try:
                os.replace(temporary, self.path)
                return
            except PermissionError as exc:
                if getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 3:
                    raise
                if not temporary.is_file():
                    raise
                current = self.path.read_bytes() if self.path.exists() else None
                if current != previous:
                    raise
                time.sleep(.05 * (attempt + 1))

    def start(self, goal, kind, project=None):
        with self.lock:
            previous = self.data.get("current")
            if previous:
                if previous.get("status") == "running":
                    previous["status"] = "interrupted"
                    previous["result"] = "A newer task replaced this task."
                    previous["updated_at"] = _now()
                self.data["history"] = (self.data["history"] + [previous])[-20:]
            timestamp = _now()
            self.data["current"] = {"goal": goal[:MAX_TASK_GOAL_CHARS], "kind": kind, "project": str(project) if project else None,
                                    "task_id": uuid.uuid4().hex,
                                    "status": "running", "stage": "started", "started_at": timestamp,
                                    "updated_at": timestamp, "checkpoints": [], "result": ""}
            self._write()
            return self.data['current']['task_id']

    def identity(self):
        with self.lock:
            current=self.data.get('current') or {}
            return current.get('task_id') or current.get('started_at')

    def require_identity(self, expected):
        if not isinstance(expected,str) or not expected or self.identity()!=expected:
            raise ValueError('Task identity changed; unrelated execution refused.')

    def checkpoint(self, stage, *, action=None, target=None, evidence=None, screen=None, source=None):
        with self.lock:
            current = self.data.get("current")
            if not current or current.get("status") != "running":
                return
            item = {"at": _now(), "stage": stage}
            for key, value in (("action", action), ("target", target), ("evidence", evidence), ("screen", screen), ("source", source)):
                if value is not None:
                    item[key] = str(value)[:500]
            current["stage"] = stage
            current["updated_at"] = item["at"]
            current["checkpoints"] = (current["checkpoints"] + [item])[-30:]
            if stage in {'uncertain_external_write','external_write_verified'}:
                pending = current.setdefault('uncertain_external_writes', [])
                token = {'action':str(action or ''),'target':str(target or '')[:500]}
                if stage == 'uncertain_external_write' and token not in pending:
                    pending.append(token)
                elif stage == 'external_write_verified':
                    current['uncertain_external_writes'] = [row for row in pending if row!=token]
            self._write()

    def finish(self, status, result, *, task_id=None):
        with self.lock:
            current = self.data.get("current")
            if task_id is not None and (not current or current.get('task_id',current.get('started_at'))!=task_id):
                return False
            if not current or current.get("status") != "running":
                return
            if status not in {"completed", "paused", "cancelled", "failed"}:
                raise ValueError("Invalid task status")
            if status == 'completed' and current.get('uncertain_external_writes'):
                status = 'paused'
                result = 'Task paused: an external write is uncertain; inspect the actual result. No automatic replay.'
            current["status"] = status
            current["updated_at"] = _now()
            current["result"] = str(result)[:1000]
            self._write()
            if self.on_finish:
                self.on_finish(json.loads(json.dumps(current)))

    def update_plan(self, remaining, completed, reason=""):
        """Persist planning context only; this must never become a replay queue."""
        with self.lock:
            current = self.data.get("current")
            if not current or current.get("status") != "running":
                return
            revision = {"at": _now(), "reason": str(reason)[:500],
                        "remaining": json.loads(json.dumps(remaining)),
                        "completed": json.loads(json.dumps(completed[-40:]))}
            current["plan"] = revision
            current["plan_revisions"] = (current.get("plan_revisions", []) + [revision])[-12:]
            current["updated_at"] = revision["at"]
            self._write()

    def record_failure(self, failure):
        with self.lock:
            current = self.data.get("current")
            if not current or current.get("status") != "running":
                return
            current["failures"] = (current.get("failures", []) + [json.loads(json.dumps(failure))])[-12:]
            current["updated_at"] = _now()
            self._write()

    def update_dag(self, graph, steps, fingerprint, timings, *, task_id=None):
        """Task-owned DAG checkpoint, never an automatic effect replay queue."""
        with self.lock:
            if task_id is not None:self.require_identity(task_id)
            current = self.data.get('current')
            if not current or current.get('status') != 'running':
                return
            payload = {'version': 1, 'graph': graph, 'steps': steps,
                       'fingerprint': fingerprint, 'timings': timings}
            encoded = json.dumps(payload, allow_nan=False)
            if len(encoded) > 1100000:
                raise ValueError('DAG checkpoint exceeds its bounded state budget.')
            current['dag'] = json.loads(encoded)
            current['stage'] = 'dag_execution'
            current['updated_at'] = _now()
            self._write()

    def update_learning(self, payload):
        """Acquisition participates in the current task, not a separate state DB."""
        encoded = json.dumps(payload, allow_nan=False)
        if len(encoded) > 100000:
            raise ValueError('Learning checkpoint exceeds task budget.')
        with self.lock:
            current = self.data.get('current')
            if current and current.get('status') == 'running':
                current['learning'] = json.loads(encoded)
                current['updated_at'] = _now()
                self._write()

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.data.get("current")))

    def set_project(self, project):
        with self.lock:
            current = self.data.get("current")
            if current and current.get("status") == "running":
                current["project"] = str(project)
                self._write()

    def set_conditions(self, conditions):
        """Persist bounded initial observations, never reusable control identities."""
        from .experience_memory import CONDITION_KEYS
        with self.lock:
            current = self.data.get('current')
            if current and current.get('status') == 'running':
                current['conditions'] = {k: str(v)[:300] for k, v in conditions.items()
                                         if k in CONDITION_KEYS and isinstance(v, str)}
                self._write()

    def unfinished(self, automatic=False):
        with self.lock:
            current = self.data.get("current")
            candidates = [current] if automatic else [current, *reversed(self.data.get("history", []))]
            for task in candidates:
                if isinstance(task, dict) and task.get("kind") in {"task", "code_task"} and task.get("status") in (
                        {"interrupted"} if automatic else {"interrupted", "paused", "failed"}):
                    return json.loads(json.dumps(task))
            return None

    @staticmethod
    def resume_blocker(task):
        if task.get('uncertain_external_writes'):
            return 'An external write is uncertain. Inspect the actual result before continuing; no automatic replay is permitted.'
        dag = task.get('dag', {})
        if any(row.get('effect') and row.get('status') != 'succeeded'
               for row in dag.get('steps', {}).values()):
            return 'A DAG effect has an uncertain result. Inspect it before continuing; it cannot be replayed.'
        if any(row.get('effect') for row in dag.get('steps', {}).values()):
            return 'DAG effects were already dispatched. Inspect their current state and request only remaining work.'
        if any(item.get("attempted") for item in task.get("failures", [])):
            return "A previous action has an uncertain result. Inspect it before issuing the remaining task."
        uncertain = False
        for item in task.get("checkpoints", []):
            stage = item.get("stage")
            if stage in {"acting", "action_attempted", "uncertain_external_write"}:
                uncertain = True
            elif stage in {"verified", "external_write_verified"}:
                uncertain = False
            if stage in {"wrote_file", "observed_file"}:
                return "Project files were already changed. Inspect them and request the remaining edits."
        return "The last action was not verified; inspect its result before continuing." if uncertain else None

    def previous(self, goal, kind):
        """Return bounded context for the same unfinished goal, never executable steps."""
        with self.lock:
            history = self.data.get("history", [])
            if not history:
                return None
            task = history[-1]
            if (task.get("goal") != goal[:MAX_TASK_GOAL_CHARS] or task.get("kind") != kind
                    or task.get("status") not in {"paused", "failed", "interrupted", "cancelled"}):
                return None
            return {"status": task["status"], "stage": task.get("stage", ""),
                    "result": task.get("result", "")[:500],
                    "plan": task.get("plan"),
                    "failures": task.get("failures", [])[-12:],
                    "checkpoints": task.get("checkpoints", [])[-12:]}

    def recall(self, goal, kind="task"):
        """Read past verified successes without changing checkpoints or hit counts."""
        with self.lock:
            return recall_tasks(self.data.get("history", []), goal, kind)
