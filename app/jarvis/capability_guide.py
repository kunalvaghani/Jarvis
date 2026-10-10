"""What Jarvis can do, which APIs it is connected to, and when to use what.

Answers are built from Jarvis's own registries and the latest live API check, so they stay accurate when
features change. "check your APIs" runs that live check (about 30 seconds) and saves the result.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

AREAS = [
    ("Conversation and memory", "Talk naturally in a long call-style conversation; I remember facts about you, "
     "summarise our conversations in Obsidian and recall them later.",
     ["remember that my sister's name is Riya", "what do you know about me", "what did we talk about yesterday",
      "forget that I have an exam"], "Use for questions, follow-ups and anything you want me to keep in mind."),
    ("Tasks on your PC", "Plan and run multi-step tasks with my own cursor, queue several tasks while we talk, "
     "and cancel a specific one.", ["open notepad and write a leave application", "cancel the YouTube one",
                                    "what's in my queue"], "Use for anything that needs clicking, typing or apps."),
    ("Writing", "Compose text with the model where your cursor is, type exact words, or hold Left Ctrl + Left Alt "
     "to dictate.", ["write a polite reply here", "write exactly see you at 6"], "Use inside any app or text box."),
    ("YouTube and Spotify", "Play songs and videos by name and control playback on whichever player is active.",
     ["play nadan parinde", "play blinding lights on spotify", "pause", "next song", "volume 40", "what's playing"],
     "Use for music and videos; I pick the clearly matching result and verify it plays."),
    ("WhatsApp", "Message people (first names are fine, I ask when several match), reply to unread chats, "
     "preview every message before sending, and ask before answering calls.",
     ["send a WhatsApp message to Jay saying I'll be late", "reply to my WhatsApp messages", "approve", "pick up"],
     "Use for chats; nothing is sent without your approval."),
    ("Gmail", "Read, write, draft, send, label, read aloud and delete emails through the Gmail API.",
     ["read my latest emails", "draft an email to ...", "send it"], "Use for email; sends and deletes ask first."),
    ("Weather and emergencies", "Watch the forecast, air quality, earthquakes, cyclones and floods around you and "
     "alert you about bad or upcoming bad weather, even while I'm working.",
     ["is bad weather coming", "weather alerts", "what's the air quality"], "Runs by itself; ask any time."),
    ("Live data", "Answer from free public APIs: weather, news, crypto and currency rates, Wikipedia and research "
     "papers, maps and routes, flights, space and sports.",
     ["bitcoin price", "USD to INR", "latest news about India", "route from Vadodara to Ahmedabad"],
     "Use for anything current; I cite the source and time."),
    ("Files, folders and coding", "Open, create, rename and delete files and folders (deletes go to the Recycle "
     "Bin after approval), and build or edit code in your projects with checks.",
     ["open my downloads", "create a file notes.txt", "fix the bug in my jarvis project"],
     "Use for local files and projects."),
]


def capabilities_text():
    lines = ["Here's what I can do:"]
    for name, summary, examples, _ in AREAS:
        lines.append(name + ": " + summary + " For example, \"" + examples[0] + "\".")
    lines.append("Ask \"how do I use WhatsApp\" (or any area) for details, or \"which APIs are you connected to\".")
    return " ".join(lines)


def area_help(question):
    lower = question.casefold()
    for name, summary, examples, when in AREAS:
        keys = [w for w in re.findall(r"[a-z]+", name.casefold()) if len(w) > 3 and w not in {"your", "with"}]
        if any(k in lower for k in keys):
            return (name + ": " + summary + " Try: " + "; ".join("\"" + e + "\"" for e in examples) + ". " + when)
    return None


def health_path(base):
    return Path(base) / ".jarvis-runtime" / "api-health.json"


def apis_text(base):
    from .realtime_catalog import CATALOG
    groups = {}
    for provider in CATALOG.values():
        groups.setdefault(provider.category, []).append(provider.name)
    text = ("I'm connected to " + str(len(CATALOG)) + " free public data APIs (" +
            "; ".join(category + ": " + ", ".join(names[:6]) + ("…" if len(names) > 6 else "") for category, names in groups.items()) +
            "), plus Gmail (Google API), YouTube (Data API v3 when a key is saved, otherwise keyless search), "
            "Spotify and WhatsApp through their Windows apps, and local Ollama models.")
    try:
        report = json.loads(health_path(base).read_text(encoding="utf-8"))
        broken = [r["name"] for r in report["providers"] if r["status"] not in WORKING | {"needs_configuration"}]
        setup = [r["name"] for r in report["providers"] if r["status"] == "needs_configuration"]
        text += (" Last live check " + report["checked_local"] + ": " + str(report["ok"]) + " of " + str(report["total"]) +
                 " working" + (", not responding: " + ", ".join(broken[:6]) if broken else "") +
                 (", optional self-hosted: " + ", ".join(setup) if setup else "") + ".")
    except (OSError, ValueError, KeyError):
        text += " Say \"check your APIs\" and I'll test them all live."
    return text


WORKING = {"ok", "rate_limited", "not_found"}  # Answered, used moments ago, or answered "no such record".
SAMPLE = {
    "wikipedia": {"id": "India"}, "wikidata": {"id": "Q668"}, "dictionary": {"id": "rain"}, "postcodes": {"id": "390001", "country": "IN"},
    "countries": {"id": "India"}, "coinpaprika": {"id": "btc-bitcoin"}, "defillama": {"id": "aave"}, "listenbrainz": {"id": "rob"},
    "cover_art": {"id": "76df3287-6cda-33eb-8e9a-044b5e15ffdd"}, "food": {"id": "737628064502"}, "binance": {"symbol": "BTC-USDT"},
    "binance_stream": {"symbol": "BTC-USDT"}, "frankfurter": {"base": "USD", "target": "INR"}, "nws": {"latitude": 40.71, "longitude": -74.0},
    "worldtime": {"timezone": "Asia/Kolkata"}, "timeapi": {"timezone": "Asia/Kolkata"}, "musicbrainz": {"query": "Arijit Singh"},
}


def live_realtime(actions):
    """Jarvis's realtime layer, or a temporary enabled copy when background monitoring is switched off."""
    realtime = getattr(actions, "realtime", None)
    if realtime is not None and realtime.options.get("enabled"):
        return realtime
    from .realtime import Realtime
    options = dict(actions.config.get("realtime", {}), enabled=True)
    return Realtime(actions.base, options, lambda *args: None)


def check_apis(actions, cancelled=lambda: False):
    """Live check of every catalog provider through Jarvis's own realtime layer; saves and summarises."""
    from .realtime_catalog import CATALOG
    realtime = live_realtime(actions)
    location = realtime.detect_location(cancelled) or {}
    here = {"latitude": location.get("latitude", 22.3072), "longitude": location.get("longitude", 73.1812)}

    def one(key):
        args = {"query": "weather", **SAMPLE.get(key, {})}
        if key in {"weather", "air", "marine", "flood", "met", "sunrise", "power", "adsblol", "overpass", "opensky"}:
            args.update(here)
        if key == "osrm":
            args.update(here, to_latitude=here["latitude"] + .5, to_longitude=here["longitude"] - .5)
        started = time.monotonic()
        try:
            row = realtime.query(key, args, cancelled)
            status, detail = row.get("status"), row.get("detail", "")
            if row.get("fallback_for"):
                detail = "answered by " + row.get("name", "a fallback")
        except Exception as exc:
            status, detail = "error", type(exc).__name__
        return {"id": key, "name": CATALOG[key].name, "category": CATALOG[key].category, "status": status,
                "seconds": round(time.monotonic() - started, 1), "detail": str(detail)[:160]}

    from .realtime_sources import FALLBACK
    first = [key for key in CATALOG if key not in FALLBACK]
    with ThreadPoolExecutor(8) as pool:
        done = dict(zip(first, pool.map(one, first)))
        # Providers with a backup run after their backups, as they would in normal use.
        later = [key for key in CATALOG if key in FALLBACK]
        done.update(zip(later, pool.map(one, later)))
    rows = [done[key] for key in CATALOG]
    extra = []
    try:
        from .media_player import youtube_key
        extra.append({"id": "youtube", "name": "YouTube Data API v3", "category": "media",
                      "status": "ok" if youtube_key() else "keyless", "seconds": 0,
                      "detail": "" if youtube_key() else "no key saved; keyless search in use"})
    except Exception:
        pass
    started = time.monotonic()
    try:
        from .gmail_api import API
        api = API(actions.base)
        try:
            api.call("GET", "profile")  # Read-only; proves the token and the API both work.
        finally:
            api.close()
        gmail = ("ok", "")
    except Exception as exc:
        gmail = ("needs_sign_in" if "Connect Gmail" in str(exc) else "unavailable", str(exc)[:120])
    extra.append({"id": "gmail", "name": "Gmail API", "category": "email", "status": gmail[0],
                  "seconds": round(time.monotonic() - started, 1), "detail": gmail[1]})
    ok = sum(r["status"] in WORKING for r in rows)
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "checked_local": datetime.now().strftime("%Y-%m-%d %H:%M"), "ok": ok, "total": len(rows),
              "providers": rows, "apps": extra}
    path = health_path(actions.base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    broken = [r["name"] for r in rows if r["status"] not in WORKING | {"needs_configuration"}]
    setup = [r["name"] for r in rows if r["status"] == "needs_configuration"]
    return (str(ok) + " of " + str(len(rows)) + " public APIs are working right now." +
            (" Not responding: " + ", ".join(broken) + "." if broken else "") +
            (" Optional, need your own server: " + ", ".join(setup) + "." if setup else "") +
            "".join(" " + e["name"] + ": " + e["status"].replace("_", " ") + "." for e in extra))


CAPABILITY_Q = re.compile(r"(?:what (?:all )?(?:can you do|are your (?:capabilities|features|skills|abilities))|"
                          r"what (?:all )?(?:tools|skills|features) (?:do you have|can you use)|"
                          r"what are you capable of|help me understand what you can do|list your (?:features|capabilities))", re.I)
API_Q = re.compile(r"(?:which|what) (?:all )?apis?(?: are you| do you| can you)?(?: connected to| have| use| using)?|"
                   r"(?:list|show)(?: me)? (?:your |all )?apis?", re.I)
HOW_Q = re.compile(r"(?:how (?:do|can) i use|how do you (?:use|handle)|when (?:do|should) (?:you|i) use|what can you do (?:with|on|in)|"
                   r"help (?:me )?with) (?P<what>.+)", re.I)
CHECK_Q = re.compile(r"(?:check|test)(?: all)?(?: of)? (?:your |the )?(?:apis?|connections|integrations)|api (?:status|health)", re.I)


def parse_command(text):
    from .commands import Command
    clean = re.sub(r"[.!?]+$", "", text.strip())
    if CHECK_Q.fullmatch(clean):
        return Command("api_health", "")
    return None


def answer(question, base):
    """Deterministic answer for capability questions, or None."""
    clean = re.sub(r"[.!?]+$", "", question.strip())
    if CAPABILITY_Q.fullmatch(clean):
        return capabilities_text()
    if API_Q.fullmatch(clean):
        return apis_text(base)
    match = HOW_Q.fullmatch(clean)
    if match:
        return area_help(match["what"])
    return None
