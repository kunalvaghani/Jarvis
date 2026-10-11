"""Answers and actions for the everyday kinds produced by intent_catalog.py.

Every text here describes what Jarvis really does (checked against the code it names) or says plainly that
something is not supported yet. Status answers read live state; nothing here sends, deletes or types.
"""
import ctypes
import json
import os
import platform
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

IMMEDIATE = {"behavior", "conversation_style", "repeat_last", "stop_speaking", "cognition_predict"}  # Answered at once, never queued.
STATUS = {"jarvis_status", "system_info"}  # Read-only; answered off the queue so a running task never delays them.
QUEUED = {"whatsapp_read", "gods_eye_camera", "media_related", "memory_summarize", "messenger_focus"}  # Touch apps.
SPOKEN = IMMEDIATE | STATUS | QUEUED

BEHAVIOR = {
    # Conversation and voice.
    "conversation_mode": "Say Jarvis once and I stay awake: follow-ups need no wake word until you've been quiet for {wake} seconds "
                         "or you say goodbye. Pauses inside that time keep the same conversation.",
    "no_command_words": "You don't need command words. Anything I don't recognise as a task, I answer as conversation.",
    "voice": "I speak with the local Kokoro voice, with natural pacing and breaths on. I can speak a little slower or faster; "
             "say 'speak more slowly'. A different voice blend is set in config under speech.voice.",
    "barge_in": "You can talk over me: when you start speaking I stop and listen, and the conversation carries on.",
    "final_only": "I wait until you've finished: I act only on your completed sentence, never on a half-heard one.",
    "still_here": "I'm here and listening.",
    "architecture": ("I work as one loop of six parts. Perception takes in your voice, the window in front of you and my "
                     "background sensors. Working memory holds the current goal, focus and what needs attention. Long-term "
                     "memory recalls past conversations, facts and how tasks went before. My reasoning and world model plan "
                     "the steps and predict what an action will do before I take it. Executive control decides whether to go "
                     "ahead or ask you, and learns from how things turn out. Then I act through my tools, and the result feeds "
                     "back into perception. Say 'show your mind' to watch it live on the island."),
    # Desktop and pointer.
    "other_monitor": "Moving a window to another monitor isn't supported yet. I can snap it left or right, or maximise or minimise it.",
    "open_folder_usage": "Say 'open folder' and its name, for example 'open folder Projects', or 'open the Downloads folder'.",
    "which_tab": "Which tab? Tell me part of its title, for example 'switch to the YouTube tab'.",
    "restart_frozen": "Say 'check if any app stopped responding' and I'll name it. Closing a frozen app needs your approval, "
                      "and I'll reopen it afterwards if you ask.",
    "pointer": "That's how I click: my own touch pointer taps the control and puts your mouse back where it was, "
               "so your mouse buttons are never used.",
    "pointer_wait": "I already do that: if you're moving the mouse or holding a button, I wait, and I refuse rather than interfere.",
    "click_cover": "I already do that: before tapping I check that the target window is in front and really under that point; "
                   "if another window covers it, I don't click.",
    "click_once": "I click once and then check the screen. If the result is uncertain I tell you rather than clicking again.",
    "keyboard": "While you type I don't send keystrokes. Push-to-write only types while you hold Left Ctrl and Left Alt.",
    # Writing.
    "writing_model": "When you say 'write ...' the local model composes the text and types it into the window you were in. "
                     "Say 'write exactly' followed by your words to type them unchanged.",
    "exact_text": "With 'write exactly' or 'type exactly' your words, capitals and punctuation are typed as you said them; "
                  "the model doesn't rewrite them.",
    "target_window": "I write into the window that was active when you spoke, and check it's still focused before typing. "
                     "If it isn't, I stop instead of typing somewhere else.",
    "push_to_write": "Push-to-write: hold Left Ctrl and Left Alt and what you say is typed at the cursor, not treated as a command. "
                     "Let go and it stops; pressing any other key during the hold cancels it. Normal listening resumes after you let go.",
    "overwrite": "Changes to existing files need your approval first, and I don't replace a file without asking.",
    # Messaging.
    "contacts": "That's how I pick contacts: a first name alone is never enough. If several people match, I show their full names "
                "on the island and ask which one you mean.",
    "need_recipient": "Who is it for? Say it with the name, for example 'WhatsApp Rahul asking if he's free tonight'.",
    "whatsapp_usage": "Say 'WhatsApp <name> saying <your words>' to send your words as they are, or 'WhatsApp <name> about <topic>' "
                      "and I'll draft it. Your own chat is listed under your name with '(You)'. Every message is previewed and "
                      "sent only after you approve.",
    "approvals": "I never send, delete or reply without asking first. The exact message and recipient appear on the island "
                 "and I read them out; only a fresh yes for that preview sends it. A no, or silence, sends nothing.",
    "change_recipient": "Say no to the current preview, then ask again with the right name. A new recipient always gets a new preview.",
    "nickname": "I search WhatsApp with the words you say, including nicknames saved in your contacts. If nothing matches, "
                "tell me the name as it's saved.",
    "chat_check": "I already do that: I confirm the chat header shows the right person right before typing, and if WhatsApp "
                  "loses focus before sending I stop, leaving the draft unsent.",
    "delivery": "After sending I confirm the message appears in the chat. I don't read the delivered or read ticks yet.",
    "chat_history": "When I draft a reply I read the recent messages in that chat for context.",
    "whatsapp_search": "WhatsApp only updates its search results when its window is in front, so I bring it forward and retry. "
                       "If it still shows nothing, the name may be saved differently.",
    "calls": "When a WhatsApp call rings I say who's calling, show it on the island and ask. Yes answers it, no declines it, "
             "and I never pick up on my own.",
    "call_controls": "I can answer or decline a ringing WhatsApp call. Ending, muting or checking a call that's already in progress "
                     "isn't supported yet.",
    "telegram": "Telegram works when Telegram Desktop is installed and signed in; I check that first. Say 'message <name> on "
                "Telegram saying ...' and I'll draft it and ask before sending.",
    "discord": "Discord can be opened, but reading servers and channels isn't supported yet.",
    "messenger_choice": "Each draft belongs to one app. Say it again with the app, for example 'message Sam on Telegram saying ...'.",
    "messenger_permissions": "WhatsApp and Telegram only need their desktop apps installed and signed in; I read them through Windows "
                             "accessibility, without API keys. I only say a messenger works after checking it's open and signed in.",
    "messaging_actions": "On WhatsApp I can find contacts, read unread chats, draft or send messages after your approval, "
                         "reply to unseen messages, and answer or decline calls. Telegram can send after approval when signed in. "
                         "Other messengers I can only open.",
    # Media.
    "choose_by_number": "Say its number from the results, for example 'play the second video', or tell me its name.",
    "media_ranking": "I prefer the official upload, and skip covers, remixes, slowed, lofi and karaoke versions unless you ask for one. "
                     "If I can't find the version you asked for, I say so.",
    "one_player": "Starting music on one player pauses the other, so YouTube and Spotify never play together.",
    "service_choice": "Videos go to YouTube. A song without a service named goes to the player you used last, otherwise your "
                      "default player.",
    "hide_island": "Hiding the island on request isn't supported yet; media cards close by themselves after a few seconds.",
    "media_island": "The island already shows a searching card while I look for a song, and a new card whenever playback changes.",
    "media_while_speaking": "Media keeps playing while I answer. Lowering the music while I speak isn't supported yet.",
    "media_retry": "I check the real player state after every media command, and say plainly if something didn't play.",
    "media_commands": "Media commands: play a song or video, pause, resume, next, previous, restart, skip forward or back by seconds, "
                      "volume or mute, shuffle and repeat, captions, playback speed, full screen, and 'what's playing'.",
    "which_song": "Which song should I queue?",
    "research_usage": "Which topic? Tell me what the papers should be about, for example 'find research papers about solar cells'.",
    "which_repo": "Which repository? Say 'learn' with its owner and name, like 'learn psf/requests', or open it in your browser "
                  "and say 'learn this repo'.",
    "coding_and_music": "Give me the coding task first, then say 'play' and a song. They run one after another, so the music "
                        "starts once the coding task finishes.",
    # Tasks and planning.
    "queue_order": "Tasks run one after another in the order you gave them; a new request waits until the current one finishes.",
    "parallel": "Yes: questions are answered while a task keeps running, and we can keep talking while I work.",
    "goodbye_keeps_tasks": "Saying goodbye ends the conversation but queued tasks keep running in the background.",
    "queue_reorder": "Changing the order of the queue isn't supported yet. I can cancel tasks by name or number.",
    "queue_pause": "Pausing a queued task isn't supported yet. I can cancel it, and you can ask for it again later.",
    "nothing_cancelled": "Okay, I've left everything running.",
    "planner": "I plan each task as steps and start each step as soon as it's ready, keeping the same task context between steps. "
               "I can describe the steps but I don't make up a finishing time.",
    "tools": "For each request I pick the direct command or the tools that fit it, rather than loading every tool.",
    "replan": "When a step fails I replan from that step, not from the start, and steps that already finished aren't repeated.",
    "no_replay": "If an action's outcome is uncertain, such as a send or a file write, I stop and tell you instead of repeating it. "
                 "Nothing with a side effect is retried automatically.",
    "performance": "The first answer is slower because the model is loaded into the GPU. It then stays warm for about {warm} minutes, "
                   "so follow-ups are faster. Direct commands run without the model at all.",
    "vision": "I work from window text and accessibility controls first, and use screenshots only when those can't identify the target.",
    "free_apis": "I use free public services wherever possible, and none of my connected services charge you. If something needs "
                 "a paid or private key, I tell you rather than using one silently.",
    "verification": "I report success only after checking the real result in the app, the player, the file or the test run. "
                    "If I can't verify it, I say so.",
    "limits": "Not supported yet: moving windows between monitors, reordering or pausing the queue, ending or muting calls, Discord "
              "reading, and hiding the island. Several God's Eye layers need keys (Google 3D, TomTom traffic, NASA FIRMS) or an "
              "SDR receiver, and larger multi-file coding tasks can fail validation on the local model.",
    # Memory.
    "dates": "I already do that: relative dates like 'tomorrow' or 'next Friday' are saved as real dates.",
    "secrets": "I never store passwords, OTPs, card or account numbers, or keys. They are dropped before anything is saved.",
    "memory_storage": "Memories live in your Obsidian vault: facts in Jarvis Memory, conversation summaries in Jarvis Conversations, "
                      "and studied repositories in Jarvis Repos, with a local cache under .jarvis-runtime. What I learn about a "
                      "repository is saved there automatically.",
    "memory_grounding": "I use saved memories when they're relevant, and only state what is actually stored; I don't invent one. "
                        "A saved fact must come from something you said, so examples and fiction aren't stored as facts about you.",
    "memory_update": "Tell me the new preference with 'remember that ...'; a newer fact on the same topic updates the old one. "
                     "Facts are kept under categories, so project and personal preferences stay separate.",
    # Context.
    "references": "When it isn't clear what 'this' or 'that' means, I ask instead of guessing.",
    # Repositories and coding.
    "license": "I learn ideas and structure from repositories, not code to paste, and each repository's licence is recorded "
               "in its note. Check that licence before reusing any code.",
    "repo_reuse": "For coding tasks I look for relevant repositories first. What I've already learned is reused from memory, "
                  "without downloading again.",
    "repo_forget_usage": "Say 'forget repo' followed by its owner and name, for example 'forget repo psf/requests'.",
    "repo_stop": "Background learning can't be paused by voice yet; it finishes the repository it's on. It can be turned off "
                 "with repo_learning.enabled in config.",
    "repo_background": "Repositories are learned one at a time in a background thread, without blocking your commands. "
                       "The island shows when learning starts and finishes. Downloads use GitHub's archive links, which keeps "
                       "API use low, and a private or missing repository is reported as not accessible.",
    "commits": "Coding agents work on their own git branches and worktrees, and I never push. To commit specific files, "
               "do it yourself or say 'run command git commit' with the file names.",
    "agents": "Already the case: parallel coding agents each get their own git worktree and only the files they own, so two agents "
              "never edit the same file. Their work is merged on an integration branch and checked before it's reported.",
    # Diagnostics.
    "stutter": "Stuttering usually means the GPU is busy with a large model while I speak. Speech keeps a reserved share of GPU "
               "memory, and the speech watchdog restarts a stuck voice. If it keeps happening, close other GPU-heavy apps.",
    "offline": "Offline I can still answer from the local model, control apps, write and code. Web search, weather, Gmail, "
               "GitHub learning and God's Eye feeds need the internet. Gmail needs your Google sign-in, and God's Eye layers "
               "need keys (Google 3D, TomTom, NASA FIRMS). An RTL-SDR receiver is the only extra hardware some features use.",
    # God's Eye.
    "styles": "Which style? Thermal, night vision, noir, retro, anime, snow or normal; or a HUD: tactical or cyber.",
    "geocoding": "I already do that: places come from OpenStreetMap, ranked by importance, so seas, regions and landmarks win "
                 "over businesses with the same name.",
    "imagery": "God's Eye already shows satellite imagery. The photorealistic 3D city view needs a Google Maps key.",
    "gods_eye_backup": "Already the case: each update keeps the previous God's Eye source in a dated backup folder.",
    "airports": "God's Eye doesn't have an airports or heliports layer I can switch on.",
    "squawks": "Emergency codes: 7700 is a general emergency, 7600 radio failure, 7500 unlawful interference (hijack). "
               "Any of these within 40 km is announced, once per event, as what the transponder reports, not a confirmed incident.",
    "flight_honesty": "I report the positions, callsigns and heights the live feed gives, with their distance, and say when the feed "
                      "is stale or unavailable. I don't guess identities the feed doesn't show.",
    "cyclone_coverage": "God's Eye's cyclone tracks come from NOAA (NHC and CPHC): the Atlantic and the eastern and central Pacific "
                        "only. They don't cover the Indian Ocean, so no track near India doesn't mean there's no storm. "
                        "The weather watcher's GDACS feed does cover India.",
    "fire_data": "NASA FIRMS active fires need a FIRMS key, which isn't set. Wildfire perimeters work without a key but cover the US. "
                 "The weather watcher also checks NASA EONET wildfire events.",
    "manual_layers": "Already the case: I only turn off layers I turned on; layers you switched on yourself stay.",
    "cameras": "Map layers are not video: only CCTV cameras in God's Eye's catalogue show live frames, and if a feed is unavailable "
               "I say so. I don't promise cameras that aren't in the catalogue.",
    "traffic": "Live traffic needs a TomTom key in God's Eye's settings; it isn't set.",
    "gods_eye_limits": "Not voice-controlled yet: social-video embedding, before-and-after imagery comparison and director storytelling. "
                       "They're available in God's Eye's own interface.",
    # Weather and live data.
    "weather_watch": "The weather watcher checks every {weather} minutes and announces a hazard once, then again only if it gets worse.",
    "official_warning": "No. My alerts come from forecast data (Open-Meteo), earthquake and disaster feeds (USGS, GDACS, NASA EONET), "
                        "not from a government warning service. Check your national weather service for official warnings.",
    "live_data": "Live answers come from public services, and I name the source. If I only have earlier or cached data I say so.",
    # Privacy.
    "privacy": "Keys stay in the git-ignored secrets folder, never in config or the repository. Your location stays on this PC, "
               "and screenshots for docs leave your area out. Each request uses the narrowest tool that can do it.",
}


def behavior(actions, key):
    config = getattr(actions, "config", {})
    return BEHAVIOR.get(key, "I'm not sure how to help with that yet.").format(
        wake=config.get("wake_timeout_seconds", 90), warm=int(config.get("gpu_scheduler", {}).get("warm_seconds", 1800) / 60),
        weather=config.get("weather_alerts", {}).get("interval_minutes", 30))


# --- session style ---------------------------------------------------------------------------------------------------
STYLE_TEXT = {"short": "Keep answers short: one or two sentences.", "simple": "Explain simply, in plain words.",
              "serious": "Be serious; no jokes.", "detailed": "Give detailed answers."}


def conversation_style(actions, value, follow_up=""):
    styles = actions.session_style
    if value in STYLE_TEXT:
        styles[value] = STYLE_TEXT[value]
        client = getattr(getattr(actions, "knowledge", None), "client", None)
        if client is not None:
            client.answer_style = list(styles.values())
        if follow_up:
            from .commands import Command
            actions.submit(Command("ask", follow_up))
            return ""
        return {"short": "Okay, short answers.", "simple": "Okay, I'll keep it simple.", "serious": "Understood, no jokes.",
                "detailed": "Okay, more detail."}[value]
    speech = actions.config.setdefault("speech", {})
    if value in {"slower", "faster", "normal_voice"}:
        current = float(speech.get("speed", 1.0))
        speech["speed"] = 1.0 if value == "normal_voice" else max(.85, min(1.2, current + (-.1 if value == "slower" else .1)))
        return "Okay, I'll speak " + ("at my normal speed." if value == "normal_voice" else value + " now.")
    if value == "chat_only":
        actions.chat_only_until = time.monotonic() + 120
        return "Okay, I'm just listening. Nothing you say for the next couple of minutes will be treated as a task."
    if value == "private":
        actions.private_mode = True
        return "Okay. I won't read message contents aloud; I'll just say who it's from. Say 'resume message alerts' to undo."
    if value == "quiet":
        actions.quiet_alerts = True
        return "Spoken notifications are off. Alerts still appear in the log. Say 'resume message alerts' to turn them back on."
    if value == "unquiet":
        actions.quiet_alerts = actions.private_mode = False
        return "Spoken notifications are back on."
    if value == "no_memory":
        curator = getattr(actions, "curator", None)
        if curator is not None:
            curator.paused = True
        return "Okay, I won't save anything from this conversation to long-term memory until Jarvis restarts."
    if value == "stop_whatsapp_watch":
        watcher = getattr(actions, "whatsapp_watcher", None)
        if watcher is None:
            return "I'm not watching WhatsApp right now."
        watcher.close()
        actions.whatsapp_watcher = None
        return "Stopped watching WhatsApp for new messages and calls until Jarvis restarts."
    raise ValueError("Unknown style " + value)


ALERT_PREFIXES = ("Weather alert", "Heads up for", "God's Eye alert", "New WhatsApp message from")


def filter_report(actions, kind, message):
    """Quiet and private modes: (kind, message) after filtering a background announcement."""
    if kind != "spoken_reply" or not isinstance(message, str):
        return kind, message
    if getattr(actions, "quiet_alerts", False) and message.startswith(ALERT_PREFIXES):
        return "log", message
    if getattr(actions, "private_mode", False):
        found = re.match(r"(New WhatsApp message from [^:.]+)[:.]", message) or re.match(r"(.{1,60}?) wrote: ", message)
        if found:
            return kind, (found[1] + ("." if found[1].startswith("New") else " sent new messages."))
    return kind, message


def repeat_last(actions, value):
    if value == "typed":
        typed = getattr(actions, "last_typed", "")
        return ("I typed: " + typed) if typed else "I haven't typed anything in this session."
    text = (getattr(actions, "last_spoken", "") or "").strip()
    if not text:
        return "I haven't said anything yet."
    if value == "sentence":
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        return sentences[-1] if sentences else text
    return text


# --- live status ---------------------------------------------------------------------------------------------------------
def _ago(seconds):
    seconds = int(max(0, seconds))
    return (str(seconds) + " seconds" if seconds < 90 else str(round(seconds / 60)) + " minutes" if seconds < 5400
            else str(round(seconds / 3600, 1)) + " hours") + " ago"


def _ollama(path):
    import requests
    return requests.get("http://127.0.0.1:11434" + path, timeout=3).json()


def jarvis_status(actions, topic):
    config = getattr(actions, "config", {})
    if topic == "uptime":
        import psutil
        started = psutil.Process(os.getpid()).create_time()
        return "I've been running for " + _ago(time.time() - started).replace(" ago", "") + "."
    if topic == "style":
        styles = list(actions.session_style.values())
        speed = config.get("speech", {}).get("speed", 1.0)
        return ("For this conversation you asked: " + " ".join(styles) if styles else
                "You haven't asked for a particular tone in this conversation.") + (
            " Speech speed is " + str(round(speed, 2)) + "." if speed != 1.0 else "")
    if topic in {"while_away", "recent_tasks"}:
        rows = list(actions.task_history)[-6:]
        with actions.queue_lock:
            current, pending = actions.current_item, len(actions.pending_tasks)
        parts = ["Recent tasks: " + "; ".join(r["what"] + " (" + r["status"] + ", " + _ago(time.time() - r["at"]) + ")"
                                             for r in rows) + "." if rows else "No tasks finished in this session."]
        if current:
            parts.append("Working on: " + (current[1].value or current[1].kind)[:80] + ".")
        if pending:
            parts.append(str(pending) + " waiting in the queue.")
        if topic == "while_away":
            watch = getattr(actions, "weather_watch", None)
            if watch is not None and watch.last and watch.last.get("hazards"):
                parts.append("Weather: " + watch.last["hazards"][0]["message"])
        return " ".join(parts)
    if topic == "recent_actions":
        rows = [r for r in actions.task_history if r["status"] == "done"][-4:]
        return ("The last things I did: " + "; ".join(r["what"] + ": " + r["result"][:100] for r in rows) + "."
                if rows else "I haven't changed anything on your desktop in this session.")
    if topic == "last_command":
        rows = list(actions.command_history)
        return ("Before this you asked: " + rows[-2]) if len(rows) > 1 else "That's the first thing you've asked me in this session."
    if topic == "last_failure":
        rows = [r for r in actions.task_history if r["status"] == "failed"]
        if not rows:
            return "Nothing has failed in this session."
        last = rows[-1]
        return "The last failure was " + last["what"] + ", " + _ago(time.time() - last["at"]) + ": " + last["result"][:300]
    if topic == "task_steps":
        state = actions.task_state.snapshot() or {}
        if not state:
            return "There's no task in progress or recently finished."
        done = [c.get("action") or c.get("stage") for c in state.get("checkpoints", [])][-6:]
        remaining = [str(s.get("action") or s.get("description") or s)[:60] for s in (state.get("plan") or {}).get("remaining", [])][:3]
        return ("Task: " + str(state.get("goal", ""))[:100] + " (" + str(state.get("status", "")) + "). " +
                ("Done so far: " + "; ".join(str(d) for d in done if d) + ". " if done else "") +
                ("Next: " + "; ".join(remaining) + "." if remaining else ""))
    if topic == "approvals":
        from .whatsapp import snapshot
        waiting = snapshot(actions)
        if waiting:
            options = "; ".join(o["label"] + (": " + o["context"][:120] if o["context"] else "") for o in waiting["options"])
            return "Waiting for you: " + waiting["question"] + " Options: " + options + ". Approving does only that."
        if actions.approvals_waiting:
            return "There's an approval card on the island waiting for you; approving does exactly what it shows, nothing else."
        return "Nothing is waiting for your approval."
    if topic == "last_draft":
        from .whatsapp import snapshot
        waiting = snapshot(actions)
        text = next((o["context"] for o in (waiting or {}).get("options", []) if o.get("context")), "")
        return ("The draft waiting for you: " + text) if text else "No draft is waiting right now."
    if topic == "media_history":
        service = getattr(actions, "last_media", None)
        title = getattr(actions, "last_media_title", "")
        return (("Last on " + service.title() + (": " + title if title else "") + ".") if service
                else "Nothing has been played in this session.")
    if topic == "gmail":
        try:
            from .gmail_api import API
            profile = API(actions.base).call("GET", "profile")
            return "Gmail is signed in as " + str(profile.get("emailAddress", "your account")) + "."
        except Exception as exc:
            return ("Gmail isn't signed in right now (" + str(exc)[:120] + "). Google sign-ins expire when the token is "
                    "revoked or unused for a long time; signing in again renews it.")
    if topic == "models":
        lines = ["Answers use " + config.get("knowledge", {}).get("model", "the local model"),
                 "planning and coding use " + config.get("brain", {}).get("planner", "the same model"),
                 "quick routing uses " + config.get("context_selector", {}).get("model", "a small model"),
                 "speech recognition is faster-whisper " + config.get("whisper", {}).get("model", ""),
                 "and the voice is Kokoro"]
        try:
            loaded = _ollama("/api/ps").get("models", [])
            placement = ["{} ({}% on GPU)".format(m["name"], round(100 * m.get("size_vram", 0) / max(1, m.get("size", 1))))
                         for m in loaded]
            lines.append("Loaded now: " + (", ".join(placement) if placement else "no model is loaded"))
        except Exception:
            lines.append("Ollama didn't answer, so I can't see which models are loaded")
        return "; ".join(lines) + "."
    if topic == "capabilities":
        from .capability_guide import capabilities_text, apis_text
        return capabilities_text() + " " + apis_text(actions.base)
    if topic == "youtube_key":
        from .media_player import youtube_key
        return ("A YouTube Data API key is set; YouTube search uses it." if youtube_key() else
                "No YouTube API key is set, so YouTube search uses the keyless fallback.")
    if topic == "github_quota":
        import requests
        try:
            core = requests.get("https://api.github.com/rate_limit", timeout=6).json()["resources"]["core"]
            return ("GitHub allows {} more API calls this hour out of {} (resets at {})."
                    .format(core["remaining"], core["limit"], datetime.fromtimestamp(core["reset"]).strftime("%H:%M")))
        except Exception as exc:
            return "I couldn't reach GitHub to check the limit (" + str(exc)[:80] + ")."
    if topic == "weather_watch":
        watch = getattr(actions, "weather_watch", None)
        if watch is None:
            return ("The weather watcher is enabled but hasn't started in this session; it starts with Jarvis."
                    if config.get("weather_alerts", {}).get("enabled", True) else
                    "The weather watcher is turned off (weather_alerts.enabled).")
        last = watch.last
        if not last:
            return "The weather watcher is on, checking every {} minutes; it hasn't finished a check yet.".format(watch.interval)
        found = last.get("hazards") or []
        sources = [k for k, ok in last.get("sources", {}).items() if ok]
        return ("The weather watcher is on. Last check " + _ago(watch.clock() - last["at"]) + " for " +
                (last.get("place") or {}).get("name", "your area") + ": " +
                ("; ".join(h["message"] for h in found[:3]) if found else "no hazards") +
                ". Sources: " + ", ".join(sources) + ". Forecast data, not an official warning.")
    if topic == "readiness":
        result = subprocess.run([os.sys.executable, "-m", "jarvis.launcher", "--check"], cwd=actions.base, capture_output=True,
                                text=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        last = (result.stdout.strip().splitlines() or [result.stderr.strip()[:200]])[-1]
        return "Launcher check: " + last[:300]
    if topic == "speech":
        whisper = config.get("whisper", {})
        return "Speech recognition: faster-whisper {} on {} ({}).".format(whisper.get("model"), whisper.get("device"),
                                                                           whisper.get("compute_type"))
    if topic == "island_config":
        keys = {k: config[k] for k in ("ui", "media") if k in config}
        return "Island and UI settings: " + json.dumps(keys)
    if topic == "changes":
        result = subprocess.run(["git", "log", "-5", "--format=%ad %s", "--date=short"], cwd=actions.base, capture_output=True,
                                text=True, timeout=20)
        return "Latest changes: " + "; ".join(result.stdout.strip().splitlines()) if result.returncode == 0 else \
            "I couldn't read the change history."
    if topic == "gods_eye_version":
        root = actions.base / "integrations/gods-eye-view-src/gods-eye-view-main"
        try:
            marker = json.loads((root / "jarvis-gods-eye.json").read_text(encoding="utf-8"))
            return "God's Eye View commit " + str(marker.get("commit", ""))[:8] + " from " + str(marker.get("date", ""))[:10] + "."
        except (OSError, ValueError):
            return "I don't have a version marker for God's Eye; say 'update God's Eye' to install the latest."
    if topic in {"cognition", "lessons"}:
        cognition = getattr(actions, "cognition", None)
        if cognition is None or not cognition.enabled:
            return "My cognitive loop is switched off (config cognition.enabled)."
        if topic == "cognition":
            return cognition.status_text()
        lessons = list(cognition.lessons)[-4:]
        return ("Lessons I've learned: " + " | ".join(lesson[17:] for lesson in lessons) + "."
                if lessons else "No lessons yet: nothing has failed repeatedly and you haven't corrected me this session.")
    raise ValueError("Unknown status topic " + topic)


def cognition_predict(actions, text):
    """'What would happen if you ...': run the world model on the command without executing it."""
    from .commands import Command, parse
    cognition = getattr(actions, "cognition", None)
    if cognition is None or not cognition.enabled:
        return "My world model is switched off (config cognition.enabled)."
    try:
        command = parse(text)
    except ValueError:
        command = Command("task", text)
    prediction = cognition.predict(command)
    return "If I " + text.rstrip("?.! ") + ": " + cognition.explain(prediction) + " I haven't done anything yet."


# --- this PC ---------------------------------------------------------------------------------------------------------------
def _windows():
    """Visible top-level windows: (hwnd, title, pid, minimized)."""
    user = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def each(hwnd, _):
        if user.IsWindowVisible(hwnd):
            length = user.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user.GetWindowTextW(hwnd, buffer, length + 1)
                pid = ctypes.c_ulong()
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                found.append((hwnd, buffer.value, pid.value, bool(user.IsIconic(hwnd))))
        return True
    user.EnumWindows(each, 0)
    return found


def _process_name(pid):
    import psutil
    try:
        return psutil.Process(pid).name().removesuffix(".exe")
    except Exception:
        return "unknown"


def system_info(actions, topic, value=""):
    import psutil
    if topic == "cpu":
        total = psutil.cpu_percent(interval=.5)
        return "CPU use is " + str(round(total)) + "% across " + str(psutil.cpu_count()) + " threads. " + system_info(actions, "top")
    if topic == "memory":
        memory = psutil.virtual_memory()
        return "{:.1f} GB of {:.1f} GB memory is free ({}% used).".format(memory.available / 2 ** 30, memory.total / 2 ** 30,
                                                                          round(memory.percent))
    if topic == "top":
        processes = list(psutil.process_iter(["name", "memory_info"]))
        for p in processes:
            try:
                p.cpu_percent(None)
            except Exception:
                pass
        time.sleep(.6)
        usage = []
        for p in processes:
            try:
                usage.append((p.cpu_percent(None), p.info["memory_info"].rss if p.info["memory_info"] else 0, p.info["name"]))
            except Exception:
                pass
        cpu = [u for u in sorted(usage, reverse=True) if u[2] and u[2] != "System Idle Process"][:3]
        ram = sorted(usage, key=lambda u: -u[1])[:3]
        return ("Busiest on CPU: " + ", ".join("{} {}%".format(n.removesuffix(".exe"), round(c / psutil.cpu_count())) for c, _, n in cpu) +
                ". Most memory: " + ", ".join("{} {:.1f} GB".format(n.removesuffix(".exe"), m / 2 ** 30) for _, m, n in ram) + ".")
    if topic == "gpu":
        try:
            row = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0].split(", ")
            return "GPU: {}, {} of {} MB video memory used ({} MB free), {}% busy.".format(row[0], row[2], row[1],
                                                                                         int(row[1]) - int(row[2]), row[3])
        except Exception:
            return "I couldn't read the GPU (nvidia-smi isn't available)."
    if topic == "gpu_processes":
        try:
            rows = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
                                  capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        except Exception:
            return "I couldn't read GPU processes (nvidia-smi isn't available)."
        apps = [r.split(", ") for r in rows if r.strip()]
        if not apps:
            return "No process is using the GPU for compute right now. " + system_info(actions, "gpu")
        apps.sort(key=lambda r: -int(r[2]) if r[2].isdigit() else 0)
        return "Using the GPU: " + ", ".join(Path(r[1]).stem + " " + r[2] + " MB" for r in apps[:5]) + "."
    if topic == "windows":
        version = platform.version()
        release = "11" if int(version.split(".")[-1] or 0) >= 22000 else platform.release()
        return "Windows " + release + " (build " + version + "), " + platform.machine() + "."
    if topic == "services":
        running = [s.display_name() for s in psutil.win_service_iter() if s.status() == "running"]
        return str(len(running)) + " services are running, for example " + ", ".join(sorted(running)[:6]) + "."
    if topic in {"apps", "minimized"}:
        rows = [(title, _process_name(pid), mini) for _, title, pid, mini in _windows()
                if title not in {"Program Manager"} and not title.startswith("Jarvis")]
        if topic == "minimized":
            rows = [r for r in rows if r[2]]
            return ("Minimised: " + "; ".join(n + " (" + t[:50] + ")" for t, n, _ in rows[:8]) + "." if rows
                    else "No windows are minimised.")
        names = sorted({n for _, n, _ in rows})
        return "Open apps: " + ", ".join(names[:15]) + "." if names else "No app windows are open."
    if topic == "running":
        name = value.casefold().replace("google ", "").replace(" ", "")
        found = [p.info["name"] for p in psutil.process_iter(["name"]) if p.info["name"] and name in p.info["name"].casefold().replace(" ", "")]
        return (value.title() + " is running" + (" (" + str(len(found)) + " processes)." if len(found) > 1 else ".")) if found else \
            value.title() + " isn't running."
    if topic == "installed":
        target = value.casefold()
        apps = [name for name in actions.apps if target in name.casefold()]
        from .windows_commands import match
        builtin = match("open " + target)
        if apps or builtin:
            return value.title() + " is available. Say 'open " + value + "' to start it."
        return "I couldn't find " + value + " among the apps I know."
    if topic == "downloads":
        folder = Path.home() / "Downloads"
        files = sorted((p for p in folder.glob("*") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        if not files:
            return "Your Downloads folder is empty."
        return "Most recent downloads: " + "; ".join(p.name + " (" + _ago(time.time() - p.stat().st_mtime) + ")" for p in files) + \
            ". Say 'open the Downloads folder' to see them."
    if topic == "not_responding":
        user = ctypes.windll.user32
        hung = [(title, _process_name(pid)) for hwnd, title, pid, _ in _windows() if user.IsHungAppWindow(hwnd)]
        return ("Not responding: " + "; ".join(n + " (" + t[:50] + ")" for t, n in hung) + "." if hung
                else "All open apps are responding.")
    if topic == "foreground":
        user = ctypes.windll.user32
        hwnd = user.GetForegroundWindow()
        title = next((t for h, t, _, _ in _windows() if h == hwnd), "")
        pid = ctypes.c_ulong()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return "The active window is " + _process_name(pid.value) + (": " + title[:80] if title else "") + "."
    if topic == "under_cursor":
        try:
            from ctypes import wintypes
            from .whatsapp import _uia
            uia, U = _uia()
            point = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            element = uia.ElementFromPoint(U.tagPOINT(point.x, point.y))
            name, kind = element.CurrentName or "", element.CurrentLocalizedControlType or "control"
            return "Under your pointer: " + kind + (" '" + name[:80] + "'" if name else " with no label") + "."
        except Exception as exc:
            return "I couldn't read what's under the pointer (" + str(exc)[:80] + ")."
    raise ValueError("Unknown system topic " + topic)


# --- app-touching reads ---------------------------------------------------------------------------------------------------
def whatsapp_read(actions, mode, who, cancelled):
    from . import whatsapp as wa
    private = getattr(actions, "private_mode", False)
    with wa.physical():
        handle = wa.ensure_window(cancelled)
        if mode == "unread":
            rows = wa.unread_chats(handle, True, False)
            if not rows:
                return "No unread WhatsApp chats. Other messengers aren't checked; WhatsApp is the only one I can read."
            if private:
                return "Unread on WhatsApp: " + ", ".join(r["name"] for r in rows[:8]) + "."
            return "Unread on WhatsApp: " + "; ".join(r["name"] + " (" + str(r["unread"]) + ")" +
                                                      (": " + r.get("preview", "")[:80] if r.get("preview") else "") for r in rows[:6]) + "."
        if mode == "open_chat":
            name = wa.open_chat_name(wa.read(wa.document(handle)))
            return ("The open chat is " + name + ".") if name else "No chat is open in WhatsApp."
        if mode == "call":
            found = wa.call_controls()
            return ("A call is ringing from " + found[0] + ".") if found else "No WhatsApp call is ringing."
        if mode == "find":
            matches = wa.match_contacts(who, wa.search(handle, who, cancelled))
            wa.clear_search(handle)
            if not matches:
                return "I couldn't find anyone called " + who + " on WhatsApp."
            names = [m["name"] for m in matches[:6]]
            actions.report(wa.CARD, wa.card("searching", who, ", ".join(names)[:90], "Matches"))
            return ("Found " + str(len(names)) + ": " + ", ".join(names) + ".") if len(names) > 1 else ("Found " + names[0] + ".")
        if mode == "latest":
            row = wa.find_contact(actions, handle, who, cancelled)
            contact = wa.open_row(handle, row, cancelled)
            wa.clear_search(handle)
            incoming = [m for m in wa.messages(wa.read(wa.document(handle))) if not m["outgoing"]]
            if not incoming:
                return "There's no message from " + contact + " in view."
            return contact + " sent a message." if private else contact + "'s latest message: " + incoming[-1]["text"][:300]
    raise ValueError("Unknown WhatsApp read " + mode)


def media_related(actions, mode, cancelled):
    """Use what is playing now: a live version, the artist, the channel, or the same title on the other player."""
    from .commands import Command
    from .media_player import active_service
    title = ""
    service = active_service(actions) or getattr(actions, "last_media", None)
    try:
        status = actions.execute(Command("spotify_control", "status", "auto"), cancelled)
        title = str(status)
    except Exception:
        title = getattr(actions, "last_media_title", "")
    title = re.sub(r"^(?:now playing|playing|paused)[:\s]*", "", title, flags=re.I).split(" on Spotify")[0].split(" on YouTube")[0]
    title = re.sub(r"[.]$", "", title).strip()
    if not title:
        return "Nothing is playing, so tell me the song or video by name."
    if mode in {"spotify", "youtube"}:
        return actions.execute(Command("play_media", title, mode), cancelled)
    if mode == "live":
        return actions.execute(Command("media_search", title + " live performance", "youtube"), cancelled)
    if mode == "longer":
        return actions.execute(Command("media_search", title + " full explanation", "youtube"), cancelled)
    artist = title.split(" by ")[-1] if " by " in title else title.split(" - ")[0]
    if mode == "artist":
        return actions.execute(Command("play_media", artist + " songs", service if service == "spotify" else "spotify"), cancelled)
    if mode == "channel":
        return actions.execute(Command("media_search", artist + " latest video", "youtube"), cancelled)
    raise ValueError("Unknown media mode " + mode)


def messenger_focus(actions, cancelled):
    import psutil
    from .commands import Command
    running = {p.info["name"].casefold() for p in psutil.process_iter(["name"]) if p.info["name"]}
    for exe, name in (("whatsapp.exe", "whatsapp"), ("telegram.exe", "telegram"), ("discord.exe", "discord"), ("signal.exe", "signal")):
        if exe in running or any(n.startswith(exe[:-4]) for n in running):
            return actions.execute(Command("open", name), cancelled)
    return "No messaging app is open."


def memory_summarize(actions):
    curator = getattr(actions, "curator", None)
    if curator is None or not curator.enabled:
        return "Long-term memory is turned off (memory.long_term.enabled)."
    count = curator.save_now()
    return ("Saving a summary of our last " + str(count) + " exchanges to Jarvis Conversations in your vault." if count >= 2
            else "There isn't enough conversation yet to summarise.")


def execute(actions, command, cancelled=lambda: False):
    kind = command.kind
    if kind == "behavior":
        return behavior(actions, command.value)
    if kind == "conversation_style":
        return conversation_style(actions, command.value, command.extra)
    if kind == "repeat_last":
        return repeat_last(actions, command.value)
    if kind == "cognition_predict":
        return cognition_predict(actions, command.value)
    if kind == "jarvis_status":
        return jarvis_status(actions, command.value)
    if kind == "system_info":
        return system_info(actions, command.value, command.extra)
    if kind == "whatsapp_read":
        return whatsapp_read(actions, command.value, command.extra, cancelled)
    if kind == "media_related":
        return media_related(actions, command.value, cancelled)
    if kind == "messenger_focus":
        return messenger_focus(actions, cancelled)
    if kind == "memory_summarize":
        return memory_summarize(actions)
    if kind == "gods_eye_camera":
        from .gods_eye import execute as gods_eye_execute
        return gods_eye_execute(actions, command, cancelled)
    raise ValueError("Unknown intent kind " + kind)
