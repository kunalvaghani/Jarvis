"""Direct navigation/media workflows with fresh checks, without model inference."""
import json
import os
from pathlib import PureWindowsPath
import re
import time

from .commands import Command, parse
from .ui_controls import _category, label_key, UNSAFE_INFERRED


def compile_workflow(goal, apps):
    text = goal.strip().rstrip(".!?")
    # Keep search query text intact; split only at the explicitly requested selection.
    match = re.fullmatch(r"(?:open|launch|go to) (?:the )?youtube(?: in (chrome|edge|firefox))? (?:and|then) "
        r"(?:search|find)(?: for)? (.+?)(?: (?:and|then) (?:play|open|select) (?:the )?(first|second|third|[1-9](?:st|nd|rd|th)?) (?:video|result))?", text, re.I)
    if not match:
        match = re.fullmatch(r"(?:search|find)(?: on)? youtube (?:for )?(.+?)(?: (?:and|then) (?:play|open|select) (?:the )?(first|second|third|[1-9](?:st|nd|rd|th)?) (?:video|result))?", text, re.I)
        if match:
            browser, query, ordinal = "chrome", match[1], match[2]
        else:
            browser = query = ordinal = None
    else:
        browser, query, ordinal = match.groups()
    if query:
        if browser and browser.casefold() not in {"chrome", "google chrome"}:
            return None  # Respect an explicitly requested browser.
        if re.search(r"\s+(?:and|then)\s+(?:open|play|select|click|delete|send|submit|write|type|create|make|save|upload)\b", query, re.I):
            return None
        steps = [{"action": "media_search", "value": query, "platform": "youtube", "browser": browser or "chrome", "expected": "Requested YouTube search results"}]
        if ordinal:
            number = {"first": 1, "second": 2, "third": 3}.get(ordinal.casefold(), int(ordinal[0]) if ordinal[0].isdigit() else 1)
            steps.append({"action": "select", "value": ordinal + " video", "category": "video", "position": number,
                          "platform": "youtube", "expected": "Selected video has active playback"})
        return steps
    music = re.fullmatch(r"(?:play|put on|start playing) (.+?) (?:on|from|in|using) (youtube|spotify)", text, re.I)
    if music:
        query, platform = music[1], music[2].casefold()
        if re.search(r"\s+(?:and|then)\s+(?:open|play|select|click|delete|send|submit|write|type|create|make|save|upload)\b", query, re.I):
            return None
        return [{"action": "media_search", "value": query, "platform": platform, "browser": "chrome", "expected": "Requested media search results"},
                {"action": "select", "value": query, "platform": platform, "category": "video" if platform == "youtube" else "track",
                 "expected": "Matched media result has active playback"}]
    clauses = re.split(r"\s+(?:and|then)\s+(?=(?:open|launch|start|search)\b)", text, flags=re.I)
    if len(clauses) < 2 or len(clauses) > 6:
        return None
    steps = []
    for clause in clauses:
        try:
            command = parse(clause)
        except ValueError:
            return None
        if command.kind == "open" and command.value in apps and not UNSAFE_INFERRED.search(command.value):
            steps.append({"action": "open", "value": command.value, "expected": "Requested native app visible"})
        else:
            return None
    return steps


def executable(snapshot):
    try:
        return PureWindowsPath(json.loads(snapshot.get("context") or "[]")[0]).name.casefold()
    except (ValueError, IndexError, TypeError):
        return ""


def observe(actions, platform, cancelled):
    from .media_ui import snapshot_for
    return snapshot_for(actions._ui(), cancelled, platform)


def search_ready(snapshot, platform, query):
    from .media_ui import platform_of
    if platform_of(snapshot) != platform:
        return False
    # Page title or the exact UIA input value, never just dispatch success.
    query = label_key(query)
    return bool(query and (query in label_key(snapshot.get("title", "")) or
        any(c["role"] == "Edit" and not c.get("password") and label_key(c.get("value", "")) == query
            for c in snapshot.get("controls", [])) or
        (platform == "spotify" and any(c["role"] == "ComboBox" and
            label_key(c.get("name", "").replace("+", " ")) == query
            for c in snapshot.get("controls", [])))))


def choose_result(snapshot, step):
    choices = _category(snapshot.get("controls", []), step["category"], snapshot.get("title", ""))
    if step.get("position"):
        index = step["position"] - 1
        return choices[index] if 0 <= index < len(choices) else None
    def media_tokens(text):
        return set(label_key(text.replace("'", "").replace("’", "")).split())
    tokens = media_tokens(step["value"])
    # Best matching title, scoped to result rows. Equal matched media results are
    # ranked in the service's displayed order for an explicit playback request.
    ranked = [(len(tokens & media_tokens(c["name"] + " " + c.get("context", "") + " " + c.get("metadata", ""))) / max(1, len(tokens)), i, c)
              for i, c in enumerate(choices)]
    eligible = sorted((row for row in ranked if row[0] >= .85), key=lambda row: (-row[0], row[1]))
    if step['category']=='track' and len(eligible)>1 and eligible[0][0]==eligible[1][0]:
        return None  # Let the user disambiguate equally matching Spotify tracks.
    return eligible[0][2] if eligible else None


def run(actions, goal, cancelled, clock=time.monotonic, sleep=time.sleep):
    steps = compile_workflow(goal, actions.apps)
    if not steps or getattr(actions, "resume_source", None):
        return None
    from .agent_events import check_policy
    state = actions.task_state
    from .experience_memory import observe_conditions
    state.set_conditions(observe_conditions(actions))
    actions.report("brain", "Using direct verified workflow; no planning model needed")
    state.update_plan(steps, [], "Direct workflow from explicit request")
    completed = []
    for step in steps:
        if cancelled():
            raise ValueError("Task cancelled before action.")
        check_policy(actions, step["action"])
        handle, before = None, {}
        platform = step.get("platform")
        if platform == "youtube" and actions.config.get("agent_runtime", {}).get("dom_browser", False):
            state.checkpoint("acting", action=step["action"], target=step["value"])
            result = actions._browser().request("search" if step["action"] == "media_search" else "select_video", cancelled,
                                     value=step["value"], position=step.get("position"), new_task=step["action"] == "media_search")
            if result.get("verified") is not True:
                raise ValueError("Task paused: browser operation returned without verification; no replay.")
            state.checkpoint("verified", action=step["action"], target=step["value"], evidence=result["message"], screen=result.get("title"))
            completed.append({**step, "verified": True, "result": result["message"]})
            state.update_plan(steps[len(completed):], completed, "DOM result verified")
            continue
        if step["action"] == "select":
            try:
                handle, before = observe(actions, platform, cancelled)
            except ValueError:
                pass
        state.checkpoint("procedure_surface", screen=before.get("title", ""))
        if step["action"] == "select":
            # The previous search was observed; select only a fresh matching row.
            chosen = choose_result(before, step)
            if chosen is None:
                if platform=='spotify':
                    choices = _category(before.get('controls',[]),'track',before.get('title',''))[:40]
                    if choices:
                        actions._ui().pending = {'handle':handle,'signature':before['signature'],'time':time.monotonic(),
                            'choices':choices,'verb':'play','media_platform':'spotify','thumbnails':before.get('thumbnails',{})}
                        question = 'Which Spotify track do you mean? Click its island card or say its name / option number.'
                        actions.report('question',question)
                        return 'Task paused: '+question
                raise ValueError("Task paused: no matching media result is visible; search may still be loading or the query may need a song title.")
            before["media_platform"] = platform
            state.checkpoint("acting", action="select", target=chosen["name"])
            result = actions._ui()._activate(handle, before, chosen, "play" if platform == "spotify" else "select", cancelled)
        else:
            state.checkpoint("acting", action=step["action"], target=step["value"])
            command = Command(step["action"], step["value"], platform or "")
            result = actions.execute(command, cancelled)
        state.checkpoint("action_attempted", action=step["action"], target=step["value"], evidence=result)
        deadline, verified, after = clock() + 8, False, {}
        while clock() < deadline:
            if cancelled():
                raise ValueError("Task cancelled after action; inspect the current result before retrying.")
            if step["action"] == "select" and platform == "spotify":
                after = before  # Playback verification below reads a new OS media state.
            else:
                try:
                    _, after = observe(actions, platform, cancelled)
                except ValueError:
                    sleep(.12)
                    continue
            if step["action"] == "media_search":
                verified = search_ready(after, platform, step["value"]) and (len(steps) == 1 or bool(_category(after.get("controls", []), "video" if platform == "youtube" else "track", after.get("title", ""))))
            elif step["action"] == "select":
                if platform == "spotify":
                    from .spotify import control
                    try:
                        status = control("status", cancelled)
                    except ValueError:
                        status = ""
                    requested = set(label_key(chosen["name"]).split())
                    observed = set(label_key(status).split())
                    verified = status.startswith("Spotify is playing:") and len(requested & observed) >= min(2, len(requested))
                else:
                    from .media_ui import platform_of
                    verified = platform_of(after) == "youtube" and any(c["role"] == "Button" and label_key(c["name"]) in {"pause", "pause k"} for c in after.get("controls", [])) and after.get("title") != before.get("title")
            else:
                entry = actions.apps[step["value"]]
                path = entry[0] if isinstance(entry, list) else entry.get("executable", "")
                names = {PureWindowsPath(path).name.casefold()} if path else set()
                if step["value"] == "calculator":
                    names.add("calculatorapp.exe")
                verified = executable(after) in names
            if verified:
                break
            sleep(.12)
        if not verified:
            raise ValueError("Task paused: the action was sent once, but its requested result was not observed. No action was replayed.")
        state.checkpoint("verified", action=step["action"], target=step["value"], evidence="Fresh accessibility/media state confirmed", screen=after.get("title"))
        completed.append({**step, "verified": True, "result": str(result)[:500]})
        state.update_plan(steps[len(completed):], completed, "Fresh state confirms last step")
    state.checkpoint("goal_verified", source='fresh_accessibility_media_state', evidence="All explicit workflow steps verified through fresh app/search/player state")
    return "Finished. Verified " + ("playback." if steps[-1]["action"] == "select" else "the requested app/search state.")
