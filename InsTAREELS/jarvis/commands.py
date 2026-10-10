from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Command:
    kind: str
    value: str = ""
    extra: str = ""


def normalize_spoken_code_request(text: str) -> str:
    """Repair common speech-recognition spacing around source filenames."""
    from .coding_languages import EXTENSION_PATTERN
    extensions = r"py|js|jsx|ts|tsx|json|html|css|md|txt|yaml|yml|toml|" + EXTENSION_PATTERN
    text = re.sub(rf"\s*\.\s*(?=(?:{extensions})\b)", ".", text, flags=re.I)
    text = re.sub(
        rf"^(modify|edit|update|fix|refactor|change)([a-z][\w-]*\.(?:{extensions})\b)",
        r"\1 \2", text, flags=re.I)
    return text


def filename(spoken: str) -> str:
    name = re.sub(r"\s+dot\s+", ".", spoken.strip(), flags=re.I)
    name = re.sub(r"\s+\.(?=[a-z0-9]{1,8}$)", ".", name, flags=re.I)
    name = re.sub(r"\.\s+(?=[a-z0-9]{1,8}$)", ".", name, flags=re.I)
    name = re.sub(r"\.text$", ".txt", name, flags=re.I)
    name = re.sub(r"\.([a-z]{1,5})$", lambda m: m.group(0).replace(" ", ""), name)
    if not Path(name).suffix:
        name += ".txt"
    if (not name or name.startswith(".") or name.endswith((" ", "."))
            or any(c in name for c in '<>:"/\\|?*')
            or any(ord(c) < 32 for c in name)
            or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}):
        raise ValueError("Use a simple filename, without folders or reserved characters.")
    return name


def spoken_clean(text: str) -> str:
    """Speech-to-text extras that hide a plain command: "Pause.", "Jarvis, pause please", "hit play"."""
    text = re.sub(r"[.!?,;:]+", " ", text).strip().lower()
    text = re.sub(r"^(?:(?:hey |ok |okay )?jarvis |please |can you |could you |would you |will you |just |hit |press |click )+", "", text)
    text = re.sub(r"(?: please| for me| now| right now| jarvis)+$", "", text).strip()
    text = re.sub(r"^stop (the )?(video|song|music|track|playback)$", r"pause \1\2", text)
    return re.sub(r"\s+", " ", text).strip()


NOW_PLAYING = {"what's playing", "what is playing", "what song is this", "which song is this", "what's this song",
               "what song is playing", "which song is playing", "what video is this", "what's playing now"}


APPROVE_WORDS = re.compile(r"(?:approve(?:d| it| that| the message)?|send it|send that|send the message|yes,? send it|"
                           r"go ahead and send(?: it)?|pick up|pick it up|pick up the call|answer the call|accept the call)", re.I)
REJECT_WORDS = re.compile(r"(?:don'?t send(?: it| that)?|do not send(?: it| that)?|reject(?: it)?|decline(?: it| the call)?|"
                          r"don'?t pick up|do not pick up|ignore the call|hang up|cut the call)", re.I)


def parse(text: str) -> Command:
    cleaned_words = spoken_clean(text)
    if APPROVE_WORDS.fullmatch(cleaned_words):
        return Command("approval_answer", "yes")  # A waiting preview, call or approval card takes it.
    if REJECT_WORDS.fullmatch(cleaned_words):
        return Command("approval_answer", "no")
    if spoken_clean(text) in NOW_PLAYING:
        return Command("spotify_control", "status", "auto")  # Answered by whichever player is in use.
    try:
        command = _parse(text)
    except ValueError:
        cleaned = spoken_clean(text)
        if not cleaned or cleaned == text.strip().lower():
            raise
        command = _parse(cleaned)  # Second attempt only; a matched command is never reinterpreted.
    if (command.kind in {"spotify_control", "spotify_volume"} and not command.extra
            and not re.search(r"spotify|\u0938\u094d\u092a\u0949\u091f\u093f\u092b\u093e\u0908", text, re.I)):
        # "next song", "volume up": no service named, so it follows whatever is playing (see media_player.resolve).
        return Command(command.kind, command.value, "auto")
    return command


def _parse(text: str) -> Command:
    from .repo_tools import command as repository_command
    repository=repository_command(text)
    if repository:return repository
    from .realtime import command as realtime_command
    realtime = realtime_command(text)
    if realtime:
        return Command('realtime', realtime)
    from .anticipation import command as anticipation_command
    proactive = anticipation_command(text)
    if proactive:
        return Command('anticipation', proactive)
    from .island_choices import navigation
    if navigation(text):
        return Command('task', text)  # Local view routing preserves background work.
    text = re.sub(r"^(?:but|and|so|okay|ok)\s+(?=(?:why|what|how|who|where|when|is|are|can)\b)", "", text.strip(), flags=re.I)
    text = re.sub(r"^(?:(?:please|can you|could you|would you)\s+)+", "", text.strip(), flags=re.I)
    text = re.sub(r"^(?:i (?:want|need) you to|can you help me|could you help me|help me)\s+", "", text, flags=re.I)
    from .conversation_intent import normalize as natural
    text = natural(text)  # "let's make an email", "let's watch a video on YouTube"
    # "open YouTube and play X" / "go to Spotify and play X": one fast command, no planning.
    m = re.fullmatch(r"(?:open|launch|start|go to|go on) (youtube|spotify)(?: app)?,?(?: and(?: then)?| then) "
                     r"(?:play|put on|start playing|search for and play|find and play) (.+?)(?: (?:on|in) (?:it|there))?[.!]*", text, re.I)
    if m:
        return Command("play_media", m[2].strip(), m[1].lower())
    text = normalize_spoken_code_request(text)
    from .gmail_workflows import gmail_request
    if gmail_request(text):
        return Command('task', text)
    from .windows_commands import parse as windows_parse
    windows = windows_parse(text)
    if windows:
        return windows
    proactive = anticipation_command(text)
    if proactive:
        return Command('anticipation', proactive)
    if navigation(text):
        return Command('task',text)
    if re.match(r'^save (?:the |this |current )?(?:document|file) as\b', text, re.I):
        return Command('task', text)
    if text.casefold() in {"list toolkits", "toolkit status", "show toolkits"}:
        return Command("toolkit", "toolkit_status", "{}")
    # Do not swallow the next task as a folder name or a GitHub search query.
    if (re.match(r"^(?:read|list|search|scrape|extract)\b", text, re.I)
            and re.search(r"\s+(?:and(?: then)?|then)\s+(?:read|list|search|find|scrape|extract|review|summarize|draft|write|improve|send|email|schedule|create|add|update|modify|edit|delete|remove|post|publish|tell|compare|open|launch|browse|select|click|fill|scroll|press|play|close)\b", text, re.I)):
        return Command("task", text)
    match = re.fullmatch(r"(read|list|search) files? (.+?) in (.+)", text, re.I)
    if match:
        return Command("toolkit", {"read": "read_file", "list": "list_files", "search": "search_files"}[match[1].casefold()],
                       json.dumps({"value": match[2], "folder": match[3]}))
    match = re.fullmatch(r"list files in (.+)", text, re.I)
    if match:
        return Command("toolkit", "list_files", json.dumps({"value": ".", "folder": match[1]}))
    match = re.fullmatch(r"append to file (.+?) in (.+?):\s*(.+)", text, re.I | re.S)
    if match:
        return Command("toolkit", "append_file", json.dumps({"value": match[1], "folder": match[2], "content": match[3]}))
    match = re.fullmatch(r"(?:scrape|extract text from) (https?://\S+)", text, re.I)
    if match:
        return Command("toolkit", "scrape_web", json.dumps({"value": match[1]}))
    match = re.fullmatch(r"search github for (.+)", text, re.I)
    if match:
        return Command("toolkit", "github_search", json.dumps({"value": match[1]}))
    tool = re.fullmatch(r"tool ([a-z_]+)\s+(\{.*\})", text, re.S)
    if tool:
        from .toolkits import TOOLS
        if tool[1] not in TOOLS:
            raise ValueError("Unknown toolkit tool. Say list toolkits.")
        params = json.loads(tool[2])
        if not isinstance(params, dict) or set(params)-{"value", "folder", "content"}:
            raise ValueError("Tool arguments may contain value, folder and content only.")
        return Command("toolkit", tool[1], json.dumps(params))
    if (re.match(r"^(?:fill|scroll|press|use shortcut)\b", text, re.I)
            or re.fullmatch(r"open (?:the )?.+ (?:menu|dropdown)", text, re.I)
            or re.match(r"^open .+? (?:menu|dropdown) and\b", text, re.I)
            or re.fullmatch(r"(?:choose|click|select) .+ (?:in|on) (?:the )?dialog", text, re.I)):
        return Command("task", text)
    if re.fullmatch(r"(?:never ?mind|forget it|scratch that|don'?t do that|do not do that|cancel that)[.!]*", text, re.I):
        return Command("cancel_task", "last")  # Drops the most recent request (or the running one).
    if re.match(r"^(?:do not|don't|never)\b", text, re.I) and not re.match(r"^(?:never ?mind|don'?t do|do not do)\b", text, re.I):
        raise ValueError("No action taken for a negated command.")
    from .memory_curator import parse_command as memory_command
    from .capability_guide import parse_command as capability_command
    from .weather_watch import parse_command as weather_command
    from .repo_learning import parse_command as repo_command
    for special in (memory_command, capability_command, weather_command, repo_command):
        found = special(text)
        if found:
            return found  # "remember that ...", "check your APIs", "is bad weather coming".
    from .whatsapp import parse_command as whatsapp_command
    whatsapp = whatsapp_command(text)
    if whatsapp:
        return whatsapp
    from .messengers import parse_command as messenger_command
    messenger = messenger_command(text)
    if messenger:
        return messenger
    from .media_commands import parse_media
    media = parse_media(text)
    if media:
        return media
    text = re.sub(r"^do\s+(?=(?:open|launch|create|modify|play|search|select|click)\b)", "", text, flags=re.I)
    # Keep a multi-step app workflow intact. Otherwise the generic open rule
    # mistakes 'chrome and search for cats' for an installed application's name.
    if (re.match(r"^(?:open|launch|start|go to|search|find|click|select|choose|play)\b", text, re.I)
            and re.search(r"\s+and\s+(?:open|launch|go to|search|find|click|select|choose|play|pause|create|make|modify|edit|type|write|fill|scroll|press|do|add|save)\b", text, re.I)
            and not re.fullmatch(r"(?:open|launch|start) .+? and (?:write|type|dictate|click|select|choose) .+", text, re.I)
            and not re.fullmatch(r"open (?:chrome|google chrome|edge|firefox) and search(?: for)? .+", text, re.I)):
        return Command("task", text)
    m = re.fullmatch(r"spotify\s+(?:par|pe|mein|पर|पे|में)\s+"
                     r"(agla|अगला|pichla|pehla|पिछला)\s+"
                     r"(?:gana|gaana|song|गाना)\s+"
                     r"(?:chalao|bajao|play karo|चलाओ|बजाओ)", text, re.I)
    if m:
        return Command("spotify_control", "next" if m[1].casefold() in {"agla", "अगला"} else "previous")
    m = re.fullmatch(r"spotify\s+(?:par|pe|mein|पर|पे|में)\s+"
                     r"(?:gana|gaana|music|गाना|म्यूजिक)\s+"
                     r"(roko|rok do|pause karo|रोको|रोक दो|chalao|bajao|play karo|चलाओ|बजाओ)", text, re.I)
    if m:
        return Command("spotify_control", "pause" if m[1].casefold() in {"roko", "rok do", "pause karo", "रोको", "रोक दो"} else "play")
    m = re.fullmatch(r"(?:code|implement|build|fix|refactor) (?:in|for) project (.+?)\s*:\s*(.+)", text, re.I)
    if m:
        return Command("code_task", m[2].strip(), m[1].strip())
    m = re.fullmatch(r"(?:code|add|change|update|improve|write|implement|build|fix|refactor) (.+?) (?:in|to|for) project (.+)", text, re.I)
    if m:
        return Command("code_task", m[1].strip(), m[2].strip())
    from .coder import workspace_coding_request
    if workspace_coding_request(text):
        return Command("task", text)
    if (re.match(r"^(?:create|make|build|add|modify|edit|update)\b", text, re.I)
            and re.search(r"\b(?:folder|script|program|app|project)s?\b", text, re.I)
            and re.search(r"\b(?:and|with)\b", text, re.I)):
        return Command("task", text)
    m = re.fullmatch(r"(?:task|do this task|plan and do) (.+)", text, re.I)
    if m:
        return Command("task", m[1])
    if (re.fullmatch(r"(?:delete|remove)(?: the)? file .+? (?:in|from) (?:the )?.+", text, re.I)
            or re.fullmatch(r"(?:modify|edit)(?: the)? file .+? in (?:the )?.+?:\s*replace .+ with .+", text, re.I)
            or re.fullmatch(r"(?:overwrite|replace entire)(?: the)? file .+? in (?:the )?.+? with (?:content )?.+", text, re.I)
            or re.fullmatch(r"(?:create|make)(?: a| the)? file .+? in (?:the )?.+", text, re.I)):
        return Command("task", text)
    if re.fullmatch(r"(?:(?:open|show) (?:jarvis(?:'s)? )?command prompt|jarvis console)", text, re.I):
        return Command("show_command_prompt")
    m = re.fullmatch(r"(?:run|execute) command (.+)", text, re.I)
    if m:
        return Command("run_command", m[1])
    if re.search(r"\b(?:create|make)\b.*\bfile\b.*\b(?:write|put)\b", text, re.I):
        return Command("task", text)
    if re.search(r"\bopen\s+(?:(?:the|this)\s+)?folder\b.*\b(?:and|then)\s+(?:create|make)\b", text, re.I):
        return Command("task", text)
    if re.fullmatch(r"(?:go to sleep|stop listening|good ?bye|bye(?: jarvis)?|bye bye|that'?s all(?: for now)?|that is all|"
                    r"end (?:the |this )?call|talk (?:to you )?later|see you(?: later)?)[.!]*", text, re.I):
        return Command("end_conversation")  # Queued tasks keep running in the background.
    if re.fullmatch(r"(?:stop|cancel) (?:all|every) tasks?|cancel everything|stop everything|clear the (?:task )?queue|"
                    r"(?:stop|cancel|remove|delete|clear|drop|discontinue|forget)(?: all| every)?(?: of)? (?:the |my )?"
                    r"(?:previous|earlier|older|pending|queued|waiting|other|remaining|old) (?:tasks|requests|jobs)"
                    r"(?: (?:from|in) (?:the |my )?queue)?[.!]*", text, re.I):
        return Command("cancel_all")
    m = re.fullmatch(r"(?:stop|cancel|remove|delete|drop|discontinue|clear)(?: all| everything)?(?: tasks?)? "
                     r"(?:except|but|other than|apart from) (?:the |my )?(.+?)(?: task| one| request)?[.!]*", text, re.I)
    if m:
        return Command("cancel_task", m[1], "except")
    cancel = (r"(?:stop|cancel|discontinue|remove|delete|drop|skip|forget(?: about)?|scrap|abort|kill|"
              r"don'?t do|do not do|never ?mind(?: about)?|no need (?:for|to do))")
    m = (re.fullmatch(cancel + r" (?:the |that |my |this )?(.+?) (?:task|one|request|job|thing)"
                      r"(?: (?:from|in) (?:the |my )?queue)?(?: anymore| any more| please)?[.!]*", text, re.I)
         or re.fullmatch(cancel + r" (?:the |that |my )?(.+?) (?:from|in|out of) (?:the |my )?(?:task )?queue[.!]*", text, re.I)
         or re.fullmatch(r"(?:discontinue|never ?mind(?: about)?|forget about|don'?t do|do not do|no need (?:for|to do)) "
                         r"(?:the |that |my )?(.+?)(?: anymore| any more)?[.!]*", text, re.I)
         or re.fullmatch(r"(?:cancel|remove|delete|drop|skip) (?:task )?(?:number |no\.? |#)(\d{1,2})[.!]*", text, re.I))
    if m and not re.fullmatch(r"(?:this|that|the current|current|it)", m[1].strip(), re.I):
        return Command("cancel_task", m[1].strip())  # A specific queued or running task, by description or position.
    if re.fullmatch(r"(?:cancel|stop|skip)(?: (?:this|that|the current|current) task| it| that)?[.!]*", text, re.I):
        return Command("cancel_current")
    if re.fullmatch(r"(?:what'?s|what is|show(?: me)?|list) (?:in )?(?:the |my )?(?:task )?queue|what are you (?:working on|doing)|"
                    r"(?:task|queue) status|what tasks are (?:left|pending|queued)[?.]*", text, re.I):
        return Command("queue_status")
    if re.fullmatch(r"(?:resume|continue|finish) (?:the |my )?(?:last |unfinished |interrupted )?task|continue where (?:you|we) left off", text, re.I):
        return Command("resume_task")
    if re.fullmatch(r"(?:start|stop|begin|end|enter|exit)(?: the)? (?:dictation|typing|writing)(?: mode)?|dictation(?: mode)?", text, re.I):
        return Command("write_help")  # No dictation mode; push-to-write or a write command instead.
    if re.fullmatch(r"(?:yes|yes please|yeah|yep|do it|no|no thanks|nope)", text, re.I):
        return Command("confirm_suggestion", "no" if text.lower().startswith("no") else "yes")
    if re.fullmatch(r"(?:suggest a button|suggest an option|what do i usually choose)", text, re.I):
        return Command("suggest_control")
    if re.fullmatch(r"forget (?:button|option) memory", text, re.I):
        return Command("forget_ui_memory")
    if re.fullmatch(r"forget (?:our )?(?:conversation|chat history)", text, re.I):
        return Command("forget_chat")
    if re.fullmatch(r"(?:tell me )?(?:(?:which|what) project (?:was|am|have) i (?:using|working on|opened last)|(?:which|what) project i was using|(?:what|which) (?:was )?my (?:last|recent) project)", text, re.I):
        return Command("project_recent")
    if re.fullmatch(r"(?:list|show|open) (?:my |the )?(?:pending|recent|active|unfinished) projects?|(?:open|show|list) (?:my |the )?projects?|(?:what|which) projects? (?:am i working on|are pending)", text, re.I):
        return Command("project_list")
    if re.fullmatch(r"(?:open|launch) (?:my |the )?projects? folder(?:(?: on| from) (?:the )?d drive)?", text, re.I):
        return Command("open_project_root")
    m = re.fullmatch(r"(?:(?:open|launch|start|show) (?:the )?)?god'?s? eye(?: view)?"
                     r"(?: (?:in|on|using) (chrome|edge|firefox))?", text, re.I)
    if m:
        return Command("gods_eye_view", "", (m[1] or "chrome").lower())
    m = re.fullmatch(r"(?:open|launch|start) (?:my |the )?project (.+)", text, re.I)
    if m:
        return Command("open_project", m[1])
    m = re.fullmatch(r"open (?:the )?(?:drive ([a-z])|([a-z])(?:\s*:\s*)? drive)", text, re.I)
    if m:
        return Command("open_drive", (m[1] or m[2]).upper())
    m = re.fullmatch(r"open (?:the )?(.+?) profile", text, re.I)
    if m:
        return Command("click_control", "open " + m[1] + " profile", "select")
    m = re.fullmatch(r"open (chrome|google chrome|edge|firefox)(?: and)? search(?: for)? (.+)", text, re.I)
    if m:
        return Command("browser_search", m[2], m[1].lower())
    m = re.fullmatch(r"search(?: for)? (.+?) (?:on|in|using) (chrome|google chrome|edge|firefox)", text, re.I)
    if m:
        return Command("browser_search", m[1], m[2].lower())
    m = re.fullmatch(r"open (.+?) (?:on|in|using) (chrome|google chrome|edge|firefox)", text, re.I)
    if m:
        return Command("browse", m[1], m[2].lower())
    m = re.fullmatch(r"(?:set |change |turn )?(?:spotify )?volume (?:to )?(\d{1,3})(?: percent|%)?(?: (?:on|in|for) spotify)?", text, re.I)
    if m:
        return Command("spotify_volume", m[1])
    m = re.fullmatch(r"(?:turn )?(?:spotify )?volume (up|down)(?: (?:on|in|for) spotify)?", text, re.I)
    if m:
        return Command("spotify_volume", m[1].lower())
    m = re.fullmatch(r"(increase|raise|decrease|lower|reduce|turn up|turn down) (?:the )?(?:spotify )?volume(?: (?:on|in|for) spotify)?", text, re.I)
    if m:
        return Command("spotify_volume", "up" if m[1].lower() in {"increase", "raise", "turn up"} else "down")
    m = re.fullmatch(r"(mute|unmute)(?: (?:the )?(?:music|audio))?(?: (?:on|in) spotify| spotify)?", text, re.I)
    if m and ("spotify" in text.lower() or "music" in text.lower()):
        return Command("spotify_volume", m[1].lower())
    m = re.fullmatch(r"(?:open|show|find|search(?: for)?) (?:my |the )?playlist (.+?)(?: (?:on|in) spotify)?", text, re.I)
    if m:
        return Command("spotify_open_playlist", m[1])
    m = re.fullmatch(r"(pause|resume|play|next|previous|skip|shuffle|repeat|what(?:'s| is) playing)(?: (?:the |my )?(?:music|song|track|playback))?(?: (?:on|in) spotify| spotify)?", text, re.I)
    if m and ("spotify" in text.lower() or any(word in text.lower().split() for word in ("music", "song", "track"))
              or m[1].lower() in {"next", "previous", "skip", "shuffle", "repeat", "what's playing", "what is playing"}):
        name = m[1].lower()
        return Command("spotify_control", {"resume": "play", "skip": "next", "shuffle": "shuffle_on", "repeat": "repeat_all",
                                           "what's playing": "status", "what is playing": "status"}.get(name, name))
    m = re.fullmatch(r"(?:play|skip|go) (?:the )?(next|previous) (?:song|track)(?: (?:on|in) spotify)?", text, re.I)
    if m:
        return Command("spotify_control", m[1].lower())
    m = re.fullmatch(r"(?:play |skip |go |)(next|previous|forward|back|backward)(?: (?:song|track|music))?(?: (?:on|in) spotify)?", text, re.I)
    if m:
        return Command("spotify_control", "previous" if m[1].lower() in {"previous", "back", "backward"} else "next")
    m = re.fullmatch(r"(?:turn |set )?(shuffle|repeat) (on|off|one|all)(?: (?:on|in) spotify)?", text, re.I)
    if m:
        return Command("spotify_control", m[1].lower() + "_" + m[2].lower())
    m = re.fullmatch(r"(?:seek|skip|fast forward|rewind) (?:spotify )?(?:by )?(\d{1,4}) seconds?(?: (?:on|in) spotify)?", text, re.I)
    if m:
        return Command("spotify_control", "seek_" + ("-" if text.lower().startswith("rewind") else "") + m[1])
    m = re.fullmatch(r"(?:play|put on|start playing) (.+?) (?:on|from|in|using) (spotify|youtube)", text, re.I)
    if m:
        return Command("play_media", m[1], m[2].lower())
    if re.fullmatch(r"(?:close|quit|exit)(?: (?:the )?(?:(?:current|active) )?(?:app|application|window))?", text, re.I):
        return Command("close_app", "this app")
    m = re.fullmatch(r"(?:close|quit|exit) (.+?)(?: app| application| window)?", text, re.I)
    if m:
        return Command("close_app", m[1])
    m = re.fullmatch(r"(?:skip|fast forward|go forward|jump ahead|skip ahead|forward)(?: by)? (\d{1,4}) seconds?", text, re.I)
    if m:
        return Command("spotify_control", "seek_" + m[1])
    m = re.fullmatch(r"(?:rewind|go back|jump back|back)(?: by)? (\d{1,4}) seconds?", text, re.I)
    if m:
        return Command("spotify_control", "seek_-" + m[1])
    m = re.fullmatch(r"(mute|unmute)(?: (?:it|that|this|the sound|sound))?", text, re.I)
    if m:
        return Command("spotify_volume", m[1].lower())
    if re.fullmatch(r"(?:skip|next)(?: (?:this|the))? (?:song|track|one)", text, re.I):
        return Command("spotify_control", "next")
    if re.fullmatch(r"(?:repeat|loop) (?:this|the) (?:song|track)", text, re.I):
        return Command("spotify_control", "repeat_one")
    if re.fullmatch(r"(?:pause|stop|resume|continue|play) (?:it|that|this|the song|the music|the track|playback)", text, re.I):
        return Command("click_control", "pause" if text.lower().startswith(("pause", "stop")) else "play", "click")
    if re.fullmatch(r"(?:pause|play|resume)(?: (?:the )?(?:video|button))?", text, re.I):
        return Command("click_control", "play" if text.lower().startswith("resume") else text.split()[0].lower(), "click")
    if re.fullmatch(r"(?:play (?:it|that|this|the song|the video) again|replay(?: it| that| this)?|start (?:it |the song |the video )?over)[.!]*", text, re.I):
        return Command("media_control", "restart", "")  # Whatever is playing on the service in use.
    m = re.fullmatch(r"(?:play|put on|start playing)(?: me)? (?:the song |the track |the video |song |music |some )?(.{2,120}?)[.!]*", text, re.I)
    if m and not re.fullmatch(r"(?:(?:it|that|this)(?: again| back)?|again|music|something|anything|the (?:first|second|third|next|previous) .+|"
                              r"(?:first|second|third|next|previous) .+|\d+(?:st|nd|rd|th)? .+)", m[1].strip(), re.I):
        return Command("play_media", m[1].strip(), "")  # Service: the one just used/opened, else the default.
    if re.fullmatch(r"(?:button|buttons|option|options|control|controls) list", text, re.I):
        return Command("list_controls")
    m = re.fullmatch(r"(?:search (?:the )?(?:web|internet)(?: for)?|look up) (.+)", text, re.I)
    if m:
        return Command("ask", m[1], "web")
    m = re.fullmatch(r"search(?: for)? (.+)", text, re.I)
    if m:
        return Command("context_search", m[1])
    if re.match(r'^(?:give|show|provide)(?: me)? (?:a |the |some )?(?:(?:c\+\+|c#|python|javascript|typescript|java|rust|go|html|css)\s+)?(?:code|source code)\b', text, re.I):
        return Command('ask', text)
    m = re.fullmatch(r"(?:ask|question|answer this) (.+)", text, re.I)
    if m:
        return Command("ask", m[1])
    if re.fullmatch(r"(?:hi|hello|hey|good morning|good afternoon|good evening|namaste|नमस्ते|how are you(?: doing)?|how's it going|thanks|thank you|धन्यवाद|time|date|weather|temperature|mausam|मौसम)[?.! ]*", text, re.I):
        return Command("ask", text)
    if re.match(r"^(?:today'?s|current|local) (?:weather|temperature|time|date)\b", text, re.I):
        return Command("ask", text)
    if re.fullmatch(r"(?:weather|temperature)(?: today| tomorrow)?(?: (?:in|for) [a-z][a-z ,]{1,60})?[?.! ]*", text, re.I):
        return Command("ask", text)
    if re.match(r"^(?:convert|multiply|divide|flip a coin|roll a di(?:e|ce)|pick a random number|split a bill|calculate a|find the percentage)\b", text, re.I):
        return Command("ask", text)
    if re.match(r"^(?:time in|current exchange rate of)\b", text, re.I):
        return Command("ask", text)
    if (re.match(r"^(?:mujhe\s+)?(?:batao|samjhao)\b", text, re.I)
            or re.search(r"\b(?:kya|kaise|kyun|kab|kahan|kaun|kitna|kitni|kaisa|kaisi)\b", text, re.I)
            or re.search(r"(?:बताओ|समझाओ|क्या|कैसे|क्यों|कब|कहाँ|कहां|कौन|कितना|कितनी|कैसा|कैसी)", text)):
        return Command("ask", text)
    if re.match(r"^(?:what|who|when|where|why|how|which|explain|tell me|describe|is|are|does|do|can|should|will)\b", text, re.I):
        return Command("ask", text)
    if re.fullmatch(r"(?:list|show)(?: the)? (?:buttons|options|controls)", text, re.I):
        return Command("list_controls")
    ordinal_words = {"first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
        "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10",
        "pehla": "1", "pehli": "1", "dusra": "2", "doosra": "2", "dusri": "2",
        "teesra": "3", "teesri": "3"}
    m = re.fullmatch(r"(?:click|select|choose|open|play)(?: on)? (?:the )?"
        r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|pehla|pehli|dusra|doosra|dusri|teesra|teesri|\d+(?:st|nd|rd|th)?) "
        r"(video|videos|vido|result|results|option|options|button|buttons|item|items|link|links)(?: (?:on|in) youtube)?[.!?]*", text, re.I)
    if m:
        number = ordinal_words.get(m[1].lower(), re.match(r"\d+", m[1])[0] if m[1][0].isdigit() else "")
        kind = re.sub(r"s$", "", m[2].lower()).replace("vido", "video")
        return Command("select_context", number + ":" + kind, "select")
    m = re.fullmatch(r"(?:click|select|choose)(?: on)? (?:this|that|yeh|is) (option|button|video|result|item|link)", text, re.I)
    if m:
        return Command("select_context", "this:" + m[1].lower(), "select")
    m = re.fullmatch(r"(?:yeh|is) (option|button|video|result|item|link) (?:select|click) (?:karo|kar do)", text, re.I)
    if m:
        return Command("select_context", "this:" + m[1].lower(), "select")
    m = re.fullmatch(r"(?:(?:click|select|choose)(?: on)?(?: the)? )?(?:option(?: number)?|number) (\d+|one|two|three|four|five|six|seven|eight|nine|ten)[.!?]*", text, re.I)
    if m:
        numbers = "one two three four five six seven eight nine ten".split()
        number = str(numbers.index(m[1].lower()) + 1) if m[1].lower() in numbers else m[1]
        return Command("choose_control", number)
    m = re.fullmatch(r"(click|select|choose)(?: on)?(?: the)? (.+)", text, re.I)
    if m:
        label = re.sub(r"^(?:button|option|tab)\s+|\s+(?:button|option|tab)$", "", m[2], flags=re.I).strip()
        if label:
            return Command("click_control", label, "select" if m[1].lower() in {"select", "choose"} else "click")
    m = re.fullmatch(r"open (?:the )?(file|folder) (.+)", text, re.I)
    if m:
        target = m[2] if m[1].lower() == 'folder' else re.sub(r"\s+(?:on|from) (?:the )?d drive$", "", m[2], flags=re.I)
        return Command("open_" + m[1].lower(), target)
    m = re.fullmatch(r"(?:open|launch|start) (?:the )?(.+)", text, re.I)
    if m:
        from .folder_lookup import folder_request
        target, drive = folder_request(m[1])
        if drive or re.search(r"\s+(?:folder|directory)$", m[1], re.I):
            return Command('open_folder', m[1])
    m = re.fullmatch(r"(?:open|launch|start) (?:the )?(.+?)(?: app)?", text, re.I)
    if m:
        return Command("open", m[1].lower())
    from .writing import parse_write
    written = parse_write(text)  # "write a note here" (composed) or "write exactly ..." (verbatim)
    if written:
        return written
    m = re.fullmatch(r"(?:create|make)(?: a| the)? file (?:called |named )?(.+?)(?: (?:containing|with content) (.+))?", text, re.I)
    if m:
        return Command("create", filename(m[1]), m[2] or "")
    m = re.fullmatch(r"(?:rename|name)(?: the)? file (.+?) to (.+)", text, re.I)
    if m:
        return Command("rename", filename(m[1]), filename(m[2]))
    m = re.fullmatch(r"(?:modify|edit)(?: the)? file (.+?) replace (.+?) with (.+)", text, re.I)
    if m:
        return Command("modify", filename(m[1]), json.dumps({"find": m[2], "content": m[3]}))
    m = re.fullmatch(r"(?:overwrite|replace entire)(?: the)? file (.+?) with (?:content )?(.+)", text, re.I)
    if m:
        return Command("modify", filename(m[1]), json.dumps({"find": "", "content": m[2]}))
    m = re.fullmatch(r"delete(?: the)? file (.+)", text, re.I)
    if m:
        return Command("delete", filename(m[1]))
    raise ValueError(f"Command not understood: {text}")
