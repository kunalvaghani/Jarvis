"""YouTube and Spotify playback by name: search, choose, play, verify.

YouTube: YouTube Data API v3 when a key is configured (JARVIS_YOUTUBE_API_KEY or
secrets/youtube.json), otherwise YouTube's own results page. The chosen video is
opened by its exact ID in Jarvis's browser and playback is verified there, so a
spelling difference ("nadan" vs "Nadaan") never blocks playback.

Spotify: no developer key is needed. Jarvis opens a search in the Spotify app, reads
the result list (title, type, artists, Play button) through accessibility, picks the
best-matching song, presses its Play button with Jarvis's pointer and confirms the
now-playing track through the Windows media session.

Every step reports a 'media_card' event for the animated island card.
"""
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote

BASE = Path(__file__).resolve().parents[1]
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/130.0 Safari/537.36')


# --- spelling-tolerant matching ---------------------------------------------------
def sound_key(text):
    """Collapse transliteration variants: nadan/nadaan/naadan, parinde/parindey/parindey."""
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", str(text).lower())
    text = re.sub(r"[^a-z0-9 ]+", " ", text.replace("&", " and "))
    words = []
    for word in text.split():
        word = word.replace("ee", "i").replace("oo", "u").replace("ph", "f").replace("w", "v")
        word = re.sub(r"(.)\1+", r"\1", word)  # aa -> a, nn -> n
        word = re.sub(r"(?<=[a-z]{3})[ey]$", "", word)  # parinde/parindey -> parind
        words.append(word.replace("h", "") if len(word) > 3 else word)
    return " ".join(words)


def similarity(query, text):
    """0..1: how well the spoken query matches a title (word coverage + overall shape)."""
    q, t = sound_key(query).split(), sound_key(text).split()
    if not q or not t:
        return 0.0
    covered = sum(1 for word in q if any(SequenceMatcher(None, word, other).ratio() >= .8 for other in t)) / len(q)
    shape = SequenceMatcher(None, " ".join(q), " ".join(t[:len(q) + 2])).ratio()
    return round(.75 * covered + .25 * shape, 3)


def clean_query(query):
    """Drop filler a person adds when asking: 'the song', 'video', 'music'."""
    query = re.sub(r"\b(?:the |a )?(?:song|track|music|video|full song|audio)\b", " ", query, flags=re.I)
    return " ".join(query.split()) or query


# --- YouTube ----------------------------------------------------------------------
def youtube_key():
    key = os.environ.get("JARVIS_YOUTUBE_API_KEY", "").strip()
    if key:
        return key
    try:
        return json.loads((BASE / "secrets/youtube.json").read_text(encoding="utf-8")).get("api_key", "").strip()
    except (OSError, ValueError):
        return ""


def iso_duration(value):
    match = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def clock_seconds(text):
    parts = [int(p) for p in re.findall(r"\d+", text or "")]
    total = 0
    for part in parts[-3:]:
        total = total * 60 + part
    return total


def youtube_search(query, limit=8, session=None, key=None):
    """[{id, title, channel, duration, thumbnail, source}] ranked by YouTube relevance."""
    import requests
    session = session or requests
    key = youtube_key() if key is None else key
    if key:
        found = session.get("https://www.googleapis.com/youtube/v3/search", timeout=10, params={
            "part": "snippet", "q": query, "type": "video", "maxResults": limit, "key": key, "safeSearch": "moderate"})
        if found.status_code == 200:
            items = [row for row in found.json().get("items", []) if row.get("id", {}).get("videoId")]
            ids = [row["id"]["videoId"] for row in items]
            durations = {}
            if ids:
                details = session.get("https://www.googleapis.com/youtube/v3/videos", timeout=10, params={
                    "part": "contentDetails", "id": ",".join(ids), "key": key})
                if details.status_code == 200:
                    durations = {row["id"]: iso_duration(row["contentDetails"].get("duration"))
                                 for row in details.json().get("items", [])}
            return [{"id": row["id"]["videoId"], "title": row["snippet"]["title"],
                     "channel": row["snippet"].get("channelTitle", ""), "duration": durations.get(row["id"]["videoId"], 0),
                     "thumbnail": "https://i.ytimg.com/vi/%s/mqdefault.jpg" % row["id"]["videoId"],
                     "source": "youtube-data-api-v3"} for row in items]
        # An invalid/exhausted key falls back to the keyless search below.
    page = session.get("https://www.youtube.com/results", timeout=10, params={"search_query": query, "hl": "en"},
                       headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    marker = "var ytInitialData = "
    start = page.text.find(marker)
    if start < 0:
        raise ValueError("YouTube search returned no results page.")
    data, _ = json.JSONDecoder().raw_decode(page.text, start + len(marker))
    rows = []

    def walk(node):
        if len(rows) >= limit:
            return
        if isinstance(node, dict):
            video = node.get("videoRenderer")
            if isinstance(video, dict) and video.get("videoId"):
                rows.append({"id": video["videoId"],
                             "title": "".join(run.get("text", "") for run in video.get("title", {}).get("runs", [])),
                             "channel": ((video.get("ownerText") or {}).get("runs") or [{}])[0].get("text", ""),
                             "duration": clock_seconds((video.get("lengthText") or {}).get("simpleText", "")),
                             "thumbnail": "https://i.ytimg.com/vi/%s/mqdefault.jpg" % video["videoId"],
                             "source": "youtube-search-page"})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(data)
    return rows


def choose_youtube(query, rows):
    """YouTube's ranking first; among the top five prefer a clear title match, skip shorts and live."""
    playable = [row for row in rows if row["duration"] > 45] or rows
    if not playable:
        return None
    # Remixes, covers and edited versions only when the user asked for one.
    variant = re.compile(r"\b(?:remix|cover|reverb|slowed|sped up|lofi|lo-fi|8d|karaoke|instrumental|mashup|nightcore)\b", re.I)
    wanted = bool(variant.search(query))
    for row in playable[:6]:
        if similarity(query, row["title"] + " " + row["channel"]) >= .6 and (wanted or not variant.search(row["title"])):
            return row  # The first clear match in YouTube's own relevance order.
    return playable[0]


def fetch_image(url, size=(96, 96)):
    """A small base64 JPEG for the island card; empty on any failure."""
    try:
        import base64
        import io
        import requests
        from PIL import Image
        response = requests.get(url, timeout=5)
        if response.status_code != 200 or len(response.content) > 2_000_000:
            return ""
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        side = min(image.size)
        image = image.crop(((image.width - side) // 2, (image.height - side) // 2,
                            (image.width + side) // 2, (image.height + side) // 2)).resize(size)
        output = io.BytesIO()
        image.save(output, "JPEG", quality=85)
        return base64.b64encode(output.getvalue()).decode()
    except Exception:
        return ""


def card(service, phase, title="", subtitle="", image="", position=0.0, duration=0.0, detail=""):
    return {"service": service, "phase": phase, "title": title[:120], "subtitle": subtitle[:120], "image": image,
            "position": float(position or 0), "duration": float(duration or 0), "detail": detail[:80],
            "at": time.time()}


def pause_other(actions, service):
    """Pause the other player so two songs never play over each other. Best effort."""
    try:
        if service == "youtube":
            now = spotify_now() if spotify_window() else None
            if now and now.get("status") == "playing":
                from .spotify import control
                control("pause", lambda: False)
        elif youtube_state(actions).get("paused") is False:
            actions.browser_automation.request("control", lambda: False, value="pause")
    except Exception:
        pass


def play_youtube(actions, query, cancelled):
    query = clean_query(query)
    actions.report("media_card", card("youtube", "searching", query, "Finding the best match"))
    rows = youtube_search(query)
    if cancelled():
        raise ValueError("YouTube request cancelled before playback.")
    chosen = choose_youtube(query, rows)
    if not chosen:
        actions.report("media_card", card("youtube", "error", query, "No YouTube results"))
        raise ValueError("YouTube found no video for " + query + ".")
    image = fetch_image(chosen["thumbnail"])
    pause_other(actions, "youtube")
    actions.report("media_card", card("youtube", "loading", chosen["title"], chosen["channel"], image, 0, chosen["duration"]))
    result = actions._browser().request("play_video", cancelled, video_id=chosen["id"], new_task=True)
    if result.get("verified") is not True:
        raise ValueError("The video opened but playback was not verified; nothing was replayed.")
    state = result.get("state") or {}
    actions.report("media_card", card("youtube", "playing", chosen["title"], chosen["channel"], image,
                                      state.get("position", 0), state.get("duration") or chosen["duration"],
                                      "Ad skipped" if result.get("ad_skipped") else ""))
    actions.last_media = "youtube"
    actions.last_youtube = {"title": chosen["title"], "channel": chosen["channel"], "image": image}
    return "Playing " + chosen["title"] + " on YouTube."


# --- Spotify ----------------------------------------------------------------------
TYPES = ("Song", "Album", "Playlist", "Artist", "Podcast", "Episode", "Audiobook")


def spotify_results(controls):
    """Structured search results from the Spotify app's accessibility tree."""
    results, current = [], None
    for control in controls:
        name, context, role = control.get("name", ""), control.get("context", "") or "", control.get("role")
        if context == "Search results" and role == "DataItem" and not name.startswith("Play "):
            current = {"title": name, "kind": "", "artists": "", "play": None}
            results.append(current)
            continue
        if current is None:
            continue
        kind = re.match(r"(%s)\b(?:\s*•\s*(.*))?$" % "|".join(TYPES), name)
        if role == "DataItem" and context == current["title"] and kind and not current["kind"]:
            current["kind"], current["artists"] = kind[1], (kind[2] or "").strip()
        elif role == "Button" and name in {"Play", "Play " + current["title"]} and current["play"] is None:
            current["play"] = control
    return [row for row in results if row["play"] is not None]


def choose_spotify(query, results):
    """Best-matching song; title (and artists, if named) must clearly match."""
    songs = [row for row in results if row["kind"] == "Song"] or [row for row in results if row["kind"] in {"", "Album"}]
    scored = [(max(similarity(query, row["title"]), similarity(query, row["title"] + " " + row["artists"])), -i, row)
              for i, row in enumerate(songs)]
    if not scored:
        return None
    best = max(scored)
    return best[2] if best[0] >= .55 else None


def spotify_window():
    from .window_focus import windows
    rows = windows("Spotify.exe")
    return rows[0][0] if rows else None


def spotify_now(cancelled=lambda: False, timeout=3.):
    """(status, title, artist, position, duration, image) from the Windows media session."""
    import asyncio
    import threading
    from .island_media import metadata
    found = {}

    def read():
        initialized = False
        try:
            from winrt.runtime import ApartmentType, init_apartment, uninit_apartment
            init_apartment(ApartmentType.MULTI_THREADED)
            initialized = True
            found["info"] = asyncio.run(asyncio.wait_for(metadata(), timeout))
        except Exception:
            pass
        finally:
            if initialized:
                uninit_apartment()
    # A fresh thread: WinRT awaits deadlock on a thread that COM (e.g. the volume API) made single-threaded.
    worker = threading.Thread(target=read, daemon=True, name="jarvis-media-session")
    worker.start()
    worker.join(timeout)
    return found.get("info")


def play_spotify(actions, query, cancelled, clock=time.monotonic, sleep=time.sleep):
    from .spotify import open_app
    from .window_focus import focus
    query = clean_query(query)
    actions.report("media_card", card("spotify", "searching", query, "Finding the best match"))
    if spotify_window() is None:
        open_app(cancelled)
        deadline = clock() + 12
        while spotify_window() is None and clock() < deadline:
            sleep(.3)
    os.startfile("spotify:search:" + quote(query, safe=""))
    handle, results, snapshot = None, [], {}
    deadline = clock() + 10
    while clock() < deadline and not cancelled():
        handle = spotify_window()
        if handle:
            focus(handle)
            try:
                snapshot = actions._ui().runner({"operation": "list", "handle": handle, "owner_pid": os.getpid()}, cancelled)
            except ValueError:
                snapshot = {}
            box = [c for c in snapshot.get("controls", []) if c.get("role") == "ComboBox" and c.get("name")]
            searched = any(sound_key(c["name"].replace("+", " ")) == sound_key(query) for c in box)
            results = spotify_results(snapshot.get("controls", [])) if searched else results
            if choose_spotify(query, results):
                break  # The old results can linger briefly after the search box changes.
        sleep(.3)
    if cancelled():
        raise ValueError("Spotify request cancelled before playback.")
    chosen = choose_spotify(query, results)
    if chosen is None:
        actions.report("media_card", card("spotify", "error", query, "No matching song"))
        raise ValueError("Spotify showed no song clearly matching " + query + "." if results else
                         "Spotify search results did not load; nothing was played.")
    pause_other(actions, "spotify")
    before = spotify_now()
    snapshot["media_platform"] = "spotify"
    actions._ui()._activate(handle, snapshot, chosen["play"], "play", cancelled)
    deadline = clock() + 8
    while clock() < deadline:
        now = spotify_now()
        if (now and now.get("status") == "playing" and similarity(chosen["title"], now.get("title", "")) >= .7
                and (not before or before.get("title") != now.get("title") or before.get("status") != "playing")):
            actions.report("media_card", card("spotify", "playing", now["title"], now.get("artist", ""), now.get("image", ""),
                                              now.get("position", 0), now.get("duration", 0)))
            actions.last_media = "spotify"
            return "Playing " + now["title"] + " by " + now.get("artist", "") + " on Spotify."
        sleep(.25)
    actions.report("media_card", card("spotify", "error", chosen["title"], "Playback not confirmed"))
    raise ValueError("Play was pressed once for " + chosen["title"] + ", but Spotify did not confirm playback. Nothing was replayed.")


CONTROL_TEXT = {"play": "Resumed", "pause": "Paused", "next": "Next", "previous": "Previous", "restart": "From the start",
                "mute": "Muted", "unmute": "Unmuted", "shuffle_on": "Shuffle on", "shuffle_off": "Shuffle off",
                "repeat_off": "Repeat off", "repeat_one": "Repeat this song", "repeat_all": "Repeat all",
                "volume_up": "Volume up", "volume_down": "Volume down", "speed_up": "Faster", "speed_down": "Slower",
                "fullscreen": "Fullscreen", "exit_fullscreen": "Exited fullscreen", "theater": "Theater mode",
                "default_view": "Default view", "miniplayer": "Miniplayer", "captions": "Captions toggled",
                "captions_on": "Captions on", "captions_off": "Captions off", "status": "Now playing"}


def control_text(action):
    action = str(action or "")
    if action in CONTROL_TEXT:
        return CONTROL_TEXT[action]
    if action.startswith("seek_"):
        seconds = int(action[5:]) if action[5:].lstrip("-").isdigit() else 0
        return ("Back " if seconds < 0 else "Forward ") + str(abs(seconds)) + "s" if abs(seconds) < 3600 else "From the start"
    if action.startswith("volume_") or action.isdigit():
        return "Volume " + action.removeprefix("volume_") + "%"
    if action.startswith("position_"):
        return "Jumped to " + action[9:] + "%"
    return action.replace("_", " ").capitalize()


def control_card(actions, command):
    """Island card after a YouTube/Spotify control command (pause, next, volume...). Never raises."""
    try:
        if command.extra == "auto" or command.kind == "click_control":
            command = getattr(actions, "media_resolved", None) or resolve(actions, command)
            actions.media_resolved = None
        elif command.kind == "media_control" and not command.extra:
            command = type(command)(command.kind, command.value, active_service(actions))
        service = ("spotify" if command.kind.startswith("spotify") else
                   command.extra if command.extra in {"youtube", "spotify"} else getattr(actions, "last_media", None) or "youtube")
        value = str(command.value)
        detail = control_text(value if command.kind != "spotify_volume" or value in {"mute", "unmute"} else "volume_" + value)
        if service == "spotify":
            time.sleep(.35)  # Let the media session publish the new state.
            now = spotify_now() or {}
            phase = "playing" if now.get("status") == "playing" else "paused"
            actions.report("media_card", card("spotify", phase, now.get("title") or "Spotify", now.get("artist", ""),
                                              now.get("image", ""), now.get("position", 0), now.get("duration", 0), detail))
            return
        last = getattr(actions, "last_youtube", None) or {}
        state = {}
        browser = getattr(actions, "browser_automation", None)
        if browser is not None and "youtube.com" in getattr(browser, "last_url", ""):
            try:
                state = browser.request("control", lambda: False, value="status").get("state") or {}
            except Exception:
                state = {}
        title = state.get("title") or last.get("title") or "YouTube"
        same = last and similarity(last.get("title", ""), title) >= .8
        actions.report("media_card", card("youtube", "paused" if state.get("paused") else "playing", title,
                                          last.get("channel", "") if same else "", last.get("image", "") if same else "",
                                          state.get("position", 0), state.get("duration", 0), detail))
    except Exception:
        pass  # The card is decoration; the command result was already reported.


def youtube_state(actions):
    """Owned YouTube player state, or {} when Jarvis's browser is not on YouTube."""
    browser = getattr(actions, "browser_automation", None)
    if browser is None or "youtube.com/watch" not in getattr(browser, "last_url", ""):
        return {}
    try:
        return browser.request("control", lambda: False, value="status").get("state") or {}
    except Exception:
        return {}


def active_service(actions):
    """The service that is playing now; otherwise the one Jarvis used last; otherwise Spotify."""
    spotify = spotify_now()
    youtube = youtube_state(actions)
    playing = [name for name, ok in (("spotify", bool(spotify and spotify.get("status") == "playing")),
                                     ("youtube", bool(youtube and youtube.get("paused") is False))) if ok]
    last = getattr(actions, "last_media", None)
    if not playing:
        available = (["spotify"] if spotify else []) + (["youtube"] if youtube else [])
        return last if last in available else (available[0] if available else last or "spotify")
    if last in playing:  # Both playing: the one Jarvis started last.
        return last
    return playing[0]


def resolve(actions, command):
    """Turn an unscoped transport command into a Spotify or YouTube one."""
    from .commands import Command
    service = active_service(actions)
    if command.kind == "click_control":
        action = command.value
    elif command.kind == "spotify_volume":
        action = command.value if command.value in {"mute", "unmute"} else "volume_" + command.value
    else:
        action = command.value
    if service == "youtube" and (action in {"play", "pause", "next", "previous", "status", "mute", "unmute", "volume_up",
                                            "volume_down", "restart"} or re.fullmatch(r"(?:seek_-?|volume_)\d{1,3}", action)):
        return Command("media_control", action, "youtube")
    if command.kind == "click_control":
        return Command("spotify_control", action, "")
    return Command(command.kind, command.value, "")


def play(actions, query, service, cancelled):
    """Play by name on the named service, or the last-used/default one, falling back to the other."""
    default = actions.config.get("media", {}).get("default_service", "youtube")
    first = service or getattr(actions, "last_media", None) or default
    order = [first] + ([] if service else [other for other in ("youtube", "spotify") if other != first])
    errors = []
    for name in order:
        try:
            return (play_youtube if name == "youtube" else play_spotify)(actions, query, cancelled)
        except ValueError as exc:
            if cancelled() or "cancelled" in str(exc):
                raise
            errors.append(name.capitalize() + ": " + str(exc))
    raise ValueError(" ".join(errors))
