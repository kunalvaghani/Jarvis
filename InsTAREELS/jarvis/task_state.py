"""Small, durable record of Jarvis's current task and verified progress.

This is an audit/checkpoint record, not an automatic action replay queue.
"""
import json
import os
from pathlib import Path
import tempfile
import threading
from datetime import datetime, timezone
from .experience import recall_tasks


def _now():
    return datetime.now(timezone.utc).isoformat()


class TaskState:
    def __init__(self, base, *, read_only=False):
        self.on_finish = None
        self.read_only = read_only
        self.path = Path(base) / "task_state.json"
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
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".jarvis-task-", delete=False) as output:
                temporary = Path(output.name)
                json.dump(self.data, output, ensure_ascii=False, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

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
            self.data["current"] = {"goal": goal[:1500], "kind": kind, "project": str(project) if project else None,
                                    "status": "running", "stage": "started", "started_at": timestamp,
                                    "updated_at": timestamp, "checkpoints": [], "result": ""}
            self._write()

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
            self._write()

    def finish(self, status, result):
        with self.lock:
            current = self.data.get("current")
            if not current or current.get("status") != "running":
                return
            if status not in {"completed", "paused", "cancelled", "failed"}:
                raise ValueError("Invalid task status")
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
                        "completed": json.loads(json.dumps(completed[-12:]))}
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
        if any(item.get("attempted") for item in task.get("failures", [])):
            return "A previous action has an uncertain result. Inspect it before issuing the remaining task."
        uncertain = False
        for item in task.get("checkpoints", []):
            stage = item.get("stage")
            if stage in {"acting", "action_attempted"}:
                uncertain = True
            elif stage == "verified":
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
            if (task.get("goal") != goal[:1500] or task.get("kind") != kind
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
