"""Other messaging apps. WhatsApp has its own module (whatsapp.py); this covers Telegram Desktop and says
plainly when an app is not signed in or not supported yet. The same rules apply: choose the person, preview the
exact text on the island, send only after approval, confirm the message appeared, never resend."""
import json
import os
import re
import time

from . import whatsapp as wa

APPS = {
    "telegram": {"exe": "Telegram.exe", "launch": "shell:AppsFolder\\TelegramMessengerLLP.TelegramDesktop_t4vj0pshhgkwm!Telegram.TelegramDesktop.Store",
                 "label": "Telegram"},
    "discord": {"exe": "Discord.exe", "label": "Discord"},
    "teams": {"exe": "ms-teams.exe", "label": "Teams"},
    "signal": {"exe": "Signal.exe", "label": "Signal"},
    "instagram": {"exe": "", "label": "Instagram"},
    "messenger": {"exe": "", "label": "Messenger"},
    "skype": {"exe": "Skype.exe", "label": "Skype"},
}
SUPPORTED = {"telegram"}
APP_WORDS = "|".join(APPS)


def parse_command(text):
    from .commands import Command
    clean = re.sub(r"[.!?]+$", "", text.strip())
    match = None
    for pattern in (r"(?:send|write)(?: a| an)? (?:message|msg|text) to (?P<who>.+?) on (?P<app>" + APP_WORDS + r")",
                    r"(?:message|text|ping) (?P<who>.+?) on (?P<app>" + APP_WORDS + r")"):
        match = re.fullmatch(pattern + r"(?:,? " + wa.HOW + r" (?P<what>.+))?", clean, re.I)
        if match:
            break
    if not match:
        return None
    who, app, what = match["who"].strip(), match["app"].casefold(), (match["what"] or "").strip()
    verbatim = bool(re.match(r"exactly |word for word ", what, re.I))
    if verbatim:
        what = re.sub(r"^(?:exactly|word for word)[:,]? ", "", what, flags=re.I)
    return Command("messenger_send", who, json.dumps({"app": app, "instruction": what, "verbatim": verbatim}))


def _window(exe):
    from .window_focus import windows
    rows = windows(exe)
    return rows[0][0] if rows else None


def send(actions, who, data, cancelled=lambda: False):
    app = data.get("app", "")
    info = APPS.get(app)
    if not info:
        raise wa.WhatsAppError("I don't know that messaging app.")
    if app not in SUPPORTED:
        raise wa.WhatsAppError(info["label"] + " messaging isn't automated yet. WhatsApp and Telegram are; "
                               "say 'send a WhatsApp message to " + who + "' instead.")
    return send_telegram(actions, who, data.get("instruction", ""), bool(data.get("verbatim")), cancelled)


def _items(handle):
    uia, U = wa._uia()
    return wa.read(uia.ElementFromHandle(handle))


def send_telegram(actions, who, instruction, verbatim, cancelled, sleep=time.sleep):
    from .jarvis_pointer import tap
    from .window_focus import focus
    with wa.physical():
        handle = _window("Telegram.exe")
        if not handle:
            os.startfile(APPS["telegram"]["launch"])
            deadline = time.monotonic() + 15
            while not handle and time.monotonic() < deadline and not cancelled():
                sleep(.5)
                handle = _window("Telegram.exe")
        if not handle:
            raise wa.WhatsAppError("Telegram did not open.")
        focus(handle)
        sleep(.6)
        items = _items(handle)
        names = {i["name"] for i in items}
        if "Your Phone Number" in names or "Quick log in using QR code" in names:
            raise wa.WhatsAppError("Telegram is open but not signed in. Sign in once, then ask me again.")
        search = next((i for i in items if i["type"] == "edit" and i["name"].casefold().startswith("search")), None)
        if not search:
            raise wa.WhatsAppError("Telegram's search box was not found, so nothing was typed.")
        actions.report(wa.CARD, wa.card("searching", who, "Finding the contact on Telegram"))
        wa.set_value(search["el"], who)
        sleep(1.2)
        rows = [{"name": i["name"].split("\n")[0], "group": False, "time": "", "preview": "", "el": i["el"], "rect": i["rect"]}
                for i in _items(handle) if i["type"] in {"item", "row", "button"} and i["name"] and i["rect"][1] > search["rect"][3]]
        found = wa.match_contacts(who, rows)
        if not found:
            raise wa.WhatsAppError("I couldn't find " + who + " in Telegram.")
        if len(found) > 1:
            prompt = wa.Prompt("Which " + who + "?", [{"label": r["name"]} for r in found[:8]], "choice")
            answer = wa.ask(actions, prompt, cancelled, "Which " + who + "? " +
                            ", ".join(str(n + 1) + ", " + r["name"] for n, r in enumerate(found[:8])))
            if not isinstance(answer, int):
                return "Okay, I didn't message anyone."
            row = found[answer]
        else:
            row = found[0]
        r = row["el"].CurrentBoundingRectangle
        tap((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        sleep(1.)
        items = _items(handle)
        header = [i for i in items if i["type"] == "text" and wa.names_match(i["name"], row["name"])]
        if not header:
            raise wa.WhatsAppError("I couldn't confirm that " + row["name"] + "'s chat opened, so nothing was typed.")
        text = instruction.strip() if verbatim else wa.draft(actions, row["name"], instruction, (), "write")
        actions.report(wa.CARD, wa.card("preview", row["name"], text, "Telegram · waiting for approval"))
        prompt = wa.Prompt("Send this Telegram message to " + row["name"] + "?",
                           [{"label": "Approve and send", "context": text}, {"label": "Cancel"}], "confirm")
        if wa.ask(actions, prompt, cancelled, "Here's the Telegram message for " + row["name"] + ": " + text +
                  ". Should I send it?") != 0:
            return "Okay, I didn't send it."
        if focus(handle) is False or wa.ctypes.windll.user32.GetForegroundWindow() != handle:
            raise wa.WhatsAppError("Telegram lost focus; nothing was typed.")
        previous = actions.desktop.target
        actions.desktop.target = handle
        try:
            actions.desktop.type(text, cancelled)
        finally:
            actions.desktop.target = previous
        wa.keys((0x0D, 0), (0x0D, 1))
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            sleep(.4)
            if any(wa.normalized(i["name"]) == wa.normalized(text) for i in _items(handle) if i["type"] == "text"):
                actions.report(wa.CARD, wa.card("sent", row["name"], text, "Sent on Telegram"))
                return "Sent to " + row["name"] + " on Telegram: " + text
        raise wa.WhatsAppError("Enter was pressed once, but the Telegram message could not be confirmed. Check Telegram before resending.")
