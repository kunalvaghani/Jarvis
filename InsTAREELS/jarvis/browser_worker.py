"""Warm Playwright worker owning a separate Chrome profile and window."""
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit, parse_qs

from .browser import music_search_url, url_for
from .ui_controls import label_key, UNSAFE_INFERRED


def parsed(url):
    return url if hasattr(url, "scheme") and hasattr(url, "path") else urlsplit(str(url))


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
        element.click(timeout=5000)
        page.wait_for_url(lambda url: parse_qs(parsed(url).query).get("v") == [video_id], timeout=10000)
        page.wait_for_function("() => {const v=document.querySelector('video');return v && !v.paused && v.readyState>=2 && !document.querySelector('.ad-showing')}", timeout=12000)
        return {**self.inspect(), "verified": True, "message": "Selected video identity and active playback verified: " + title[:160]}

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
            if action in {"fullscreen", "exit_fullscreen"}:
                desired = action == "fullscreen"
                if bool(page.evaluate("!!document.fullscreenElement")) != desired:
                    page.locator(".ytp-fullscreen-button:visible").click()
                page.wait_for_function("p => !!document.fullscreenElement === p", arg=desired)
            elif action in {"theater", "default_view"}:
                desired = action == "theater"
                if (page.locator("ytd-watch-flexy").get_attribute("theater") is not None) != desired:
                    page.locator(".ytp-size-button:visible").click()
                page.wait_for_function("p => document.querySelector('ytd-watch-flexy')?.hasAttribute('theater') === p", arg=desired)
            else:
                page.locator(".ytp-miniplayer-button:visible").click()
                page.locator("ytd-miniplayer[active]").wait_for(state="visible")
        elif action in {"next", "previous"}:
            old = page.url
            page.locator(".ytp-next-button:visible" if action == "next" else ".ytp-prev-button:visible").click()
            page.wait_for_url(lambda url: parsed(url).geturl() != old)
        elif action in {"next_frame", "previous_frame"}:
            if not video.evaluate("v => v.paused"):
                raise ValueError("Frame stepping requires a paused video.")
            video.press("." if action == "next_frame" else ",")
        elif action in {"captions", "captions_on", "captions_off"}:
            button = page.locator(".ytp-subtitles-button:visible")
            if button.count() != 1:
                raise ValueError("No unique captions control is available.")
            old = button.get_attribute("aria-pressed") == "true"
            if action == "captions" or old != (action == "captions_on"):
                button.click()
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
        return {"verified": True, "state": current, "message": "YouTube player state observed: " + json.dumps(current)}

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
        if (request.get("new_task") and operation in {"navigate", "search"} and self.page is not None
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
        if operation == "navigate":
            self.page.goto(url_for(request["value"]), wait_until="domcontentloaded")
            return {**self.inspect(), "message": "Opened requested website in Jarvis browser."}
        if operation == "search":
            return self.search(request["value"])
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
                locator.click()
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
