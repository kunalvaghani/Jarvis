"""One snapshot of everything going on, so Jarvis can keep several contexts in mind at once.

Each question and task plan gets a compact "situation": what is on screen, which repository you are looking at
(and whether Jarvis has learned it), the task running and the queue, questions Jarvis is waiting on, what is
playing, the active project, recent conversation topics, and background learning. Jarvis can then answer
"what is this repo about?", "go back to the email thing" or "is that done yet?" without being told which context
you mean. Everything here is cheap to read (no network, no model) and bounded in size.
"""
import ctypes
import re
import time


def foreground():
    try:
        user = ctypes.windll.user32
        hwnd = user.GetForegroundWindow()
        buffer = ctypes.create_unicode_buffer(300)
        user.GetWindowTextW(hwnd, buffer, 300)
        pid = ctypes.c_ulong()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        import psutil
        return buffer.value.strip(), psutil.Process(pid.value).name()
    except Exception:
        return "", ""


def situation(actions, question=""):
    """A dict of the contexts that are active right now (empty parts are left out)."""
    found = {}
    title, process = foreground()
    if title and process.casefold() not in {"python.exe", "pythonw.exe"}:
        found["on_screen"] = {"window": title[:160], "app": process}
    learner = getattr(actions, "repo_learner", None)
    if learner is not None and learner.enabled:
        status = learner.status()
        if status.get("viewing"):
            entry = {"repository": status["viewing"], "learned": bool(status.get("viewing_learned"))}
            row = learner.known(status["viewing"]) if entry["learned"] else None
            if row:
                entry["purpose"] = row.get("purpose", "")[:300]
            found["viewing_repository"] = entry
        if status.get("learning_now") or status.get("queued"):
            found["background_learning"] = {"now": status.get("learning_now"), "waiting": status.get("queued", [])[:4]}
    state = getattr(actions, "task_state", None)
    snapshot = state.snapshot() if state is not None else None
    if snapshot and snapshot.get("status") in {"running", "paused"}:
        found["current_task"] = {"goal": str(snapshot.get("goal", ""))[:200], "status": snapshot.get("status"),
                                 "kind": snapshot.get("kind")}
    pending = list(getattr(actions, "pending_tasks", []) or [])
    if pending:
        found["queued_tasks"] = [str(getattr(item[1] if isinstance(item, tuple) else item, "value", item))[:100]
                                 for item in pending[:5]]
    prompts = getattr(actions, "whatsapp_prompts", None)
    if prompts:
        found["waiting_for_your_answer"] = prompts[-1].question[:200]
    if getattr(actions, "pending_question", None):
        found["waiting_for_your_answer"] = str(actions.pending_question.get("question", ""))[:200]
    media = getattr(actions, "last_media", None)
    if media:
        found["media"] = {"service": media}
        if media == "youtube" and getattr(actions, "last_youtube", None):
            found["media"]["last_played"] = actions.last_youtube.get("title", "")[:120]
    projects = getattr(actions, "projects", None)
    try:
        memory = projects._memory() if projects is not None else {}  # Saved opens only; no folder scan.
        if memory:
            path = max(memory, key=lambda key: memory[key])
            found["active_project"] = {"name": path.replace("\\", "/").rstrip("/").split("/")[-1], "path": path}
    except Exception:
        pass
    curator = getattr(actions, "curator", None)
    if curator is not None and curator.enabled:
        with curator.lock:
            turns = list(curator.turns)[-6:]
        if turns:
            found["recent_topics"] = [t["q"][:100] for t in turns]
        if curator.summaries:
            last = curator.summaries[-1]
            found["last_conversation"] = last["date"] + " " + last["time"] + " — " + last["title"]
    weather = getattr(actions, "weather_watch", None)
    if weather is not None and weather.last and weather.last.get("hazards"):
        found["weather_alerts"] = [h["message"][:140] for h in weather.last["hazards"][:2]]
    if question and re.search(r"(?i)\b(?:this|that|it|the) (?:repo|repository|project|code)\b", question):
        found.setdefault("note", "The user may mean the repository or project shown above.")
    return found


def prompt_block(actions, question=""):
    """The situation as compact JSON text for a system prompt (bounded)."""
    import json
    data = situation(actions, question)
    return json.dumps(data, ensure_ascii=False)[:2500] if data else ""
