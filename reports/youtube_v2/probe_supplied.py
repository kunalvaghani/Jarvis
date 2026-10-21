"""Reproducible pre-integration public browser probe; no account operations."""
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
SOURCE = Path(r'D:\Phython Project\Connectors\jarvis_youtube_connector')
sys.path.insert(0, str(SOURCE))
from youtube_connector.youtube_v2 import YouTubeConnector
from playwright.async_api import async_playwright


async def main():
    rows = []
    async def attempt(name, fn):
        started = time.perf_counter()
        try:
            result = await fn()
            rows.append(dict(command=name, result=result, elapsed_ms=round((time.perf_counter()-started)*1000, 2)))
            return result
        except Exception as exc:
            rows.append(dict(command=name, error_type=type(exc).__name__, error=str(exc)[:400], elapsed_ms=round((time.perf_counter()-started)*1000, 2)))

    async with async_playwright() as pw:
        chrome = Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Google/Chrome/Application/chrome.exe'
        context = await pw.chromium.launch_persistent_context(
            str(ROOT.parents[1] / 'app/.jarvis-runtime/youtube-v2-gate-a-profile'),
            executable_path=str(chrome), headless=False, accept_downloads=False,
            args=['--no-first-run'], viewport={'width':1280,'height':800})
        page = context.pages[0] if context.pages else await context.new_page()
        controller = YouTubeConnector(page=page, api_key='')
        try:
            await attempt('play_video exact public ID', lambda: controller.play_video('aqz-KE-bpKQ'))
            await attempt('get_status', controller.get_status)
            await attempt('pause', controller.pause)
            await attempt('seek 12', lambda: controller.seek(12))
            await attempt('skip_forward 10', lambda: controller.skip_forward(10))
            await attempt('skip_back 5', lambda: controller.skip_back(5))
            await attempt('set_volume 35', lambda: controller.set_volume(35))
            await attempt('mute', controller.mute)
            await attempt('unmute', controller.unmute)
            await attempt('set_speed 1.25', lambda: controller.set_speed(1.25))
            await attempt('resume', controller.resume)
            await attempt('media_status', controller.media_status)
            if page.url.startswith('https://www.youtube.com/'):
                await page.screenshot(path=str(ROOT/'gate-a-public-page.png'))
                diagnostic = await page.locator('body').inner_text()
                (ROOT/'gate-a-public-page.txt').write_text(diagnostic[:12000], encoding='utf-8')
            await attempt('pause cleanup', controller.pause)
        finally:
            await controller.close()
            await context.close()
    (ROOT/'supplied-injected-live.json').write_text(json.dumps(dict(
        python=sys.version.split()[0], playwright=importlib.metadata.version('playwright'),
        results=rows), indent=2), encoding='utf-8')

if __name__ == '__main__':
    asyncio.run(main())
