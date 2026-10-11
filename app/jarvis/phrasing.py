"""Reduce the many ways a request is phrased to one canonical form the command rules know.

"Could you pull up my desktop?", "Quick question: what's playing?", "I need you to give me the gist of the
three newest unread emails" and "Have a look at for earthquake alerts" become "show me my desktop",
"what's playing", "summarize the three newest unread emails" and "find earthquake alerts". Only the head of
the sentence is rewritten (wrappers, politeness, a synonym of the leading verb, spoken numbers), so dictated
text after "write exactly" or "send ... saying" keeps its words and capitalisation.
"""
import re

# Lead-ins that carry no instruction. Repeated: "Hey Jarvis, quick question: could you ...".
WRAPPERS = [
    r"(?:hey |hi |ok |okay )?jarvis\b[,!]?",
    r"(?:hey|hi|okay|ok|so|um|uh|well|alright|all right|oh)\b[,!]?(?= )",
    r"quick question\s*[:,-]?", r"(?:tell me )?one (?:more )?thing\s*[:,-]", r"just checking\s*[-:,]?",
    r"by the way\s*[,:-]?", r"for now\s*[,:-]", r"just to clarify\s*[,:-]?", r"i mean\s*[,:-]",
    r"when you(?:'re| are) ready\s*[,:-]?", r"if you can\s*[,:-]", r"real quick\s*[,:-]?",
    r"remember\s*[,:-](?= *(?:before|after|earlier|when|if)\b)", r"actually\s*[,:-]?", r"also\s*[,:-]?",
    r"please\b[,]?", r"kindly\b", r"(?:could|can|would|will) you (?:please )?(?:just )?(?:be able to )?",
    r"would you be able to", r"would you mind", r"do you mind", r"(?:can|could) you help me(?: to)?",
    r"i(?:'d| would) like you to", r"i (?:want|need) you to", r"i(?:'d| would) like to", r"go ahead and",
    r"make sure (?:that )?you", r"be sure to", r"(?:please )?remember to", r"try to", r"i want to",
    r"do you know(?= (?:what|which|who|where|when|how|if|whether)\b)", r"any idea(?= (?:what|which|who|where|when|how|if|whether)\b)",
    r"(?:could|can) you tell me(?= (?:what|which|who|where|how|whether)\b)",
    r"(?:please )?tell me(?= (?:which|what|who|where|how|whether)\b)", r"not quite\s*[-:,]?", r"no wait\s*[,:-]?",
    r"now,? (?=(?:do|play|show|open|search|find)\b)",
]
WRAPPER = re.compile(r"^(?:" + "|".join(WRAPPERS) + r")\s*", re.I)

# Leading-verb synonyms -> the verb the command rules use. Applied once, to the head only.
VERBS = [
    (r"under no circumstances\b", "never"), (r"could we\b", "can we"), (r"pull up me\b", "show me"),
    (r"press (?=(?:the |this |that )?.*\b(?:button|checkbox|check box|icon|link|option|tab|toggle)\b)", "click "),
    (r"press only once\b", "click only once"), (r"choose all\b", "select all"),
    (r"type (?:these|the|this) exact (?:words|text|sentence)\s*:?", "write exactly:"),
    (r"draft (?=.+ (?:in|into) (?:this app|here|this window|the current window|notepad|word|this document)\b)", "write "),
    (r"add more detail to\b", "expand"), (r"turn down (?=the (?:music|volume))", "lower "), (r"turn up (?=the (?:music|volume))", "raise "),
    (r"continue (?!the conversation|where|with)(?=(?:the|a|that|this|message|my|playing)\b)", "resume "),
    (r"update (?=the alert feed)", "refresh "), (r"keep (?=our (?:discussion|conversation))", "save "), (r"pull up\b", "show"), (r"bring up\b", "open"), (r"put up\b", "show"),
    (r"pull (.+?) back\b", r"bring \1 back"), (r"display\b", "show"),
    (r"have a look at up\b", "look up"), (r"have a look at for\b", "find"), (r"have a look (?:at|for)\b", "find"),
    (r"look for\b", "find"), (r"look up for\b", "search for"),
    (r"look up (my (?:inbox|sent folder|emails?|mail|gmail|drafts)|youtube|spotify|telegram|whatsapp|discord|"
     r"contacts?|github|the (?:web|internet))\b", r"search \1"),
    (r"take a look at (?=for|whether|if|that|how)\b", "check "), (r"take a look at\b", "check"),
    (r"check with me\b", "ask me"), (r"check with (?=for|before|which|whether)\b", "ask "),
    (r"let me know me\b", "alert me"), (r"let me know\b", "tell me"),
    (r"give me a heads[- ]up(?: me)?\b", "warn me"), (r"keep me posted (?:on|about)\b", "tell me about"),
    (r"give me the gist of\b", "summarize"), (r"give me a summary of\b", "summarize"), (r"sum up\b", "summarize"),
    (r"walk me through\b", "explain"), (r"run me through\b", "explain"), (r"help me understand\b", "explain"),
    (r"go through back\b", "read back"), (r"go through\b", "read"), (r"read out\b", "read"),
    (r"put together\b", "write"), (r"prepare\b", "draft"), (r"whip up\b", "write"),
    (r"put on\b", "play"), (r"place on\b", "play"), (r"throw on\b", "play"), (r"place\b", "put"),
    (r"hold on,? (?:stop|pause) (?:that|the|this)? ?(?:playback|video|song|music)\b", "pause it"),
    (r"hold (?=(?:the|whatever|this|that|my|it)\b)(?!the (?:door|key|shortcut|button))", "pause "),
    (r"silence\b", "mute"), (r"drop\b", "cancel"), (r"discontinue\b", "stop"), (r"scrap\b", "cancel"),
    (r"quit (?=the background|background)", "stop "), (r"head back\b", "go back"),
    (r"start over (?=(?:this|the|that|it)\b)", "restart "), (r"start over\b", "restart"),
    (r"jump\b", "skip"), (r"shift (?=(?:this|that|the|my|your|east|west|north|south)\b)", "move "),
    (r"adjust\b", "change"), (r"switch (.+?) (on|off|up|down)\b", r"turn \1 \2"),
    (r"change back to\b", "switch back to"), (r"change to\b", "switch to"), (r"change from\b", "switch from"),
    (r"execute\b", "run"), (r"examine\b", "inspect"), (r"pinpoint\b", "identify"), (r"contrast\b", "compare"),
    (r"repair\b", "fix"), (r"take away\b", "remove"), (r"keep in mind\b", "remember"), (r"note that\b", "remember that"),
    (r"stop remembering\b", "forget"), (r"favou?rite\b", "star"), (r"flag (.+?) as\b", r"mark \1 as"),
    (r"organi[sz]e (.+?) by\b", r"group \1 by"), (r"file away\b", "archive"), (r"bring back\b", "restore"),
    (r"leave (?=(?:listening|your answer|the code|the media|the layers|this location|this detail|the project|"
     r"the military|the old|the change|the language|playing|the music))", "keep "),
    (r"work with\b", "use"), (r"enter (?=(?:this|these|quotation|the text))", "type "), (r"map (?=recent|major|the|all)", "plot "),
    (r"sketch\b", "draw"), (r"focus the globe on\b", "center the globe on"),
    (r"move the globe camera the (camera|globe)\b", r"fly the \1"), (r"move the globe camera\b", "fly"),
    (r"turn the camera around\b", "rotate the camera around"), (r"angle the camera\b", "tilt the camera"),
    (r"respond to\b", "answer"), (r"enable\b", "turn on"), (r"disable\b", "turn off"),
    (r"tap\b", "press"), (r"move down down\b", "scroll down"), (r"move down (?=back|within|to)", "scroll "),
    (r"refresh (?=the old preference)", "update "), (r"finish (?=the current (?:whatsapp )?call)", "end "),
    (r"bring the sound back on for\b", "unmute"), (r"turn the sound back on for\b", "unmute"),
    (r"make a\b", "create a"), (r"open up\b", "open"), (r"fire up\b", "open"), (r"boot up\b", "open"),
    (r"get rid of\b", "remove"), (r"wipe out\b", "delete"), (r"turn off the (?=(?:civilian|radar|cameras|cctv|military|media island))", "hide the "),
]
VERB_RULES = [(re.compile("^" + pattern, re.I), replacement) for pattern, replacement in VERBS]

NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
           "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
           "forty five": 45, "fifty": 50, "sixty": 60, "ninety": 90, "a hundred": 100, "hundred": 100}
NUMBER_UNIT = re.compile(r"\b(" + "|".join(sorted(NUMBERS, key=len, reverse=True)) +
                         r")(?= (?:seconds?|secs?|minutes?|percent|%))", re.I)


def head_rewrite(text):
    """One leading-verb synonym; the rest of the sentence keeps its case."""
    for pattern, replacement in VERB_RULES:
        found = pattern.match(text)
        if found:
            return found.expand(replacement) + text[found.end():]
    return text


# Trailing softeners that never change the request.
TAIL = re.compile(r"(?:[,\s]+(?:please|pls|for me|right now|real quick|thanks|thank you|if you can|if possible)|,\s*jarvis)+[?.!]*$", re.I)


def keeps_punctuation(text):
    """Dictated or file content keeps its final punctuation ("write exactly ... PM.", "saying see you soon.")."""
    dictation = re.match(r"^(?:write|type|send|text|message|tell(?! me\b)|reply|say|email|draft|compose|whatsapp)\b", text, re.I)
    content = re.search(r"\b(?:saying|that says|exactly|word for word|verbatim|content|containing|asking|telling)\b|[:\"]", text, re.I)
    code = re.search(r"\.(?:py|js|ts|tsx|jsx|json|html|css|md|txt|cpp|c|h|java|go|rs|cs)\b|^(?:modify|edit|refactor|implement|code)\b",
                     text, re.I)
    return bool((dictation and content) or code or re.search(r"\bfile\b|\bcontent\b", text, re.I))


def canonical(text):
    """Canonical command text, or the input unchanged when nothing applies."""
    original = text
    text = re.sub(r"[‘’]", "'", re.sub(r"[“”]", '"', str(text))).strip()
    text = re.sub(r"\s+", " ", text)
    for _ in range(6):
        stripped = WRAPPER.sub("", text, count=1).lstrip(" ,:;-")
        if stripped == text or not stripped:
            break
        text = stripped
    if keeps_punctuation(text):
        pass
    else:
        text = re.sub(r"\s*[?.!]+$", "", text)
    text = head_rewrite(head_rewrite(text))  # "tap" -> "press" -> "click".
    text = re.sub(r"^(?:yes|yeah|okay|ok),? (?=approve\b)", "", text, flags=re.I)
    text = NUMBER_UNIT.sub(lambda m: str(NUMBERS[m[1].lower()]), text)
    text = re.sub(r"\b(\d+(?:\.\d+)?) times\b", r"\1x", text)
    if not keeps_punctuation(text):
        text = re.sub(r"\s*[?.!]+$", "", text)  # Only end punctuation; dictated text keeps its own.
        text = TAIL.sub("", text) or text  # "..., please", "... for me", "... right now".
    return text if text else original
