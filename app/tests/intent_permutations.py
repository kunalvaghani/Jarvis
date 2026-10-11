"""Permutations of the intent testbook (tests/fixtures/intent_testbook.txt).

Each scenario's direct sentence is re-phrased with the lead-ins and endings people actually use in speech:
politeness ("could you ... ?"), wake words ("Hey Jarvis,"), discourse markers ("quick question:", "by the
way,"), and trailing softeners ("please", "for me", "right now"). Every variant must reach the same intent
as the direct sentence.
"""
import re
from pathlib import Path

CORPUS = Path(__file__).parent / "fixtures" / "intent_testbook.txt"
QUESTION = re.compile(r"^(?:what|which|who|whose|where|when|why|how|is|are|was|were|did|do|does|can|could|will|would|have|has|should)\b", re.I)
NEGATION = re.compile(r"^(?:do not|don'?t|never)\b", re.I)
WH = re.compile(r"^(?:what|which|who|where|how|whether)\b", re.I)

IMPERATIVE = ["Could you {x}?", "Can you {x}?", "Would you {x}?", "Will you {x}?", "Could you please {x}?",
              "Would you be able to {x}?", "Please {x}.", "{X}, please.", "{X} for me.", "{X} right now.",
              "I need you to {x}.", "I want you to {x}.", "I'd like you to {x}.", "Go ahead and {x}.", "Kindly {x}.",
              "Hey Jarvis, {x}.", "Jarvis, {x}", "Okay Jarvis, {x}.", "Hey, could you {x}?", "Jarvis, could you {x}?",
              "By the way, {x}.", "Also, {x}.", "Okay, {x}.", "Alright, {x}.", "Real quick, {x}."]
QUESTIONS = ["Hey Jarvis, {x}?", "Jarvis, {x}?", "Quick question: {x}?", "Tell me one thing: {x}?", "Just checking - {x}?",
             "By the way, {x}?", "Hey, {x}?", "Okay, {x}?", "So, {x}?", "Um, {x}?", "{X}?", "{X}"]
WH_QUESTIONS = ["Do you know {x}?", "Could you tell me {x}?", "Can you tell me {x}?", "Any idea {x}?"]
NEGATIONS = ["Please {x}.", "Make sure you {x}.", "Be sure to {x}.", "Hey Jarvis, {x}.", "Just checking - {x}.", "Remember to {x}."]


def scenarios():
    rows = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            number, direct, polite, everyday = line.split("|")
            rows.append((number, direct, polite, everyday))
    return rows


def variants(direct):
    """Re-phrasings of one direct sentence (the direct form itself excluded)."""
    core = direct.strip().rstrip(".?!")
    lower = core[0].lower() + core[1:] if not re.match(r"^(?:I|I'm|I've|I'd|God's|YouTube|Spotify|WhatsApp|Gmail|Telegram|Discord|"
                                                       r"Notepad|Word|Chrome|Windows|Jarvis|GitHub|Obsidian)\b", core) else core
    if NEGATION.match(core):
        templates = NEGATIONS
    elif QUESTION.match(core):
        templates = QUESTIONS + (WH_QUESTIONS if WH.match(core) else [])
    elif re.match(r"^(?:I|I'm|No|The|That|This|Earlier|If|After|While|When|Actually)\b", core):
        templates = ["Hey Jarvis, {x}.", "Jarvis, {x}.", "By the way, {x}.", "Okay, {x}.", "{X}"]  # Statements and corrections.
    else:
        templates = IMPERATIVE
    seen, out = {direct}, []
    for template in templates:
        text = template.format(x=lower, X=core)
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out
