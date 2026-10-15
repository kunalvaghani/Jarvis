"""Everyday requests that have no dedicated phrase elsewhere, mapped to what Jarvis can really do.

Input is canonical text (see phrasing.py). Each rule maps one family of sentences to an existing command
(open, media, queue, memory, God's Eye, repos ...) or to one of the honest local kinds handled in
intent_handlers.py:

- behavior: a standing instruction or "how do you handle ..." question, answered with what Jarvis
  actually does (or plainly says is not supported yet). Never an action.
- conversation_style: short/simple/serious answers, slower speech, private or quiet mode, for this session.
- repeat_last: say the last reply again (or only its last sentence).
- jarvis_status / system_info: read-only facts about Jarvis or this PC, answered without the queue.
- whatsapp_read, gods_eye_camera, media_related, memory_summarize, messenger_focus: read or view actions.

Rules are full matches, so a sentence that only contains these words is left to the normal routing.
"""
import json
import re

from .commands import Command

C = Command
FLAGS = re.I


def gev(**spec):
    return C("gods_eye_show", json.dumps(spec))


def cam(**spec):
    return C("gods_eye_camera", json.dumps(spec))


GERUND = {"opening": "open", "playing": "play", "sending": "send", "writing": "write", "searching": "search",
          "checking": "check", "reading": "read", "learning": "learn", "drafting": "draft", "showing": "show",
          "launching": "launch", "starting": "start", "closing": "close", "finding": "find", "running": "run"}


def queued(phrase):
    """'add opening Notepad to the queue' -> the command for 'open Notepad' (queued like any request)."""
    from .commands import _parse
    words = phrase.strip().split(" ", 1)
    verb = GERUND.get(words[0].casefold(), words[0])
    request = verb + (" " + words[1] if len(words) > 1 else "")
    if re.fullmatch(r"play (?:a |some )?(?:song|music|track)s?", request, FLAGS):
        return C("behavior", "which_song")
    try:
        return _parse(request)
    except ValueError:
        return C("task", request)


HAZARDS = ["weather-radar", "weather-lightning", "weather-cyclones", "earthquakes", "local-firms", "fire-perimeters"]

# (pattern, builder). Builders take the match. Order matters only between overlapping patterns.
RULES = [
    (r"(?:refresh|reload|update|add|load) (?:the )?(?:god'?s eye )?(?:cctv|camera)s?(?: cameras| feeds| pack| list)?(?: for .+| in .+)?|"
     r"add (?:cctv|cameras) (?:for|in) .+", lambda m: C("gods_eye_cameras", "refresh")),
    (r"why (?:can'?t|cannot|don'?t|do not) i see (?:any |the )?(?:cctv|cameras?|camera feeds?)(?: .*)?|"
     r"(?:which|what) (?:cities|places|countries|regions) have (?:live )?(?:cctv|cameras)(?: .*)?|"
     r"(?:is there|are there) (?:any )?(?:live )?(?:cctv|cameras) (?:in|for) .+", lambda m: C("gods_eye_cameras", "coverage")),
    # --- references and compound requests the planner or a question should resolve --------------------------
    (r"open (?:my |the )?(?:latest|most recent) (?:spreadsheet|document|file|report)",
     lambda m: C('task', m[0])),
    (r"turn (?:the )?sound (up|down) a notch", lambda m: C('spotify_volume', m[1].lower(), 'auto')),
    (r"pause what(?:'s| is) playing", lambda m: C('click_control', 'pause', 'click')),
    (r"i said close (?:this|the) tab,? not the browser", lambda m: C('windows_command', '[329]', '{}')),
    (r"open youtube,? (?:find|search for) (.+?),? and play (?:the official video|it|the official version)",
     lambda m: C("play_media", m[1] + (" official" if "official" in m[0].lower() else ""), "youtube")),
    (r"search (youtube|spotify) for (.+?),? (?:and )?play it(?:,? .*)?", lambda m: C("play_media", m[2], m[1].casefold())),
    (r"open (?:the one|that one|that file|this file|the file|that thing|the thing|it|that) .+|open the map and point out .+|"
     r"open a project,? .+|(?:open|bring up|launch|start) [^,]+, .+ and .+|start two independent tasks.*",
     lambda m: C("task", m[0]) if not m[0].lower().startswith("start two") else C("behavior", "queue_order")),
    (r"show where this region is(?: on the globe)?|fly to the place i just mentioned", lambda m: C("task", m[0])),
    (r"show (?:me )?nearby military (?:installations|bases)(?: on the map)?", lambda m: gev(place="me", layers=["military-installations"],
                                                                                           kind="military-installations")),
    (r"search for a research paper using a scholarly api", lambda m: C("behavior", "research_usage")),
    (r"find a public launch schedule|(?:when is|what are) the next (?:rocket )?launch(?:es)?", lambda m: C("ask", "upcoming rocket launch schedule")),
    (r"get recent earthquakes from a public feed", lambda m: C("ask", "recent earthquakes worldwide")),
    (r"look up a github repo,? learn its structure and summari[sz]e it", lambda m: C("behavior", "which_repo")),
    (r"queue a coding task,? then play music while it works", lambda m: C("behavior", "coding_and_music")),
    (r"write (?:unit )?tests? for .+", lambda m: C("task", m[0])),

    # --- conversation, wake word and voice ---------------------------------------------------------------
    (r"(?:start a conversation|keep listening|stay awake|continue the conversation)(?: .*)?", lambda m: C("behavior", "conversation_mode")),
    (r"(?:answer|respond to) me even if .*|you don'?t need (?:a )?command words.*", lambda m: C("behavior", "no_command_words")),
    (r"(?:do not|don'?t) treat this as a task.*|i'?m (?:just )?thinking (?:aloud|out loud).*", lambda m: C("conversation_style", "chat_only")),
    (r"i'?m (?:feeling )?(?:tired|bored|sad|happy|stressed|sleepy)\b.*", lambda m: C("ask", m[0])),
    (r"(?:give me|tell me|say) (?:a |another )?(?:quick |short |funny )?joke", lambda m: C("ask", "Tell me a quick joke.")),
    (r"(?:be|stay|keep it) serious(?: .*)?|(?:do not|don'?t) (?:make|tell) (?:a )?jokes?(?: .*)?|no jokes(?: .*)?",
     lambda m: C("conversation_style", "serious")),
    (r"(?:speak|talk) (?:a (?:little|bit) )?(?:more )?slow(?:ly|er)|slow down (?:your|the) (?:voice|speech)",
     lambda m: C("conversation_style", "slower")),
    (r"(?:speak|talk) (?:a (?:little|bit) )?(?:more )?(?:quickly|faster)|speed up (?:your|the) (?:voice|speech)",
     lambda m: C("conversation_style", "faster")),
    (r"(?:speak|talk) (?:at )?(?:normal|regular) speed|normal (?:voice|speech) speed", lambda m: C("conversation_style", "normal_voice")),
    (r"sound (?:less robotic|more natural|more human)|(?:your voice|you) sound(?:s)? robotic", lambda m: C("behavior", "voice")),
    (r"(?:say|repeat) (?:that|it|what you said) again(?:,? please)?|(?:repeat|say) that|come again|pardon|what did you say",
     lambda m: C("repeat_last", "all")),
    (r"repeat (?:only |just )?(?:the |your )?last (?:sentence|line|part)", lambda m: C("repeat_last", "sentence")),
    (r"(?:stop|quit) talking.*|be quiet.*|shut up.*|hush.*|stop speaking.*", lambda m: C("stop_speaking", "")),
    (r"let me interrupt.*|(?:can|may) i interrupt.*", lambda m: C("behavior", "barge_in")),
    # Screen pre-awareness and app knowledge (screen_awareness.py, app_knowledge.py).
    (r"(?:what|which) apps (?:do i have|have i got|are (?:installed|on (?:my|this) (?:pc|computer|laptop)))|list (?:all )?(?:of )?my (?:apps|programs|applications)|"
     r"what (?:apps|programs|software) (?:do i have|are installed)(?: on (?:my|this) (?:pc|computer|laptop))?",
     lambda m: C("screen_info", "apps")),
    (r"what (?:does|can) this (?:app|program|application) do|what is this (?:app|program|application)|what can (?:you|i) do (?:in|with) this (?:app|program)|"
     r"what are (?:the )?features of this (?:app|program)", lambda m: C("screen_info", "this_app")),
    (r"what buttons (?:are there|are on (?:the )?screen|does this app have|can you see|are here)(?: here| on screen)?|(?:list|show|tell me) the buttons (?:on (?:the )?screen|here|in this app)",
     lambda m: C("screen_info", "buttons")),
    (r"(?:stop|don'?t keep) asking (?:me )?about (?:this app|this screen|what'?s on (?:the )?screen)|don'?t ask (?:me )?about this app(?: again)?",
     lambda m: C("screen_info", "mute_app")),
    (r"(?:pause|stop|turn off|disable|switch off) (?:the )?screen (?:suggestions|awareness|questions|offers)|stop asking (?:me )?(?:questions )?about (?:my|the) screen",
     lambda m: C("screen_info", "pause")),
    (r"(?:resume|start|turn on|enable|switch on) (?:the )?screen (?:suggestions|awareness|questions|offers)", lambda m: C("screen_info", "resume")),
    (r"what can you do (?:here|on this screen|for me here|in this window)|help me with (?:this|what'?s on (?:the|my)) (?:app|screen|window)|"
     r"any suggestions (?:here|for (?:this|my) screen)|what would you suggest here", lambda m: C("screen_info", "offer_now")),
    # Cognitive architecture (cognition.py): working memory, world-model predictions, lessons.
    (r"(?:what(?:'s| is) (?:in )?|show (?:me )?|tell me (?:what'?s in )?)?your working memory|what are you (?:thinking|focus(?:s)?ing) (?:about|on)(?: right now)?|"
     r"what are you thinking(?: right now)?|(?:what(?:'s| is) (?:your )?)?cogniti(?:on|ve) (?:status|loop|state)|"
     r"how(?:'s| is) your (?:mind|brain|cognitive loop)(?: doing)?|what(?:'s| is) on your mind",
     lambda m: C("jarvis_status", "cognition")),
    (r"what (?:have you|did you) learn(?:ed|t)? from (?:your |the )?(?:mistakes|failures|corrections|last (?:tasks|actions))|"
     r"(?:show|tell me|list) (?:me )?(?:your |the )?lessons(?: (?:you'?ve |you have )?learned)?|what lessons have you learned",
     lambda m: C("jarvis_status", "lessons")),
    (r"(?:what would|what will|what'?d) happen if (?:you|i (?:asked|told) you to|we) (.+)|"
     r"(?:predict|simulate) what (?:would happen|happens|will happen) if (?:you|i (?:asked|told) you to) (.+)|"
     r"before you do it,? (?:tell me )?what would happen if you (.+)",
     lambda m: C("cognition_predict", next(g for g in m.groups() if g))),
    (r"(?:explain|describe|tell me about) (?:your|the jarvis) (?:cognitive )?architecture|how do you think|how does your (?:mind|brain) work",
     lambda m: C("behavior", "architecture")),
    (r"(?:keep|make) (?:your |the )?(?:answers?|replies|responses?) (?:short|brief|concise)(?: .*)?|"
     r"(?:short|brief) answers?(?: please)?|earlier i asked for a short answer.*", lambda m: C("conversation_style", "short")),
    (r"(?:give me|explain|say) (?:it |that )?(?:the |a )?simple(?:r)? (?:version|way|terms)|(?:explain|say) (?:it|that) simply|"
     r"(?:in )?simple(?:r)? terms", lambda m: C("conversation_style", "simple", "Give me a simpler version of your last answer.")),
    (r"(?:do not|don'?t) interrupt me.*", lambda m: C("behavior", "final_only")),
    (r"have we been (?:talking|chatting) (?:for )?long|how long have we been (?:talking|chatting)|how long have you been (?:on|running|awake)",
     lambda m: C("jarvis_status", "uptime")),
    (r"i'?m still here.*|(?:do not|don'?t) (?:go to sleep|sleep)(?: yet)?", lambda m: C("behavior", "still_here")),
    (r"good ?bye(?: for now)?|bye for now|end (?:our|this|the) conversation(?: .*)?|go to sleep(?: .*)?|"
     r"that'?s all for now|talk to you later|see you later", lambda m: C("end_conversation")),
    (r"wake up(?: and)? (?:tell me )?what happened(?: while i was (?:away|gone))?|what happened while i was (?:away|gone)|"
     r"what did i miss", lambda m: C("jarvis_status", "while_away")),
    (r"i didn'?t mean (?:that|it) (?:as an instruction|literally)|that was (?:a joke|just a joke|sarcasm)(?:,? not .*)?|"
     r"i was (?:only )?joking", lambda m: C("cancel_task", "last")),
    (r"(?:can you )?remember the (?:tone|style) i asked for(?: .*)?|what (?:tone|style) did i ask for(?: .*)?",
     lambda m: C("jarvis_status", "style")),

    # --- Windows, apps, processes ----------------------------------------------------------------------
    (r"bring (.+?) (?:to the front|to front|back from the taskbar|back|up front)|put (?:the )?(.+?) window on top|"
     r"switch to (whatsapp|spotify|chrome|notepad|telegram|discord|word|excel|vs ?code)(?: window)?",
     lambda m: C("open", (m[1] or m[2] or m[3]).strip().casefold())),
    (r"switch (?:back )?to (?:my |the )?(?:previous|last|other) (?:window|app|application)|go back to (?:my |the )?previous (?:window|app)|"
     r"open the (?:program|app|application) i used (?:a moment ago|before|last|just now)|alt tab",
     lambda m: C("windows_command", "[257]", "{}")),
    (r"show (?:me )?(?:all )?(?:my )?(?:open|running) windows|task view", lambda m: C("windows_command", "[258]", "{}")),
    (r"minimi[sz]e (?:the |this )?(?:current |active )?(?:app|window|application)?", lambda m: C("windows_command", "[272]", "{}")),
    (r"maximi[sz]e (?:the |this )?(?:current |active )?(?:app|window|application)?", lambda m: C("windows_command", "[271]", "{}")),
    (r"close (?:this|the current|the) (?:browser )?tab(?:,? not the (?:entire|whole) browser)?", lambda m: C("windows_command", "[329]", "{}")),
    (r"show (?:me )?(?:my |the )?desktop|minimi[sz]e (?:all|every)(?: windows| apps)?", lambda m: C("windows_command", "[259]", "{}")),
    (r"(?:drag|move|snap) (?:that|this|the) window (?:to the )?(left|right)", lambda m: C("windows_command", "[269]" if m[1].lower() == "left" else "[270]", "{}")),
    (r"move (?:this|that|the) window to (?:the )?(?:other|next|second) (?:monitor|screen|display)", lambda m: C("behavior", "other_monitor")),
    (r"find (?:the )?(.+?) app(?: installed)?(?: on this pc| on my pc| on this computer)?|is (.+?) installed(?: on this pc)?",
     lambda m: C("system_info", "installed", (m[1] or m[2]).strip())),
    (r"find (?:the |my )?(?:file|files|download|downloads) i (?:downloaded|saved) (?:earlier|recently|today|last)|"
     r"(?:what|which) (?:files )?did i download (?:recently|today|last)|(?:show|list) (?:my )?recent downloads",
     lambda m: C("system_info", "downloads")),
    (r"open (?:a|the) folder i (?:mention|say|name)(?: .*)?", lambda m: C("behavior", "open_folder_usage")),
    (r"(?:tell me |show me |list )?(?:what|which) (?:programs|apps|applications|windows) are (?:currently )?(?:running|open)(?: right now)?|"
     r"list (?:the )?(?:running|open) (?:programs|apps|applications)", lambda m: C("system_info", "apps")),
    (r"close (notepad|word|excel|chrome|.+?) without (?:deleting|losing|discarding) (?:unsaved|my) (?:notes|work|changes)",
     lambda m: C("close_app", m[1])),
    (r"(?:tell me )?(?:whether|if) (.+?) is (?:already |currently |still )?running|is (.+?) (?:already |currently |still )?running",
     lambda m: C("system_info", "running", (m[1] or m[2]).strip())),
    (r"(?:show |show me |tell me )?(?:my |the )?(?:battery(?: level| status)?|battery percentage)|(?:what is|what's|check) (?:my |the )?battery(?: level| status| percentage)?",
     lambda m: C("system_info", "battery")),
    (r"show (?:me )?(?:the )?cpu (?:usage|load)", lambda m: C("system_info", "quick_cpu")),
    (r"(?:show me |tell me )?how much (?:cpu|processor) (?:i'?m|am i|is being|are we) using(?: right now)?|(?:what'?s|what is) (?:my |the )?cpu (?:usage|load)|cpu usage",
     lambda m: C("system_info", "cpu")),
    (r"how much (?:memory|ram) is (?:free|available|used|left)(?: right now)?|(?:what'?s|what is) (?:my |the )?(?:memory|ram) usage|(?:memory|ram) usage",
     lambda m: C("system_info", "memory")),
    (r"check (?:the )?gpu(?: model)?(?: and vram)?|(?:what|which) gpu (?:do i have|is this)|how much vram(?: do i have| is available| is free)?(?: for inference)?|"
     r"(?:what'?s|what is) (?:my |the )?gpu", lambda m: C("system_info", "gpu")),
    (r"(?:what'?s|what is) my windows version|which (?:version of )?windows (?:am i|is this)(?: running)?|windows version",
     lambda m: C("system_info", "windows")),
    (r"show (?:me )?(?:the )?(?:active|running) services|(?:what|which) services are running", lambda m: C("system_info", "services")),
    (r"find the app whose window is hidden|(?:which|what) (?:apps?|windows?) (?:are|is) (?:hidden|minimi[sz]ed)",
     lambda m: C("system_info", "minimized")),
    (r"switch to the right chrome tab|switch to the right tab", lambda m: C("behavior", "which_tab")),
    (r"show (?:me )?which process is slowing (?:the|my) (?:machine|pc|computer)|(?:what|which) (?:process|app) is slowing (?:the|my) (?:machine|pc|computer)(?: down)?|"
     r"(?:what|which) (?:process|app) is using (?:the most|most|all the) (?:cpu|memory|ram)", lambda m: C("system_info", "top")),
    (r"(?:check )?(?:whether |if )?(?:an |any )?(?:application|app|program)s? (?:has |have )?stopped responding|(?:is|are) (?:any )?(?:apps?|programs?) (?:frozen|not responding)",
     lambda m: C("system_info", "not_responding")),
    (r"restart (?:only )?the frozen (?:application|app)(?: .*)?", lambda m: C("behavior", "restart_frozen")),
    (r"(?:tell me )?what (?:did you|you) change(?:d)? on (?:my|the) (?:desktop|screen|pc)(?: just now)?", lambda m: C("jarvis_status", "recent_actions")),

    # --- pointer, clicking, screen ---------------------------------------------------------------------
    (r"(?:select|choose|click|open) (?:the )?(first|second|third|fourth|fifth) (?:search )?result", lambda m: C("select_context",
     {"first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5"}[m[1].lower()] + ":result", "select")),
    (r"open (?:the )?drop-?down(?: menu)? and (?:choose|select|pick) .+", lambda m: C("task", m[0])),
    (r"click outside the dialog.*|dismiss (?:the |this )?dialog", lambda m: C("task", m[0])),
    (r"select all(?: the)? text(?: in this field| in the field| here)?|select everything(?: here)?", lambda m: C("task", "press ctrl+a to select all the text in the focused field")),
    (r"(?:focus|click) the search (?:box|bar|field) and type .+", lambda m: C("task", m[0])),
    (r"find (?:the )?.+? (?:button|option|link|menu)(?: .*)?|i can'?t see the .+? (?:button|option)(?:; find it| .*)?", lambda m: C("task", m[0])),
    (r"(?:move|shift) your (?:own )?(?:cursor|pointer) over (?:that|the|this) .+", lambda m: C("task", m[0])),
    (r"use your (?:own )?pointer without (?:stealing|taking|moving) my mouse.*", lambda m: C("behavior", "pointer")),
    (r"wait until i stop moving (?:my|the) mouse(?: before clicking)?", lambda m: C("behavior", "pointer_wait")),
    (r"(?:tell me )?what (?:button|control|element|thing) is under (?:my|the) (?:cursor|mouse|pointer)", lambda m: C("system_info", "under_cursor")),
    (r"(?:which|what) (?:application|app|window) (?:currently )?has (?:the )?(?:keyboard )?focus|(?:which|what) (?:window|app) am i (?:in|using)|"
     r"i changed windows;? which one are we talking about", lambda m: C("system_info", "foreground")),
    (r"(?:do not|don'?t) click if (?:another|a) window (?:covers|is covering|blocks) .*", lambda m: C("behavior", "click_cover")),
    (r"click only once.*|(?:do not|don'?t) click twice.*", lambda m: C("behavior", "click_once")),
    (r"(?:the )?(?:button|click) did nothing.*|that click didn'?t work.*", lambda m: C("task", m[0])),
    (r"go back to the (?:last|previous) page|(?:go )?back a page|browser back", lambda m: C("task", "go back to the previous page in the browser")),
    (r"(?:do not|don'?t) touch my keyboard.*|(?:do not|don'?t) type while i(?:'m| am)? typing.*", lambda m: C("behavior", "keyboard")),

    # --- writing and push-to-write ------------------------------------------------------------------------
    (r"compose (.+)", lambda m: _write("write " + m[1])),
    (r"write (?!.*\b(?:script|program|function|class|code|tests?|module|api|website|game)\b)(.+?) (?:in|into) (?:this|the current|the active) (?:app|window|document)",
     lambda m: _write(m[0])),
    (r"use the local model to improve .*", lambda m: C("behavior", "writing_model")),
    (r"(?:fix|correct|check) the (?:grammar|spelling)(?: .*)?|(?:make|rewrite) the text you (?:just )?wrote .*|"
     r"expand (?:that|the) answer into .+ here|make (?:it|that|the text) (?:shorter|longer|more formal|more casual)(?: here)?",
     lambda m: C("task", m[0])),
    (r"(?:start|insert|add) a new (?:paragraph|line)(?:[ ,].*)?|type quotation marks around .+|put this exact title .+|"
     r"put the drafted message into .+|copy the (?:paragraph|text|draft|message) (?:we|you) (?:drafted|wrote) to the clipboard",
     lambda m: C("task", m[0])),
    (r"(?:do not|don'?t) change my (?:punctuation|words|capitali[sz]ation).*", lambda m: C("behavior", "exact_text")),
    (r"write into the current window.*|(?:do not|don'?t) (?:enter|type) (?:any )?text until .*|confirm the target window .*",
     lambda m: C("behavior", "target_window")),
    (r"open (\w[\w ]*?) first,? (?:and )?then (.+)", lambda m: C("task", m[0])),
    (r"hold left (?:control|ctrl) and left alt.*|i want push-to-write .*|stop (?:typing|writing) (?:as soon as|when) i (?:release|let go).*|"
     r"when i let go,? stop .*|while i hold the shortcut.*|during that key hold.*|ignore voice commands during push-to-write|"
     r"cancel the unfinished phrase if i press another key|go back to normal listening after push-to-write|"
     r"(?:how does|what is) push[- ]to[- ]write(?: work)?", lambda m: C("behavior", "push_to_write")),
    (r"before overwriting (?:that|the|a) file,? show me the changes|ask me before overwriting .*", lambda m: C("behavior", "overwrite")),
    (r"the text went to the wrong (?:app|window).*", lambda m: C("cancel_current")),
    (r"read back (?:the )?(?:exact )?text you (?:entered|typed|wrote)", lambda m: C("repeat_last", "typed")),

    # --- Gmail -----------------------------------------------------------------------------------------
    (r"(?:explain )?why (?:does )?gmail (?:needs|need|wants|asks) me to sign in(?: again)?|is gmail (?:still )?(?:authenticated|signed in|connected)|"
     r"(?:tell me )?if the api session has expired", lambda m: C("jarvis_status", "gmail")),
    (r"(?:tell me )?(?:what|which) approvals? (?:are )?you(?:'re| are)? waiting (?:for|on)|what were you waiting for me to approve|"
     r"show (?:me )?the pending approvals.*|(?:tell me )?what (?:still )?needs (?:manual )?approval|(?:tell me )?exactly what (?:an|the|this) approval will authori[sz]e",
     lambda m: C("jarvis_status", "approvals")),
    (r"approve (?:only )?(?:this|the) gmail action|approve (?:and send )?(?:only )?the (?:previewed |message )?(?:message|preview)|"
     r"(?:yes,? )?approve only the message preview|i said yes to the call.*", lambda m: C("approval_answer", "yes")),
    (r"(?:do not|don'?t) send(?: it)?;? (?:revise|change|edit) .*|(?:do not|don'?t) send;? i changed my mind|never ?mind,? leave it as a draft|"
     r"cancel the send;? keep the draft|i said cancel,? so do not execute the pending action", lambda m: C("approval_answer", "no")),

    # --- WhatsApp, calls, other messengers --------------------------------------------------------------
    (r"open (whatsapp|telegram) desktop", lambda m: C("open", m[1].casefold())),
    (r"find (?:the )?chat with (.+)|(?:find|show me|list) everyone (?:whose first name is|named|called) (.+)|"
     r"find (?:my )?contacts? (?:named|called) (.+)", lambda m: C("whatsapp_read", "find", (m[1] or m[2] or m[3]).strip())),
    (r"ask me which .+ if more than one matches|if there are two .+, give me .+|show the full names of the matching contacts|"
     r"(?:do not|don'?t) (?:assume|guess) (?:the first contact|a recipient).*|(?:ask|tell me) which contact i mean.*",
     lambda m: C("behavior", "contacts")),
    (r"open the chat i selected.*|use the other contact with that first name|the (?:second|other|first) (\w+),? not the (?:first|second|other)",
     lambda m: C("task", m[0])),
    (r"read (?:the )?(?:latest|last|newest) message from (?!my |that |this |the same |him\b|her\b|them\b)(.+)", lambda m: C("whatsapp_read", "latest", m[1])),
    (r"(?:tell me )?(?:if|whether) (?:there are|i have) (?:any )?unread whatsapp(?: messages| chats)?|(?:any )?unread whatsapp(?: messages| chats)?|"
     r"(?:do i have|are there) (?:any )?(?:new|unread) (?:whatsapp )?messages(?: on whatsapp)?|summari[sz]e (?:the )?(?:unread|incoming) (?:messages|notifications)(?: .*)?|"
     r"(?:which|what) messengers? (?:has|have) unread messages", lambda m: C("whatsapp_read", "unread")),
    (r"(?:draft|write) a reply to the (?:last|latest|newest) (?:whatsapp |unseen |unread )?message|draft a whatsapp reply(?: .*)?|"
     r"(?:read|answer) (?:an |my )?unread chats?(?:,? draft .*)?|prepare a whatsapp reply.*", lambda m: C("whatsapp_reply", "", "{}")),
    (r"write a whatsapp message (?:asking|saying|telling) .+", lambda m: C("behavior", "need_recipient")),
    (r"send the exact message i dictate .*|send a message to myself as a test", lambda m: C("behavior", "whatsapp_usage")),
    (r"show (?:the )?(?:message )?preview on the (?:dynamic )?island|read the preview to me before i approve|"
     r"ask for approval before sending .*|show me the message before you send it", lambda m: C("behavior", "approvals")),
    (r"change the recipient before sending|send it to (?:him|her|them) instead", lambda m: C("behavior", "change_recipient")),
    (r"search contacts by nickname.*", lambda m: C("behavior", "nickname")),
    (r"(?:tell me )?which (?:whatsapp )?chat is (?:currently )?open", lambda m: C("whatsapp_read", "open_chat")),
    (r"verify the selected chat before typing|(?:do not|don'?t) send anything if (?:the )?focus moves.*", lambda m: C("behavior", "chat_check")),
    (r"check (?:whether|if) the message was delivered", lambda m: C("behavior", "delivery")),
    (r"open (?:that|the) person'?s earlier messages.*", lambda m: C("behavior", "chat_history")),
    (r"(?:explain )?why (?:is )?the whatsapp search (?:isn'?t|is not|not) showing results", lambda m: C("behavior", "whatsapp_search")),
    (r"what was the last (?:message|draft) you prepared(?: for me)?", lambda m: C("jarvis_status", "last_draft")),
    (r"(?:tell me|let me know|alert me) when a (?:whatsapp )?call (?:starts )?ring(?:s|ing)|(?:answer|pick up|decline) (?:the |that )?(?:incoming )?(?:whatsapp )?call (?:if|when) i .+|"
     r"(?:do not|don'?t) (?:accept|answer|pick up) (?:a |any )?calls? automatically|show the incoming call on the island|ask me whether to pick up(?: a| the)? call|"
     r"when whatsapp rings.*", lambda m: C("behavior", "calls")),
    (r"who(?: is|'s) calling(?: me)?(?: on whatsapp)?", lambda m: C("whatsapp_read", "call")),
    (r"end the (?:current )?(?:whatsapp )?call|hang up the (?:current )?call|mute my (?:microphone|mic) (?:during|on) the call.*|"
     r"(?:tell me )?whether the call is still active|is the call still (?:on|active)", lambda m: C("behavior", "call_controls")),
    (r"go back to our conversation after the call", lambda m: C("behavior", "still_here")),
    (r"search telegram for (?:a chat with )?(.+)|draft a telegram message.*|ask before sending a telegram message|send a telegram message.*",
     lambda m: C("behavior", "telegram")),
    (r"find the (?:discord )?server i was looking at|show new messages in the selected channel", lambda m: C("behavior", "discord")),
    (r"write a reply in (?:that|this) channel without sending", lambda m: C("compose_text", "a reply", json.dumps({"target": "", "tail": ""}))),
    (r"switch to the messaging app (?:that'?s|that is) (?:already )?open", lambda m: C("messenger_focus", "")),
    (r"send that draft on whatsapp,? not telegram|(?:no,? )?i meant the person on telegram", lambda m: C("behavior", "messenger_choice")),
    (r"(?:do not|don'?t) read (?:private|personal) (?:chats|messages) (?:out loud|aloud)(?: .*)?", lambda m: C("conversation_style", "private")),
    (r"turn off spoken (?:notifications|alerts)(?: .*)?|(?:mute|silence) (?:spoken )?(?:notifications|alerts)(?: .*)?|quiet mode",
     lambda m: C("conversation_style", "quiet")),
    (r"(?:resume|turn on|unmute) (?:spoken )?(?:message )?(?:notifications|alerts)(?: .*)?", lambda m: C("conversation_style", "unquiet")),
    (r"(?:do not|don'?t) claim a messenger is connected.*|(?:tell me )?what permissions (?:that|the|this) app needs", lambda m: C("behavior", "messenger_permissions")),
    (r"stop (?:monitoring|watching) (?:this|the|whatsapp) ?(?:messenger|app)?(?: for now)?", lambda m: C("conversation_style", "stop_whatsapp_watch")),
    (r"(?:which|what) messaging actions can you (?:actually )?(?:perform|do)|what can you (?:really )?do in (?:these|the) chat apps",
     lambda m: C("behavior", "messaging_actions")),

    # --- YouTube and Spotify ------------------------------------------------------------------------------
    (r"search (youtube|spotify) for (.+)", lambda m: C("media_search", m[2], m[1].casefold())),
    (r"play the official (?:version|video|song) of (.+)", lambda m: C("play_media", m[1] + " official", "")),
    (r"play (.+?) by the (?:correct|right|original) artist", lambda m: C("play_media", m[1], "")),
    (r"play something by (.+)", lambda m: C("play_media", m[1], "spotify")),
    (r"play (?:a|an|the) video (?:explaining|about|on) (.+)", lambda m: C("play_media", m[1] + " explained", "youtube")),
    (r"play the (first|second|third) (?:relevant )?video(?: from the results)?", lambda m: C("select_context",
     {"first": "1", "second": "2", "third": "3"}[m[1].lower()] + ":video", "select")),
    (r"play the video i selected.*|play the album we were looking at", lambda m: C("behavior", "choose_by_number")),
    (r"skip covers and remixes.*|find the original track,? not a cover|(?:do not|don'?t) (?:silently )?(?:choose|pick) a different (?:remix|version)|"
     r"if the original isn'?t there.*|(?:tell me )?if the requested version (?:couldn'?t|could not|can'?t) be found", lambda m: C("behavior", "media_ranking")),
    (r"find (?:a )?live (?:performance|version) of this song", lambda m: C("media_related", "live")),
    (r"find another song by this artist|play another song by this artist", lambda m: C("media_related", "artist")),
    (r"(?:open|play) the (?:most recent|latest|newest) video from (?:that|this) channel|show (?:me )?(?:more )?videos by the (?:creator|channel) we were watching",
     lambda m: C("media_related", "channel")),
    (r"search for a longer explanation of the same topic", lambda m: C("media_related", "longer")),
    (r"(?:switch|move) (?:it |this song |the song )?from youtube to spotify(?: for this song)?|this time do it in spotify|play (?:it|this) on spotify instead",
     lambda m: C("media_related", "spotify")),
    (r"play (?:it|this|that) as a youtube video instead|play (?:it|this) on youtube instead|now open that song on youtube",
     lambda m: C("media_related", "youtube")),
    (r"(pause|resume|mute|unmute) the youtube (?:video|tab)", lambda m: C("media_control", {"resume": "play"}.get(m[1].lower(), m[1].lower()), "youtube")),
    (r"resume the paused video|continue the paused video|unpause the video", lambda m: C("media_control", "play", "youtube")),
    (r"restart (?:this|the) video(?: from the (?:beginning|start))?", lambda m: C("media_control", "restart", "youtube")),
    (r"restart (?:the|this) (?:current )?(?:song|track)|play the last song again", lambda m: C("media_control", "restart", "")),
    (r"skip (?:forward|ahead) (\d{1,3}) seconds?", lambda m: C("spotify_control", "seek_" + m[1])),
    (r"(?:skip|go) back (\d{1,3}) seconds?", lambda m: C("spotify_control", "seek_-" + m[1])),
    (r"(?:set|change) (?:the )?video volume to (\d{1,3})(?: percent|%)?", lambda m: C("media_control", "volume_" + m[1], "youtube")),
    (r"(?:change|set) (?:the )?playback speed to (\d(?:\.\d+)?)x?|play (?:it )?at (\d(?:\.\d+)?)x(?: speed)?",
     lambda m: C("media_control", "speed_" + (m[1] or m[2]), "youtube")),
    (r"(?:switch|go) back to normal (?:playback )?speed|normal playback speed", lambda m: C("media_control", "speed_1", "youtube")),
    (r"put the video (?:in|on|into) full ?screen|(?:make|go) (?:the video )?full ?screen", lambda m: C("media_control", "fullscreen", "youtube")),
    (r"(?:leave|exit|get out of) full ?screen(?: .*)?", lambda m: C("media_control", "exit_fullscreen", "youtube")),
    (r"play the next (?:suggested |recommended )?video", lambda m: C("media_control", "next", "youtube")),
    (r"go back to the previous video|play the previous video", lambda m: C("media_control", "previous", "youtube")),
    (r"(?:what|which) video (?:is playing|are we watching)(?: right now)?|(?:tell me )?the video(?:'s)? title and channel|which video did we just play|"
     r"(?:the )?video is still loading.*|who(?: is|'s) singing (?:this|the) song|(?:what'?s|what is) that (?:spotify )?(?:track|song) called|"
     r"(?:tell me )?how far (?:through|into) the (?:track|song|video) (?:we are|are we)|(?:tell me )?whether the video is paused|is the video paused|"
     r"confirm (?:that )?playback (?:actually )?started|(?:the )?play button didn'?t work.*|that didn'?t start.*|show (?:me )?the current media card|"
     r"show (?:the )?(?:track |album )?(?:artwork|art)(?: on the (?:dynamic )?island)?|show the (?:youtube video'?s|video'?s|track'?s) (?:progress|title)(?: .*)?|"
     r"show the track title(?: .*)?|(?:which|what) player is (?:making sound|playing)(?: right now)?", lambda m: C("spotify_control", "status", "auto")),
    (r"(pause|resume) the spotify (?:track|song|music)", lambda m: C("spotify_control", "pause" if m[1].lower() == "pause" else "play", "spotify")),
    (r"skip to the next (?:track|song)|i said next.*", lambda m: C("spotify_control", "next", "auto")),
    (r"go back to the previous (?:track|song)", lambda m: C("spotify_control", "previous", "auto")),
    (r"seek to the middle of the (?:song|track|video)|(?:skip|go) to (?:the )?(?:middle|halfway)(?: point)?", lambda m: C("media_control", "position_50", "")),
    (r"stop repeating(?: the| this)?(?: track| song)?|repeat off", lambda m: C("spotify_control", "repeat_off", "auto")),
    (r"turn the (?:music|volume|active player'?s volume) (up|down)(?: a (?:little|bit))?|(?:raise|lower) the (?:music|volume)(?! while)",
     lambda m: C("spotify_volume", (m[1] or ("up" if m[0].lower().startswith("raise") else "down")).lower(), "auto")),
    (r"mute (?:only )?the active player", lambda m: C("spotify_volume", "mute", "auto")),
    (r"(?:pause|stop) (?:whatever|what) is playing|pause (?:all|everything)", lambda m: C("spotify_control", "pause", "auto")),
    (r"resume the thing i paused|resume that one(?:,? not the newer one)?|pick up the song from where it stopped|"
     r"play it on whichever player i was using|i just said play.*|keep playing on the service i used last", lambda m: C("spotify_control", "play", "auto")),
    (r"stop youtube when spotify starts(?: playing)?|(?:do not|don'?t) start two players.*", lambda m: C("behavior", "one_player")),
    (r"use youtube for videos and spotify for songs", lambda m: C("behavior", "service_choice")),
    (r"what did i (?:last )?(?:listen to|watch)(?: last)?", lambda m: C("jarvis_status", "media_history")),
    (r"hide the media (?:island|card)(?: .*)?", lambda m: C("behavior", "hide_island")),
    (r"bring the island back when playback changes|show that you'?re searching for the song|put the searching indicator .*",
     lambda m: C("behavior", "media_island")),
    (r"the last command was for (spotify|youtube),? not (?:spotify|youtube)", lambda m: C("media_related", m[1].casefold())),
    (r"keep the media running while you answer.*|lower the music while you'?re speaking", lambda m: C("behavior", "media_while_speaking")),
    (r"retry the safe search .*|(?:do not|don'?t) say you can'?t control playback.*", lambda m: C("behavior", "media_retry")),
    (r"(?:what|which) media commands do you support(?: right now)?|what can you do with (?:music|media|youtube|spotify)",
     lambda m: C("behavior", "media_commands")),

    # --- queue and tasks ---------------------------------------------------------------------------------
    (r"(?:what|which) tasks? (?:is|are) (?:running|active|in progress)(?: right now)?|what'?s waiting in the queue|what have you got lined up(?: next)?|"
     r"(?:tell me )?the progress of the (?:first|current) task|which task is (?:first|second|third|next) in the queue|is that task done(?: yet)?|"
     r"did you finish the thing i asked for|which of the two .+ tasks are you cancelling|report (?:only )?the tasks that are (?:still )?unfinished|"
     r"what happened to the first task|(?:tell me )?which task is still running", lambda m: C("queue_status")),
    (r"(?:add|put) (.+?) (?:to|in|on) the (?:task )?queue|queue (.+?) after the current task|queue (?:up )?(.+)",
     lambda m: queued(m[1] or m[2] or m[3])),
    (r"start the next queued task when this one finishes|do the (?:\w+ )?tasks one after (?:another|the other)|"
     r"(?:do not|don'?t) interrupt the task that'?s (?:already )?running", lambda m: C("behavior", "queue_order")),
    (r"answer (?:this|my) quick question while the task continues|can we keep talking while you work|"
     r"answer my question now and leave the queued tasks alone", lambda m: C("behavior", "parallel")),
    (r"cancel (?:the )?(.+?) task only|cancel only the (.+?) task(?: and continue .*)?", lambda m: C("cancel_task", (m[1] or m[2]).strip())),
    (r"(?:remove|cancel|delete|drop) task (?:number |no\.? |#)?(one|two|three|four|five|\d{1,2})", lambda m: C("cancel_task",
     {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}.get(m[1].lower(), m[1]))),
    (r"scratch (?:the |my )?last request(?: i made)?|forget (?:my |the )?last request", lambda m: C("cancel_task", "last")),
    (r"stop the task you'?re (?:doing|working on)(?: now)?|stop (?:what you'?re|the current) (?:doing|task)", lambda m: C("cancel_current")),
    (r"cancel everything in the queue|clear (?:the|my) queue|cancel all (?:the )?(?:queued )?tasks", lambda m: C("cancel_all")),
    (r"keep the (.+?) task but (?:cancel|drop|stop|remove) the (.+?) task", lambda m: C("cancel_task", m[2])),
    (r"(?:do not|don'?t) cancel the tasks when i say goodbye|go to sleep but keep my queued work running", lambda m: C("behavior", "goodbye_keeps_tasks")),
    (r"reorder the queue.*|put this urgent task ahead.*|change the order of the queue.*|move .+ to the front of the queue",
     lambda m: C("behavior", "queue_reorder")),
    (r"pause the queued task.*", lambda m: C("behavior", "queue_pause")),
    (r"(?:what|which) task failed (?:most recently|last)|(?:explain )?which step caused the failure|(?:explain )?why the last coding attempt failed|"
     r"(?:tell me )?about the last error you recovered from", lambda m: C("jarvis_status", "last_failure")),
    (r"(?:tell me )?which steps of (?:that|the) task (?:already )?completed|show (?:me )?the next step you'?re about to run|"
     r"check (?:whether|if) the last step worked(?: as intended)?|inspect the current task log", lambda m: C("jarvis_status", "task_steps")),
    (r"never ?mind;? leave the current work untouched", lambda m: C("behavior", "nothing_cancelled")),
    (r"i meant cancel the (old|new|first|second|other) (.+?) task,? not the .+", lambda m: C("cancel_task", m[1] + " " + m[2])),
    (r"resume (?:a|the) task that was waiting for my answer|go back to the email thing|can we return to that gmail job", lambda m: C("resume_task")),
    (r"what was the result of the task from earlier|(?:what|which) tasks did you finish(?: earlier)?(?: today)?|"
     r"summari[sz]e what changed and what remains broken|after the workflow finishes.*", lambda m: C("jarvis_status", "recent_tasks")),
    (r"what was the last command i gave you|what did i ask you to do (?:most recently|last)", lambda m: C("jarvis_status", "last_command")),

    # --- planning, tools, recovery: standing instructions ------------------------------------------------------
    (r"plan the task before changing anything|break this complicated job into smaller steps|start executing each step as soon as .*|"
     r"give me an estimated set of steps.*|reuse the same task context.*", lambda m: C("behavior", "planner")),
    (r"use only the tools relevant .*|(?:tell me )?which skill you'?re using.*|why did you choose that tool.*|identify tools and apis required by the plan",
     lambda m: C("behavior", "tools")),
    (r"the click failed;? replan .*|if the first (?:search|attempt|try) fails.*|(?:do not|don'?t) restart the whole task.*|try an alternative safe method.*", lambda m: C("behavior", "replan")),
    (r"stop and ask if you can'?t confirm .*|(?:do not|don'?t) resend an email.*|report the exact blocker.*|(?:do not|don'?t) repeat (?:a|an) (?:side effect|irreversible operation).*|"
     r"stop a risky step.*|preserve the original data.*", lambda m: C("behavior", "no_replay")),
    (r"use your cpu and gpu efficiently.*|(?:tell me )?why the planner is taking so long|prefer the fast direct command path.*|"
     r"keep the language model warm.*|why is my first answer slower than the next one", lambda m: C("behavior", "performance")),
    (r"use the screen only when .*|(?:do not|don'?t) send screenshots to the planner.*", lambda m: C("behavior", "vision")),
    (r"use a free service when an api is optional|(?:do not|don'?t) use a paid api.*|warn me if a requested function needs a paid key|"
     r"use the safe fallback rather than guessing|use an alternate research api if the first fails", lambda m: C("behavior", "free_apis")),
    (r"check the final result in the app,? not just in logs|run the relevant tests before you report success|"
     r"(?:do not|don'?t) claim the tests passed.*|only tell me it passed after checking the tests|stop after a verified successful result",
     lambda m: C("behavior", "verification")),
    (r"(?:which|what) part of this request is unsupported(?: today)?|say plainly when a capability isn'?t implemented|"
     r"(?:what|which) parts of jarvis are not working(?: yet)?|(?:tell me )?what you cannot verify(?: right now)?", lambda m: C("behavior", "limits")),

    # --- memory ------------------------------------------------------------------------------------------------
    (r"(?:what|which) preferences have you saved(?: about me)?|what did you learn from the last session|(?:tell me )?whether you saved that detail|"
     r"show a short summary rather than the entire vault|(?:tell me )?when that saved preference was last updated", lambda m: C("memory_list", "")),
    (r"what did we (?:discuss|talk about) (yesterday|today|last week|earlier)", lambda m: C("memory_conversations", m[0])),
    (r"find the conversation where we (.+)", lambda m: C("memory_conversations", m[1])),
    (r"remind me what i told you about (.+)", lambda m: C("memory_list", m[1])),
    (r"forget the (?:preference|fact|thing) i just (?:mentioned|told you|said)", lambda m: C("memory_forget", "last")),
    (r"forget (?:only )?the (?:fact|preference) about (.+)", lambda m: C("memory_forget", m[1])),
    (r"summari[sz]e our conversation into my obsidian vault|save (?:our|this) (?:discussion|conversation) (?:as a (?:conversation )?note|to (?:my )?(?:memory|obsidian))(?: .*)?",
     lambda m: C("memory_summarize", "")),
    (r"show the latest jarvis conversations note", lambda m: C("memory_conversations", "latest")),
    (r"convert that relative date into a real date.*", lambda m: C("behavior", "dates")),
    (r"(?:do not|don'?t) store (?:my )?passwords?(?: .*)?|(?:do not|don'?t) store my (?:password|one-time code|otp).*", lambda m: C("behavior", "secrets")),
    (r"where did you store the memory of this repo|where are the repo notes stored(?: in obsidian)?|open the relevant memory note|"
     r"remember what you learned about this repository", lambda m: C("behavior", "memory_storage")),
    (r"use what you remember when answering.*|(?:do not|don'?t) invent a memory.*|distinguish a saved fact from an assumption|"
     r"which memory helped you choose that response|(?:do not|don'?t) confuse a fictional example.*|(?:tell me )?whether a result came from memory or a live api",
     lambda m: C("behavior", "memory_grounding")),
    (r"update the old preference with this new one|keep the project preference separate.*", lambda m: C("behavior", "memory_update")),
    (r"keep this detail only for the current conversation|(?:do not|don'?t) remember (?:this|that)(?: .*)?|off the record", lambda m: C("conversation_style", "no_memory")),
    (r"(?:what|which) tools and apis do you (?:know you )?have|(?:list|show) the skills you have installed|(?:which|what) apis are connected to jarvis|"
     r"(?:which|what) tools can you execute without a model call", lambda m: C("jarvis_status", "capabilities")),

    # --- context references ---------------------------------------------------------------------------------
    (r"(?:what is|what'?s) the name of the current project", lambda m: C("project_recent")),
    (r"use this window as the target|(?:do not|don'?t) mix up the two projects|ask me if you can'?t confidently resolve .*",
     lambda m: C("behavior", "references")),
    (r"what did you learn while i was browsing|which repos have you (?:already )?(?:studied|learned)|is this repository in your learned index|"
     r"what did you learn from the repo i browsed .+|show a learning status on the dynamic island", lambda m: C("repo_list", "")),

    # --- repositories ----------------------------------------------------------------------------------------------
    (r"learn the (?:github )?repo(?:sitory)? in my current tab|learn (?:this|the current) (?:github )?(?:repo|repository|project)(?: quietly.*)?",
     lambda m: C("repo_learn", "")),
    (r"(?:what is|what'?s) (?:this|the) (?:repo|repository|github project) (?:for|doing)|what'?s the point of this repo", lambda m: C("repo_explain", "")),
    (r"find (?:github )?(?:projects|repos|repositories) (?:relevant to|for|about) (.+)", lambda m: C("toolkit", "github_search", json.dumps({"value": m[1]}))),
    (r"explore the file structure of this repo(?:sitory)?", lambda m: C("repo_explain", "", "structure")),
    (r"find where the main application starts|(?:what|where) is the entry point", lambda m: C("repo_explain", "", "entry")),
    (r"explain the important modules in this codebase|show how the functions call each other", lambda m: C("repo_explain", "", "modules")),
    (r"identify the dependencies this project needs|(?:what are|list) (?:the )?dependencies(?: of this repo)?", lambda m: C("repo_explain", "", "dependencies")),
    (r"read the repo(?:sitory)? readme and setup instructions|explain the build process used here|how do i (?:run|build|install) this repo",
     lambda m: C("repo_explain", "", "setup")),
    (r"find the test suite in this repo", lambda m: C("repo_explain", "", "tests")),
    (r"what license does this repo(?:sitory)? use|explain the license before reusing repository code", lambda m: C("repo_explain", "", "license")),
    (r"show which coding task used this repo(?:sitory)? as a reference", lambda m: C("repo_explain", "", "used_for")),
    (r"(?:do not|don'?t) copy code from a project.*|identify reusable ideas,? not copyrighted code.*", lambda m: C("behavior", "license")),
    (r"search for an example repo before writing code|find an open-source example before implementing.*|use the repo knowledge you saved.*|"
     r"use your cached notes before downloading it again|explain which repo ideas influenced the design", lambda m: C("behavior", "repo_reuse")),
    (r"refresh the repo knowledge.*|update the repo knowledge.*", lambda m: C("repo_learn", "")),
    (r"forget what you learned about (?:that|this) repo", lambda m: C("behavior", "repo_forget_usage")),
    (r"stop learning the repo in the background|stop the background github analysis(?: for now)?", lambda m: C("behavior", "repo_stop")),
    (r"(?:tell me )?when background learning finishes|keep repository learning low priority.*|learn quietly in the background.*|"
     r"(?:do not|don'?t) exhaust the free github api quota|(?:tell me )?if the repo is private or inaccessible",
     lambda m: C("behavior", "repo_background")),
    (r"how many github requests are left(?: if known)?", lambda m: C("jarvis_status", "github_quota")),

    # --- coding --------------------------------------------------------------------------------------------------
    (r"keep the change local;? (?:do not|don'?t) commit(?: it)?|commit only the files i name", lambda m: C("behavior", "commits")),
    (r"use separate worktrees for independent agents|(?:do not|don'?t) have two agents edit the same file.*|have a merge agent review the changes",
     lambda m: C("behavior", "agents")),
    (r"(?:show )?(?:me )?which files you intend to change|show the git diff of your edits|(?:run|execute) (?:the )?(?:relevant|entire|integration) tests?(?: suite)?.*|"
     r"fix the import error .*|inspect the traceback .*|reproduce the failing behavio(?:u)?r.*|compare the result to the requested behavio(?:u)?r|"
     r"create a backup before overwriting the source|(?:add|put) a function without breaking .*|create a pull request draft.*|check for merge conflicts.*|"
     r"check (?:whether|if) the application still starts|(?:tell me )?which tests were skipped|(?:tell me )?what still doesn'?t work in the generated project",
     lambda m: C("task", m[0])),

    # --- diagnostics -------------------------------------------------------------------------------------------
    (r"(?:which|what) (?:local )?model is answering me(?: right now)?|(?:which|what) model does the planner use|(?:which|what) model powers your voice|"
     r"(?:tell me )?if a model is running on (?:the )?cpu or gpu|show the model cache status(?: if available)?", lambda m: C("jarvis_status", "models")),
    (r"check (?:whether|if) all (?:configured |connected )?apis respond|check all connected apis(?: .*)?", lambda m: C("api_health", "")),
    (r"(?:which|what) public endpoints are failing(?: right now)?|(?:tell me )?which api fallback was used|(?:tell me )?if the live flight endpoint is unavailable",
     lambda m: C("api_health", "failing")),
    (r"do you have a youtube api key(?: configured)?|is (?:the )?youtube api (?:key )?(?:set|configured)", lambda m: C("jarvis_status", "youtube_key")),
    (r"check (?:whether|if) the god'?s eye server is running|is god'?s eye running", lambda m: C("gods_eye_status", "")),
    (r"(?:tell me )?whether the weather watcher is active|is the weather watcher (?:on|running|active)", lambda m: C("jarvis_status", "weather_watch")),
    (r"show the last startup readiness result|(?:run|show) the launcher health check", lambda m: C("jarvis_status", "readiness")),
    (r"(?:tell me )?why (?:the )?speech is stuttering|why is your voice (?:stuttering|choppy|breaking up)", lambda m: C("behavior", "stutter")),
    (r"(?:which|what) process(?:es)? (?:is|are) (?:monopoli[sz]ing|using) the gpu|show (?:me )?the windows processes using (?:the )?gpu",
     lambda m: C("system_info", "gpu_processes")),
    (r"while the song plays,? show me the windows processes using (?:the )?gpu", lambda m: C("system_info", "gpu_processes")),
    (r"show the active speech recognition backend|(?:which|what) speech recognition (?:backend|model) (?:is active|are you using)",
     lambda m: C("jarvis_status", "speech")),
    (r"(?:can you )?answer this without using the web|(?:can you )?do this entirely offline|(?:which|what) capabilities require cloud credentials|"
     r"(?:which|what) features require extra local hardware", lambda m: C("behavior", "offline")),
    (r"show the configuration setting for the island ui", lambda m: C("jarvis_status", "island_config")),
    (r"(?:tell me )?what changed since the last update", lambda m: C("jarvis_status", "changes")),

    # --- God's Eye: places and camera ------------------------------------------------------------------------------
    (r"(?:fly|center|centre|focus) (?:the globe|the camera|god'?s eye|the view) (?:to|on|over) (.+)", lambda m: gev(place=m[1], layers=[], kind="place")),
    (r"show (?:me )?(.+?) from (?:the air|above|space)", lambda m: gev(place="me" if m[1].lower() in {"me", "my area"} else m[1], layers=[], kind="place")),
    (r"take me to (.+?) and zoom in", lambda m: gev(place=m[1], layers=[], kind="place", zoom="in")),
    (r"fly out to see the whole (.+)", lambda m: gev(place=m[1], layers=[], kind="place")),
    (r"(?:no,? )?i said (?:the )?(.+?),? not the (?:restaurant|business|shop|hotel)|i meant the actual (?:gulf|place|city),? not a business.*",
     lambda m: gev(place=m[1] if m.lastindex and m[1] else "persian gulf", layers=[], kind="place")),
    (r"(?:show )?a close-?up of this (?:landmark|place|area)|zoom (?:all the way )?in(?: a lot| closer| more)?", lambda m: cam(zoom="in", amount="lot")),
    (r"zoom (?:in )?a (?:little|bit)", lambda m: cam(zoom="in", amount="little")),
    (r"zoom out until the whole (?:city|area|region|country) is visible(?: a bit)?|zoom out(?: a lot| more)?|(?:use )?a wider (?:regional )?view(?: .*)?|"
     r"show a wider view of the storm", lambda m: cam(zoom="out", amount="lot")),
    (r"show the same place from a higher altitude|zoom out a (?:little|bit)|show the coastline around this point", lambda m: cam(zoom="out", amount="medium")),
    (r"rotate the camera around (?:this|the) (?:area|place)|orbit (?:around )?(?:this|the) (?:area|place)", lambda m: cam(move="orbit")),
    (r"tilt the camera to a more overhead view|frame this area directly from above|look straight down", lambda m: cam(overhead=True)),
    (r"return to the previous camera position|go back to the previous (?:view|camera position|place)", lambda m: cam(back=True)),
    (r"move the view (?:a (?:little|bit) )?(north|south)|pan (north|south)(?: .*)?", lambda m: cam(move="pan", direction="up" if (m[1] or m[2]).lower() == "north" else "down")),
    (r"move the view (?:a (?:little|bit) )?(east|west)|pan (east|west)(?: .*)?|move (east|west) without changing the zoom",
     lambda m: cam(move="pan", direction="right" if (m[1] or m[2] or m[3]).lower() == "east" else "left")),
    (r"label the place you'?re showing me|(?:annotate|label) this map location(?: with a label)?|(?:drop|add) a pin here", lambda m: cam(label=True)),
    (r"remove the annotation you just added|clear the annotations", lambda m: cam(clear=True)),
    (r"what location is god'?s eye (?:currently )?centered on|where is god'?s eye (?:looking|pointing)", lambda m: cam(where=True)),
    (r"fly the camera along the route you drew|fly along the route", lambda m: cam(fly_route=True)),
    (r"go to my approximate current location|put the globe over where i am(?:,? roughly)?|show me where i am", lambda m: gev(place="me", layers=[], kind="place")),
    (r"keep this location but change the visual style", lambda m: C("behavior", "styles")),
    (r"find the correct place,? not a similarly named business", lambda m: C("behavior", "geocoding")),
    (r"switch from the normal map to satellite imagery|use satellite imagery", lambda m: C("behavior", "imagery")),
    (r"refresh god'?s eye to the latest installed version|update god'?s eye(?: .*)?", lambda m: C("gods_eye_update", "")),
    (r"what version of god'?s eye is installed", lambda m: C("jarvis_status", "gods_eye_version")),
    (r"keep the old god'?s eye source as a backup .*", lambda m: C("behavior", "gods_eye_backup")),
    (r"change the location to (.+)", lambda m: gev(place=m[1], layers=[], kind="place")),

    # --- God's Eye: aircraft, layers, hazards -----------------------------------------------------------------------
    (r"what plane is flying overhead(?: right now)?|what aircraft (?:that is|is that|is) above us|is there a helicopter (?:nearby|overhead)|"
     r"(?:tell me )?the nearest aircraft'?s callsign(?: if available)?|how far away is that (?:aircraft|plane)|what'?s its reported altitude|"
     r"which direction is that plane moving|are there any aircraft with an emergency squawk|what made that loud noise outside|"
     r"could those sirens be related to something nearby|is (?:there )?any unusual aircraft activity (?:reported )?around me|"
     r"summari[sz]e the last local aircraft update|is there a reported wildfire near (?:this location|me)|check for nearby earthquakes|"
     r"what(?: is|'s) happening around (?:my location|me)(?: right now)?|did the background watcher spot anything unusual|"
     r"use local flight information to answer why it'?s noisy outside", lambda m: C("gods_eye_explain", m[0])),
    (r"show (?:me )?the nearest aircraft(?: to my area| to me)?", lambda m: gev(place="me", layers=["flights"], kind="flights", nearest="flights")),
    (r"show (?:both )?military planes and (?:mapped )?bases|show the military layer but keep the camera where it is",
     lambda m: gev(place="", layers=["military", "military-installations"], kind="military")),
    (r"hide (?:the )?(civilian aircraft|flights|planes|radar|rain radar|cameras|cctv|military(?: flights| aircraft)?|military bases|lightning|ships)(?: for now)?(?: but (?:leave|keep) (lightning|the radar|radar) visible)?|"
     r"hide the radar but leave lightning visible|keep the military layer but remove the cameras",
     lambda m: cam(hide=[_layer(m[1]) if m[1] else ("weather-radar" if "radar" in m[0].lower() else "cctv")])),
    (r"turn on (?:the |my )?(military installations|local ads-?b receiver|rain radar|lightning|cyclone|satellite|ship|transit) layer",
     lambda m: gev(place="", layers=[_layer(m[1])], kind=_layer(m[1]))),
    (r"show (?:all )?(?:the )?(?:airports and heliports|airports|heliports)(?: .*)?", lambda m: C("behavior", "airports")),
    (r"(?:tell me )?whether the live flight feed is fresh|how current are those flight positions|tell me when the last god'?s eye poll succeeded|"
     r"what radius are you monitoring(?: around me)?|check (?:whether|if) the alert is inside that radius|check (?:whether|if) an rtl-sdr is configured|"
     r"(?:tell me )?if a local receiver has not been installed|why is the local radio-receiver layer empty",
     lambda m: C("gods_eye_status", "")),
    (r"alert me if a 7700 emergency appears nearby|flag any 7500 aircraft alert carefully|what does squawk (7500|7600|7700) mean",
     lambda m: C("behavior", "squawks")),
    (r"(?:do not|don'?t) identify a flight if the feed is uncertain|show me aircraft positions,? not predicted identities|"
     r"(?:do not|don'?t) turn stale flight data into a real-time claim", lambda m: C("behavior", "flight_honesty")),
    (r"show me aircraft around the last place we viewed", lambda m: gev(place="", layers=["flights"], kind="flights")),
    (r"show the latest weather near (.+)", lambda m: gev(place=m[1], layers=["weather-radar", "weather-lightning"], kind="weather-radar", lock=True)),
    (r"show the cyclone tracks(?: god'?s eye has)?|show (?:all )?cyclones(?: near (.+))?", lambda m: gev(place=m[1] or "", layers=["weather-cyclones", "weather-satellite"],
     kind="weather-cyclones", coverage_note=True)),
    (r"(?:which|what) regions does the cyclone feed cover|explain the gaps in indian ocean cyclone coverage|"
     r"(?:do not|don'?t) say there'?s no storm when the source lacks coverage|if the feed doesn'?t cover here.*", lambda m: C("behavior", "cyclone_coverage")),
    (r"plot recent earthquakes around (.+)|show (?:recent )?earthquakes (?:around|near|in) (.+)", lambda m: gev(place=m[1] or m[2], layers=["earthquakes"], kind="earthquakes")),
    (r"show (?:the )?active fire layer near me|show (?:active )?fires near me", lambda m: gev(place="me", layers=["local-firms", "fire-perimeters"], kind="local-firms")),
    (r"(?:tell me )?whether the fire data requires a key|check for new nasa wildfire reports", lambda m: C("behavior", "fire_data")),
    (r"show wildfire perimeters in (.+)", lambda m: gev(place=m[1], layers=["fire-perimeters"], kind="fire-perimeters")),
    (r"show only hazard layers(?: on the globe)?", lambda m: gev(place="", layers=HAZARDS, kind="hazards")),
    (r"hide every layer you turned on for the last request|turn off every layer you turned on.*", lambda m: cam(hide=["*"])),
    (r"keep the layers i switched on manually", lambda m: C("behavior", "manual_layers")),
    (r"show the location associated with the alert", lambda m: C("jarvis_status", "weather_watch")),
    (r"open the nearest (?:available )?cctv(?: camera)?(?: feed)?|show the camera'?s viewing direction(?: on the map)?", lambda m: gev(place="", layers=["cctv"], kind="cctv", cctv=True)),
    (r"find cameras near (.+)|show (?:all )?(?:available )?camera locations around (.+)", lambda m: gev(
        place="" if re.fullmatch(r"this (?:city|area|place)", (m[1] or m[2]), FLAGS) else (m[1] or m[2]), layers=["cctv"], kind="cctv", cctv=True)),
    (r"(?:tell me )?when a camera feed is unavailable|(?:do not|don'?t) promise access to a camera .*|(?:do not|don'?t) mistake a map layer for a live video feed|"
     r"is this a live camera view", lambda m: C("behavior", "cameras")),
    (r"turn on mapped license plate reader locations.*", lambda m: gev(place="", layers=["alpr-cameras"], kind="alpr-cameras")),
    (r"show the mapped data cent(?:er|re)s near the city|find large dams in this region|show ports and ships near the coast|"
     r"show satellite tracks over this region|show public transit routes.*|show recent imagery for this area",
     lambda m: gev(place="", layers=[_layer(m[0])], kind=_layer(m[0]))),
    (r"plot major undersea cables in the (.+)", lambda m: gev(place=m[1], layers=["telegeography-submarine-cables"], kind="cables")),
    (r"show recent rocket launches", lambda m: gev(place="", layers=["rocket-launches"], kind="rocket-launches")),
    (r"show road traffic in (.+?) if a key is configured", lambda m: gev(place=m[1], layers=["traffic"], kind="traffic", lock=True)),
    (r"(?:tell me )?why the live traffic overlay is unavailable", lambda m: C("behavior", "traffic")),
    (r"draw (?:a )?(?:driving )?route from (.+?) to (.+?)(?: and fly along it)?", lambda m: gev(place="", route=[m[1].strip(), m[2].strip()])),
    (r"(?:switch|change) (?:god'?s eye )?to (?:the )?(thermal|noir|retro|anime|snow|normal|night[- ]vision)(?: visual)?(?: style| view| look)?(?: and keep the current location)?|"
     r"(?:apply|use) the (night[- ]vision|thermal|noir|retro) look|go back to the normal visual style",
     lambda m: gev(place="", style=_style(m[1] or m[2] or "normal"))),
    (r"use the cyber radar interface|(?:switch|change) to the (tactical|cyber|operator|minimal) hud", lambda m: gev(place="", style=["hud", (m[1] or "cyber").lower()])),
    (r"(?:explain )?which advanced god'?s eye controls aren'?t voice-integrated", lambda m: C("behavior", "gods_eye_limits")),
    (r"open the eiffel tower in god'?s eye and show cameras nearby", lambda m: gev(place="eiffel tower", layers=["cctv"], kind="cctv", cctv=True)),
    (r"show military activity over the (.+?)(?: and summari[sz]e .*)?", lambda m: gev(place=m[1], layers=["military", "military-installations"], kind="military")),
    (r"show flights overhead and tell me what data source they come from", lambda m: gev(place="me", layers=["flights", "local-adsb"], kind="flights", sources=True)),
    (r"check the weather and open the relevant area in god'?s eye", lambda m: gev(place="me", layers=["weather-radar", "weather-lightning"], kind="weather-radar", lock=True)),
    (r"find the latest earthquake feed and plot the relevant region", lambda m: gev(place="", layers=["earthquakes"], kind="earthquakes")),

    # --- weather watcher and public data -------------------------------------------------------------------------
    (r"will bad weather hit my area.*|what severe weather is expected.*|(?:tell me )?if there'?s heavy rain coming|check for thunderstorms(?: and hail)?|"
     r"(?:tell me )?about nearby flood alerts|find earthquake alerts near my city|show public disaster reports from gdacs|refresh the alert feed(?: now)?|"
     r"show the last storm alert in my area", lambda m: C("weather_alerts", "check")),
    (r"warn me when the forecast becomes more dangerous|warn me if strong winds are forecast|(?:do not|don'?t) repeat the same weather warning.*|"
     r"(?:do not|don'?t) announce the same storm twice.*", lambda m: C("behavior", "weather_watch")),
    (r"(?:tell me )?what triggered that warning|why did the weather alert appear on my island|is the last alert still active|"
     r"(?:tell me )?the forecast source used for this warning|what was the last successful weather update|how old is that weather observation|"
     r"compare current conditions with the earlier update", lambda m: C("jarvis_status", "weather_watch")),
    (r"is that an official government warning", lambda m: C("behavior", "official_warning")),
    (r"check the current temperature where i am", lambda m: C("ask", "current temperature")),
    (r"check the time using an available free time api", lambda m: C("ask", "current time")),
    (r"use cached data only if you label it as cached|show live information without opening a dozen tabs|verify that this answer is still current|"
     r"which free api answered that question", lambda m: C("behavior", "live_data")),

    # --- context and follow-ups (answers keep the ask/task kinds a waiting prompt accepts) ---------------------
    (r"make (?:the|that|this|my) (?:reply|draft|message|email|body|text|note) (?:a (?:bit|little) )?(?:warmer|shorter|longer|friendlier|"
     r"kinder|more \w+|less \w+)(?: .*)?", lambda m: C("task", m[0])),
    (r"(?:i (?:opened|have) youtube(?: open(?:ed)?)?(?: first)?|youtube is open);? (?:now )?play (.+)", lambda m: C("play_media", m[1], "youtube")),
    (r"(?:now )?do (?:it|the same(?: thing)?) (?:for|with) (?:the )?(?:result number|number|result) (\w+)|do the same thing with the (\w+) result",
     lambda m: C("ask", m[0])),
    (r"expand (?:on )?the last point(?: you made)?|(?:tell me )?more about (?:that|the last point)", lambda m: C("ask", m[0])),
    (r"use the same (?:contact|person|chat) as before", lambda m: C("task", m[0])),
    (r"compare this repo(?:sitory)? (?:to|with) the one we saw before", lambda m: C("ask", m[0])),
    (r"find current information using an accessible news source|(?:what'?s|what is) (?:the )?(?:latest|today'?s) news", lambda m: C("ask", "latest news headlines")),
    (r"read the warning on the screen(?: before proceeding)?|what does (?:this|the) (?:warning|error|message on screen) say", lambda m: C("ask", m[0])),
    (r"right-?click (?:this|the) .+|hover over the .+", lambda m: C("task", m[0])),
    (r"find a coding example,? build .+|find the right \w+,? draft the message .+", lambda m: C("task", m[0])),

    # --- permissions and safety ----------------------------------------------------------------------------------
    (r"ask me to confirm before deleting an email|(?:do not|don'?t) send anything when i say only draft|never use an approval from an earlier message|"
     r"(?:do not|don'?t) read personal messages aloud.*", lambda m: C("behavior", "approvals")),
    (r"never put api keys in a public repo(?:sitory)?|(?:explain )?what permission this api needs|use the least privileged tool.*|"
     r"(?:do not|don'?t) expose personal coordinates.*", lambda m: C("behavior", "privacy")),
    (r"(?:do not|don'?t) claim an action succeeded without verification|show me the last known state when the app disconnects",
     lambda m: C("behavior", "verification")),
    # Last: anything about email goes to the Gmail workflow (it reads, searches, drafts and asks before any write).
    (r".+", lambda m: _mail(m[0])),
]

MAIL = re.compile(r"\b(?:e-?mails?|gmail|inbox|mailbox|threads?|drafts?|recipients?|cc|bcc|labels?|attachments?|senders?|"
                  r"trash|unarchive|archive|subject)\b", re.I)
MAIL_MESSAGE = re.compile(r"\b(?:unread|newest|latest|first|second|third|recent|older) (?:\w+ )?messages?\b|"
                          r"\bmessages? (?:from (?:my|the same)|older than|into trash)\b|\bmessage (?:to|into) \w+$|"
                          r"\b(?:the|an?) (?:message|mail) (?:about|regarding|with the subject)\b|\bquoted reply\b|\breply history\b|\blatest reply\b|"
                          r"\b(?:restore|unarchive|archive|star|unstar|forward) (?:the|this|that) (?:\w+ )?message\b", re.I)
NOT_MAIL = re.compile(r"\b(?:whatsapp|telegram|discord|chats?|channel|spotify|youtube|tasks?|queue|repo(?:sitory)?|obsidian|"
                      r"god'?s eye|island)\b|^(?:what were we|find the conversation|explain why|why )", re.I)


def _mail(text):
    if re.match(r"(?:cancel|stop|drop|discontinue|scrap|abort|skip|forget|never ?mind|don'?t|do not|no need)\b", text, re.I):
        return None  # "don't do the email anymore" cancels a task.
    if (MAIL.search(text) or MAIL_MESSAGE.search(text)) and not NOT_MAIL.search(text):
        from .conversation_intent import normalize
        return C("task", normalize(text))  # "let's make an email" -> "make an email".
    return None


def _write(text):
    from .writing import parse_write
    return parse_write(text) or C("task", text)


LAYER_HINTS = [("civilian", "flights"), ("flight", "flights"), ("plane", "flights"), ("military installation", "military-installations"),
               ("military base", "military-installations"), ("military", "military"), ("ads-b", "local-adsb"), ("adsb", "local-adsb"),
               ("rain radar", "weather-radar"), ("radar", "weather-radar"), ("lightning", "weather-lightning"), ("cyclone", "weather-cyclones"),
               ("camera", "cctv"), ("cctv", "cctv"), ("data cent", "local-datacenters"), ("dam", "local-dams"), ("ship", "ais-live-vessels"),
               ("port", "ais-live-vessels"), ("satellite track", "satellites"), ("satellite", "satellites"), ("transit", "transit"),
               ("imagery", "recent-imagery")]


def _layer(words):
    low = words.casefold()
    return next((layer for hint, layer in LAYER_HINTS if hint in low), "flights")


def _style(word):
    from .gods_eye import STYLES
    word = word.casefold().replace("-", " ")
    return list(STYLES.get(word, ("style", "normal")))


COMPILED = tuple((re.compile(pattern, FLAGS), builder) for pattern, builder in RULES)
import hashlib
BUILTIN_PATTERN_SHA256 = hashlib.sha256('\n'.join(pattern.pattern for pattern,_ in COMPILED).encode('utf-8')).hexdigest()


def match(text):
    """The catalog command for canonical text, or None."""
    clean = re.sub(r"\s+", " ", text.strip().rstrip(".!?").strip())
    clean = re.sub(r"^(?:no|okay|ok|actually|hey)\s*[,;:]\s*", "", clean, flags=FLAGS) if not clean.lower().startswith("no, i") else clean
    for pattern, builder in COMPILED:
        found = pattern.fullmatch(clean)
        if found:
            command = builder(found)
            if command is not None:
                return command
    return None
