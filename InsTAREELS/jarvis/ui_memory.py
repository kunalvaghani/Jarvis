"""Local history of successful Jarvis selections, scoped to app and window title."""
import json
from pathlib import Path
import time
from .experience import memory_score


class UIMemory:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        if not self.path.exists():
            return {"version": 1, "contexts": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("contexts"), dict):
            raise ValueError("Button memory is unreadable; preserve ui_memory.json and use forget button memory to reset it.")
        return data

    def save(self, data):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def remember(self, context, control, verb):
        if not context:
            return
        data = self.read()
        entries = data["contexts"].setdefault(context, [])
        existing = next((item for item in entries if item["name"] == control["name"] and item["role"] == control["role"]), None)
        if existing is None:
            existing = {"name": control["name"], "role": control["role"], "count": 0}
            entries.append(existing)
        existing.update(count=existing["count"] + 1, last_used=time.time(), verb=verb)
        entries.sort(key=lambda item: (item["count"], item["last_used"]), reverse=True)
        data["contexts"][context] = entries[:30]
        self.save(data)

    def candidate(self, context, controls):
        entries = self.read()["contexts"].get(context, [])
        now = time.time()
        for item in sorted(entries, key=lambda item: memory_score(
                item.get("count", 0), item.get("last_used"), now), reverse=True):
            matches = [control for control in controls if control["name"] == item["name"] and control["role"] == item["role"]]
            if len(matches) == 1:
                return matches[0], item.get("verb", "select")
        return None

    def clear(self):
        self.save({"version": 1, "contexts": {}})
