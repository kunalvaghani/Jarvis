"""Warm Playwright worker owning a separate Chrome profile and window."""
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit, parse_qs

from .browser import music_search_url, url_for
from .browser_cursor import click as cursor_click
from .ui_controls import label_key, UNSAFE_INFERRED


def parsed(url):
    return url if hasattr(url, "scheme") and hasattr(url, "path") else urlsplit(str(url))


def player_message(action, state):
    """Short, speakable summary of the verified player state."""
    def clock(seconds):
        seconds = int(seconds or 0)
        return "%d:%02d" % (seconds // 60, seconds % 60)
    title = state.get("title") or "the video"
    where = clock(state.get("position")) + " of " + clock(state.get("duration"))
    if action == "status":
        return ("Paused: " if state.get("paused") else "Playing: ") + title + ", at " + where + " on YouTube."
    words = {"play": "Resumed", "pause": "Paused", "mute": "Muted", "unmute": "Unmuted", "restart": "Restarted",
             "next": "Next video:", "previous": "Previous video:"}
    if action in {"next", "previous"}:
        return words[action] + " " + title + "."
    if action.startswith("volume") or action.startswith("speed"):
        return "YouTube volume %d%%, speed %gx." % (round((state.get("volume") or 0) * 100), state.get("speed") or 1)
    return words.get(action, "Done") + " on YouTube."


def reveal_controls(page):
    """YouTube hides its control bar until the pointer moves over the player."""
    try:
        page.locator("#movie_player").hover(timeout=2000)
    except Exception:
        pass


class Session:
    def __init__(self):
        self.driver = self.context = self.page = None
        self.user_closed = False

    def open(self, settings):
        if self.context:
            if self.user_closed or self.page.is_closed():
                self.user_closed = True
                raise ValueError("Jarvis browser was closed deliberately; say open Jarvis browser to start a new session.")
            return
        if self.user_closed:
            raise ValueError("Jarvis browser was closed deliberately; explicitly open a new session.")
        from playwright.sync_api import sync_playwright
        self.driver = sync_playwright().start()
        profile = Path(__file__).resolve().parent.parent / ".jarvis-runtime" / "browser-profile"
        options = {"headless": bool(settings.get("headless", False)), "viewport": {"width": 1280, "height": 800},
                   "args": ["--force-renderer-accessibility", "--no-first-run"]}
        executable = settings.get("executable")
        if executable:
            options["executable_path"] = executable
        else:
            options["channel"] = "chrome"
        try:
            self.context = self.driver.chromium.launch_persistent_context(str(profile), **options)
        except Exception:
            self.close()
            raise
        self.context.set_default_timeout(5000)
        self.context.set_default_navigation_timeout(15000)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        def closed(*_):
            self.user_closed = True
        self.context.on('close', closed)
        self.page.on('close', closed)

    def close(self):
        try:
            if self.context:
                self.context.close()
        finally:
            if self.driver:
                self.driver.stop()
            self.context = self.driver = self.page = None

    def inspect(self):
        page = self.page
        controls = page.locator("button,a[href],input:not([type=password]),textarea,select").evaluate_all("els => els.filter(e => e.getClientRects().length && !e.disabled).slice(0,120).map(e => ({name:(e.getAttribute('aria-label')||e.getAttribute('title')||e.innerText||e.getAttribute('placeholder')||'').trim().slice(0,160),role:e.tagName==='A'?'Hyperlink':['INPUT','TEXTAREA'].includes(e.tagName)?'Edit':'Button',href:e.tagName==='A'?e.href:undefined}))")
        player = page.locator('video').first.evaluate("v => ({paused:v.paused,ready:v.readyState,ad:!!document.querySelector('.ad-showing')})") if page.locator('video').count() else None
        return {"url": page.url, "title": page.title(), "controls": controls, "owned": True, "player": player}

    def search(self, query):
        page = self.page
        destination = music_search_url(query, "youtube")
        if urlsplit(page.url).hostname in {"www.youtube.com", "youtube.com"}:
            field = page.locator("input[name=search_query]:visible")
            if field.count() == 1:
                field.fill(query)
                if field.input_value() != query:
                    raise ValueError("Browser search text was not verified; it was not submitted.")
                field.press("Enter")
            else:
                page.goto(destination, wait_until="domcontentloaded")
        else:
            page.goto(destination, wait_until="domcontentloaded")
        page.wait_for_url(lambda url: parsed(url).path == "/results" and parse_qs(parsed(url).query).get("search_query") == [query], timeout=8000)
        page.locator("ytd-video-renderer a#video-title").first.wait_for(state="visible", timeout=10000)
        return {**self.inspect(), "verified": True, "message": "YouTube search query and visible results verified."}

    def select_video(self, query, position=None):
        page = self.page
        if urlsplit(page.url).hostname not in {"youtube.com", "www.youtube.com"} or urlsplit(page.url).path != "/results":
            raise ValueError("Select a video only from fresh YouTube search results.")
        links = page.locator("ytd-video-renderer a#video-title")
        rows = []
        for i in range(min(30, links.count())):
            link = links.nth(i)
            if not link.is_visible():
                continue
            href = link.get_attribute("href") or ""
            if href.startswith("/watch?") and parse_qs(urlsplit(href).query).get("v"):
                rows.append((link, link.inner_text(), parse_qs(urlsplit(href).query)["v"][0]))
        if position:
            if not 1 <= int(position) <= len(rows):
                raise ValueError("The requested video position is not visible.")
            chosen = rows[int(position)-1]
        else:
            def tokens_for(text):
                return set(label_key(text.replace("'", "").replace("’", "")).split())
            tokens = tokens_for(query)
            matches = [(len(tokens & tokens_for(title)) / max(1, len(tokens)), i, row)
                       for i, row in enumerate(rows) for _, title, _ in [row]]
            matches.sort(key=lambda row: (-row[0], row[1]))
            if not matches or matches[0][0] < .85:
                raise ValueError("No visible video title matches the requested media; refine the title.")
            chosen = matches[0][2]
        link, title, video_id = chosen
        element = link.element_handle()  # Bound live element, never a stored index.
        if element is None:
            raise ValueError("The selected video disappeared before action.")
        cursor_click(element,page,timeout=5000)
        page.wait_for_url(lambda url: parse_qs(parsed(url).query).get("v") == [video_id], timeout=10000)
        page.wait_for_function("() => {const v=document.querySelector('video');return v && !v.paused && v.readyState>=2 && !document.querySelector('.ad-showing')}", timeout=12000)
        return {**self.inspect(), "verified": True, "message": "Selected video identity and active playback verified: " + title[:160]}

    def play_video(self, video_id):
        """Open one exact video and verify real playback; skippable ads are skipped once each."""
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError("A YouTube video ID is required.")
        page = self.page
        page.goto("https://www.youtube.com/watch?v=" + video_id, wait_until="domcontentloaded")
        page.wait_for_url(lambda url: parse_qs(parsed(url).query).get("v") == [video_id], timeout=10000)
        page.locator("video").first.wait_for(state="attached", timeout=15000)
        deadline, skipped, nudged, state = time.monotonic() + 35, False, False, None
        started = time.monotonic()
        while time.monotonic() < deadline:
            state = page.evaluate("""() => {const v=document.querySelector('video');
                return v ? {playing: !v.paused && v.readyState >= 2, ad: !!document.querySelector('.ad-showing'),
                            position: v.currentTime, duration: v.duration, paused: v.paused} : null}""")
            if state and state["playing"] and not state["ad"]:
                break
            if state and state["ad"]:
                skip = page.locator(".ytp-skip-ad-button:visible, .ytp-ad-skip-button-modern:visible, .ytp-ad-skip-button:visible")
                if skip.count():
                    cursor_click(skip.first, page)
                    skipped = True
            elif state and state["paused"] and not nudged and time.monotonic() - started > 3:
                # Autoplay can be held back by the page; one play request is the user's intent.
                page.locator("video").first.evaluate("async v => { try { await v.play() } catch (e) {} }")
                nudged = True
            time.sleep(.4)
        else:
            raise ValueError("The video opened but playback did not start" +
                             (" (an unskippable ad is still playing)" if state and state.get("ad") else "") + "; nothing was replayed.")
        title = page.title().removesuffix(" - YouTube")
        return {**self.inspect(), "verified": True, "video_id": video_id, "state": state, "ad_skipped": skipped,
                "message": "Playing " + title[:160] + " (video identity and playback verified)."}

    def control(self, action):
        page = self.page
        if urlsplit(page.url).hostname not in {"youtube.com", "www.youtube.com"}:
            raise ValueError("YouTube player controls require the owned YouTube page.")
        video = page.locator("video").first
        video.wait_for(state="attached")
        before = video.evaluate("v => ({position:v.currentTime,duration:v.duration,volume:v.volume,speed:v.playbackRate})")
        expected = {}
        if action in {"play", "pause", "mute", "unmute", "restart"}:
            commands = {"play": "await v.play()", "pause": "v.pause()", "mute": "v.muted=true", "unmute": "v.muted=false", "restart": "v.currentTime=0"}
            video.evaluate("async v => {" + commands[action] + ";}")
            if action == "restart":
                expected["position"] = 0
        elif re.fullmatch(r"seek_-?\d{1,3}", action):
            expected["position"] = max(0, min(before["duration"], before["position"] + int(action[5:])))
            video.evaluate("(v, seconds) => v.currentTime=Math.max(0,Math.min(v.duration,v.currentTime+seconds))", int(action[5:]))
        elif re.fullmatch(r"(?:position|volume)_\d{1,3}", action):
            value = int(action.split("_")[1])
            if not 0 <= value <= 100:
                raise ValueError("Media percentage must be between 0 and 100.")
            expected["volume" if action.startswith("volume_") else "position"] = value / 100 if action.startswith("volume_") else before["duration"] * value / 100
            video.evaluate("(v,p) => " + ("v.volume=p/100" if action.startswith("volume_") else "v.currentTime=v.duration*p/100"), value)
        elif action in {"volume_up", "volume_down", "speed_up", "speed_down"}:
            prop = "volume" if action.startswith("volume") else "playbackRate"
            old = video.evaluate("v => v." + prop)
            amount = (.05 if prop == "volume" else .25) * (1 if action.endswith("up") else -1)
            target = max(0 if prop == "volume" else .25, min(1 if prop == "volume" else 2, old + amount))
            expected["volume" if prop == "volume" else "speed"] = target
            video.evaluate("(v,p) => v." + prop + "=p", target)
        elif action in {"fullscreen", "exit_fullscreen", "theater", "default_view", "miniplayer"}:
            reveal_controls(page)
            if action in {"fullscreen", "exit_fullscreen"}:
                desired = action == "fullscreen"
                if bool(page.evaluate("!!document.fullscreenElement")) != desired:
                    cursor_click(page.locator(".ytp-fullscreen-button:visible"),page)
                page.wait_for_function("p => !!document.fullscreenElement === p", arg=desired)
            elif action in {"theater", "default_view"}:
                desired = action == "theater"
                if (page.locator("ytd-watch-flexy").get_attribute("theater") is not None) != desired:
                    cursor_click(page.locator(".ytp-size-button:visible"),page)
                page.wait_for_function("p => document.querySelector('ytd-watch-flexy')?.hasAttribute('theater') === p", arg=desired)
            else:
                cursor_click(page.locator(".ytp-miniplayer-button:visible"),page)
                page.locator("ytd-miniplayer[active]").wait_for(state="visible")
        elif action in {"next", "previous"}:
            old, old_title = page.url, page.title()
            reveal_controls(page)
            button = page.locator(".ytp-next-button:visible" if action == "next" else ".ytp-prev-button:visible")
            if button.count():
                cursor_click(button.first, page)
            elif action == "next":
                page.keyboard.press("Shift+N")  # YouTube's own "next video" shortcut.
            else:
                # Outside a playlist YouTube's "previous" is the previous watched video.
                page.go_back(wait_until="domcontentloaded")
                if "/watch" not in page.url:
                    page.go_forward(wait_until="domcontentloaded")
                    raise ValueError("There is no previous video in this session.")
            page.wait_for_url(lambda url: parsed(url).geturl() != old, timeout=10000)
            # YouTube swaps videos in place; wait for the new title and metadata before reading state.
            page.wait_for_function("t => document.title && document.title !== t", arg=old_title, timeout=10000)
            page.wait_for_function("() => { const v = document.querySelector('video'); return v && v.readyState >= 1 }",
                                   timeout=10000)
            video = page.locator("video").first
        elif action in {"next_frame", "previous_frame"}:
            if not video.evaluate("v => v.paused"):
                raise ValueError("Frame stepping requires a paused video.")
            video.press("." if action == "next_frame" else ",")
        elif action in {"captions", "captions_on", "captions_off"}:
            reveal_controls(page)
            button = page.locator(".ytp-subtitles-button:visible")
            if button.count() != 1:
                raise ValueError("No unique captions control is available.")
            old = button.get_attribute("aria-pressed") == "true"
            if action == "captions" or old != (action == "captions_on"):
                cursor_click(button,page)
            new = button.get_attribute("aria-pressed") == "true"
            if new != ((not old) if action == "captions" else action == "captions_on"):
                raise ValueError("Captions change was sent but not verified.")
        elif action != "status":
            raise ValueError("Unsupported owned-browser media control.")
        current = video.evaluate("v => ({paused:v.paused,muted:v.muted,volume:v.volume,position:v.currentTime,duration:v.duration,ready:v.readyState,speed:v.playbackRate})")
        desired = {"play": current["paused"] is False, "pause": current["paused"] is True,
                   "mute": current["muted"] is True, "unmute": current["muted"] is False}
        if action in desired and not desired[action]:
            raise ValueError("Player action was sent but its state did not match.")
        for key, value in expected.items():
            if value is None or current[key] is None or abs(current[key] - value) > (2 if key == "position" else .01):
                raise ValueError("Player change was sent but its requested value was not verified.")
        if action in {"next_frame", "previous_frame"} and current["position"] == before["position"]:
            raise ValueError("Frame action was sent but position change was not observed.")
        title = page.title()
        if isinstance(title, str):  # Shown on the island media card.
            current["title"] = re.sub(r"^\(\d+\) |\s*-\s*YouTube$", "", title)[:300]
        return {"verified": True, "state": current, "message": player_message(action, current)}

    def perform(self, request):
        operation = request["operation"]
        if operation == 'windows_commands':
            if self.page is None or self.user_closed or self.page.is_closed():
                raise ValueError('Open and inspect the Jarvis browser first; closed pages are not restarted.')
            from .windows_command_browser import perform as windows_perform
            return windows_perform(request,self.page)
        if operation == "reset" and self.page is not None and not self.page.is_closed():
            self.page.bring_to_front()
            return self.inspect()
        if (request.get("new_task") and operation in {"navigate", "search", "play_video"} and self.page is not None
                and (self.user_closed or self.page.is_closed()
                     or self.context and self.context.browser and not self.context.browser.is_connected())):
            self.close()
            self.user_closed = False
        if operation == "reset":
            self.close()
            self.user_closed = False
        self.open(request.get("settings", {}))
        if request.get("new_task") and operation in {"navigate", "search"}:
            self.page.bring_to_front()
        if operation in {"reset", "inspect"}:
            return self.inspect()
        if operation=='read_text':
            text=self.page.locator('body').inner_text(timeout=5000)
            return {'url':self.page.url,'title':self.page.title(),'text':text[:12000],'truncated':len(text)>12000,'owned':True,'untrusted':True}
        if operation == "navigate":
            self.page.goto(url_for(request["value"]), wait_until="domcontentloaded")
            return {**self.inspect(), "message": "Opened requested website in Jarvis browser."}
        if operation == "search":
            return self.search(request["value"])
        if operation == "play_video":
            self.page.bring_to_front()
            return self.play_video(request.get("video_id"))
        if operation == "select_video":
            return self.select_video(request["value"], request.get("position"))
        if operation == "control":
            return self.control(request["value"])
        if operation in {"click", "fill"}:
            if request.get("url") != self.page.url:
                raise ValueError("Browser page changed before action; inspect fresh state.")
            label = request["value"]
            if UNSAFE_INFERRED.search(label):
                raise ValueError("This browser action needs the explicit account/action approval path.")
            locator = self.page.get_by_role("button", name=label, exact=True).or_(self.page.get_by_role("link", name=label, exact=True)) if operation == "click" else self.page.get_by_role("textbox", name=label, exact=True).or_(self.page.get_by_role("searchbox", name=label, exact=True))
            if locator.count() != 1:
                raise ValueError("The named browser target is not unique; specify its context.")
            if operation == "click":
                cursor_click(locator,self.page)
                return {**self.inspect(), "verified": False, "message": "Clicked exact visible browser target once; goal needs fresh verification."}
            if locator.evaluate("e => e.type === 'password' || /password/i.test(e.getAttribute('autocomplete')||'')"):
                raise ValueError("Password fields are excluded from generic browser filling.")
            locator.fill(request["content"])
            if locator.input_value() != request["content"]:
                raise ValueError("Browser field write was not verified.")
            return {"verified": True, "message": "Exact browser field value verified."}
        raise ValueError("Unsupported browser operation.")


def main():
    session = Session()
    try:
        for line in sys.stdin:
            ident = None
            try:
                envelope = json.loads(line)
                ident, request = envelope["id"], envelope["request"]
                if request.get("operation") == "shutdown":
                    break
                result = {"id": ident, "result": session.perform(request)}
            except Exception as exc:
                result = {"id": ident, "error": str(exc)[:1000]}
            print(json.dumps(result), flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
