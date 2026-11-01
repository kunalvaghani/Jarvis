"""Animated single-page web apps built, tested in a real browser and repaired (flag control.api_routes, off).

User request 2026-11-01: VS Code tasks should be different apps and websites each time, using an animated UI
library, and what Jarvis builds must work without errors. This route:

1. asks the coding model for ONE self-contained ``index.html`` (inline CSS and JS) that animates with GSAP or
   anime.js loaded from cdnjs at a pinned version (no install on this PC; the user chose the CDN);
2. loads it in headless Chrome from a local server and checks, independently of the model:
   - no console errors and no uncaught page errors;
   - the animation library loaded and the page really called it;
   - every visible button changes the page when clicked, and typing into a text box then pressing Enter
     changes it too (interactive parts do something; nothing is dead);
3. sends every problem found back to the model to fix the file, up to three repair rounds;
4. writes the file through the normal create command only when every check passes, then opens the folder in
   a NEW VS Code window.
"""
from __future__ import annotations

import functools
import http.server
import json
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from .small_program import source

LIBRARIES = {
    'gsap': ('https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js', 'gsap',
             ('to', 'from', 'fromTo', 'timeline', 'set')),
    'anime': ('https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.2/anime.min.js', 'anime', ()),
}
WEB = re.compile(r'\b(?:web ?app|website|web ?site|web ?page|landing page|single[- ]page|page|dashboard|portfolio|'
                 r'(?:timer|todo|to-do|quiz|game|calculator|tracker|gallery|counter|clock|weather|notes?) app)\b', re.I)
NOT_WEB = re.compile(r'\b(?:python|\.py|flask|django|node|express|react|vue|svelte|next\.?js|backend|server|database|'
                     r'api|login|sign ?in|payment)\b', re.I)
FOLDER = re.compile(r'\b(?:new\s+)?(?:project\s+)?folder\s+(?:called|named)\s+["\']?([A-Za-z0-9][\w.-]{0,60})', re.I)
ROUNDS = 3
INSTRUMENT = '''
(() => {
  window.__calls = 0;
  const wrap = (lib, names) => {
    if (!lib) return lib;
    // Every method counts (anime.timeline(), anime.set(), gsap.utils...), not only a few names: a live gate
    // (2026-11-02) failed a working anime.js page four times because only anime(...) itself was counted.
    const methods = (target) => {
      for (const n of Object.keys(target)) {
        if (typeof target[n] === 'function') { const f = target[n].bind(target);
          target[n] = (...a) => { window.__calls++; return f(...a); }; }
      }
    };
    if (typeof lib === 'function') {
      const fn = function(...a) { window.__calls++; return lib.apply(this, a); };
      Object.assign(fn, lib);
      methods(fn);
      return fn;
    }
    methods(lib);
    return lib;
  };
  for (const [name, names] of [['gsap', ['to', 'from', 'fromTo', 'timeline', 'set']], ['anime', []]]) {
    let value;
    Object.defineProperty(window, name, {configurable: true, get: () => value, set: v => { value = wrap(v, names); }});
  }
  window.__changes = 0;
  new MutationObserver(m => { window.__changes += m.length; }).observe(document, {subtree: true, childList: true,
    attributes: true, characterData: true});
})();
'''


def matches(goal: str) -> Optional[Tuple[str, str]]:
    """(library, folder name) for a request for one animated web page or browser app; None otherwise."""
    files = re.sub(r'\b(?:anime|gsap|three|motion)\.js\b', '', goal, flags=re.I)  # Library names, not files.
    if not WEB.search(goal) or NOT_WEB.search(files) or re.search(r'\.(?:py|js|ts|css)\b', files, re.I):
        return None
    folder = FOLDER.search(goal)
    if not folder:
        return None
    library = 'anime' if re.search(r'\banime(?:\.js|js)?\b', goal, re.I) else 'gsap'
    return library, folder.group(1).rstrip('.,')


def describe(goal: str) -> str:
    text = re.sub(r'^\s*open (?:vs ?code|visual studio code)\s*(?:,|and)\s*', '', goal, flags=re.I)
    text = re.sub(r'\s+in (?:a )?new (?:project )?folder (?:called|named) \S+ in (?:my |the )?[\w -]+? folder\b', '', text,
                  flags=re.I)
    return ' '.join(re.sub(r',?\s*and save it\.?\s*$', '', text, flags=re.I).split())


def prompt(request: str, library: str) -> str:
    url, name, _ = LIBRARIES[library]
    return (f'Write ONE complete, self-contained index.html for this request: {request}\n'
            f'Use inline <style> and <script> only. Load the animation library exactly with '
            f'<script src="{url}"></script> and use `{name}` for real, visible animations (on load and on user '
            'actions). No other external files, images, fonts or libraries. Give every button and input an id. '
            'Every button must visibly change the page when clicked; a text box must do something on Enter. '
            'Responsive layout, modern look. The page must run without any console error. '
            'Return only the HTML.')


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass


def check(html: str, library: str, timeout_ms: int = 15000) -> List[str]:
    """Problems found by loading and using the page in headless Chrome; [] when it works."""
    from playwright.sync_api import sync_playwright
    problems: List[str] = []
    url, name, _ = LIBRARIES[library]
    if url not in html:
        problems.append(f'the page does not load {name} from {url}')
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / 'index.html').write_text(html, encoding='utf-8')
        (Path(folder) / 'favicon.ico').write_bytes(b'')  # The browser asks for it; a 404 there is not the page's error.
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(_Quiet, directory=folder))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as driver:
                browser = driver.chromium.launch(channel='chrome', headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1280, 'height': 800})
                    errors: List[str] = []
                    page.on('console', lambda m: errors.append('console: ' + m.text) if m.type == 'error' else None)
                    page.on('pageerror', lambda e: errors.append('error: ' + str(e)))
                    page.add_init_script(INSTRUMENT)
                    page.goto(f'http://127.0.0.1:{server.server_address[1]}/index.html', timeout=timeout_ms,
                              wait_until='load')
                    page.wait_for_timeout(1500)
                    loaded = page.evaluate(f'() => typeof window.{name} !== "undefined"')
                    if not loaded:
                        problems.append(f'{name} did not load')
                    problems += dead_controls(page)
                    # Counted after the page was used: "new items animate in" only animates on adding an item
                    # (a live gate failed a working to-do app four times when this was counted at load, 2026-11-02).
                    if loaded and page.evaluate('() => window.__calls') == 0:
                        problems.append(f'{name} is loaded but never used for an animation')
                    problems += [e[:300] for e in dict.fromkeys(errors)]
                finally:
                    browser.close()
        finally:
            server.shutdown()
    return problems


def dead_controls(page: Any) -> List[str]:
    problems: List[str] = []
    buttons = page.locator('button:visible, [role=button]:visible, input[type=button]:visible, input[type=submit]:visible')
    if page.locator('button, [role=button], input[type=button], input[type=submit]').count() == 0:
        problems.append('the page has no buttons to use')
    for box in page.locator('input[type=text]:visible, input:not([type]):visible, textarea:visible').all()[:3]:
        before = page.evaluate('() => window.__changes')
        box.fill('Jarvis check')
        box.press('Enter')
        page.wait_for_timeout(400)
        if page.evaluate('() => window.__changes') == before:
            problems.append(f'typing in {box.get_attribute("id") or "a text box"} and pressing Enter does nothing')
    for index in range(min(buttons.count(), 8)):
        button = buttons.nth(index)
        label = (button.get_attribute('id') or button.inner_text() or 'a button').strip()[:40]
        before = page.evaluate('() => window.__changes')
        try:
            button.click(timeout=3000)
        except Exception as error:
            problems.append(f'button {label} cannot be clicked: {type(error).__name__}')
            continue
        page.wait_for_timeout(600)
        if page.evaluate('() => window.__changes') == before:
            problems.append(f'button {label} does nothing when clicked')
    return problems


def build(request: Callable[..., Any], goal: str, library: str, cancelled: Callable[[], bool],
          report: Callable[[str, str], None], checker: Callable[[str, str], List[str]] = check) -> Tuple[Optional[str], List[str]]:
    """(working index.html, problems of the last round) after up to ROUNDS checked repairs."""
    asked = describe(goal)
    html = source(request('tool_text', cancelled, tool='write_code', context='', goal=prompt(asked, library),
                          long_output=True))
    history: List[str] = []
    for round_number in range(ROUNDS + 1):
        if cancelled():
            raise ValueError('Cancelled before the page was written.')
        problems = checker(html, library)
        report('tool', f'web app check round {round_number + 1}: ' + ('passed' if not problems else
                                                                      f'{len(problems)} problem(s)'))
        if not problems:
            return html, history
        history = problems
        if round_number == ROUNDS:
            break
        html = source(request('tool_text', cancelled, tool='improve_code', context=html, goal=(
            prompt(asked, library) + '\nThe current index.html (in context) was tested in a real browser and has '
            'these problems; fix every one and return the complete corrected file:\n- ' + '\n- '.join(problems)),
            long_output=True))
    return None, history


def run_web_app(actions: Any, project: Path, goal: str, library: str, cancelled: Callable[[], bool]) -> str:
    target = project / 'index.html'
    if target.exists():
        raise ValueError(f'{target} already exists; Jarvis does not overwrite it without asking. Nothing was written.')
    html, problems = build(actions.brain.client.request, goal, library, cancelled, actions.report)
    if html is None:
        raise ValueError('The web page was not saved: it still had problems after ' + str(ROUNDS) + ' repair rounds ('
                         + '; '.join(problems[:5]) + ').')
    from .commands import Command
    actions.execute(Command('create_in_folder', 'index.html', json.dumps({'folder': str(project), 'content': html})),
                    cancelled)
    if not target.is_file():
        raise ValueError(f'{target} was not created.')
    return (f'Created {target}: it loads {library} from cdnjs, animates, and every button and text box works in a '
            'real browser with no console errors.')
