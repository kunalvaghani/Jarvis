"""Route 2: Playwright + CDP browser executor with tab-scoped accessibility refs (ADR 0003).

Member names follow the browser toolset (doc section 2.2) so a model-facing adapter can map 1:1.
Reads come from Chrome's accessibility tree (rendered content only). Every request passes the URL
policy; document redirects are followed hop by hop so a public page cannot bounce the browser to
a local or private address. Clicks on refs are dispatched only after the target is visible,
stable, enabled, still the element that was read, and actually receives the pointer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlsplit

from ..coords import CoordinateError, Frame, Layout, Monitor, Point, Rect, Transform
from ..executor import Health, RouteExecutor
from ..policy import Policy, PolicyError
from ..refs import RefRegistry
from ..timing import StageTimer
from ..types import Action, ActionResult, ControlError, ErrorCategory, Expectation, Observation, Ref, Route

INTERACTIVE = frozenset({'button', 'link', 'textbox', 'searchbox', 'checkbox', 'radio', 'combobox', 'listbox',
                         'option', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'tab', 'switch', 'slider',
                         'spinbutton', 'treeitem', 'gridcell', 'columnheader', 'rowheader', 'textarea'})
SILENT = frozenset({'InlineTextBox', 'LineBreak', 'none', 'generic', 'LabelText', 'paragraph', 'Section',
                    'group', 'list', 'listitem', 'RootWebArea', 'Iframe', 'IframePresentational'})
MAX_TREE_CHARS = 50_000
KEY_NAMES = {'ctrl': 'Control', 'control': 'Control', 'cmd': 'Meta', 'super': 'Meta', 'win': 'Meta', 'meta': 'Meta',
             'alt': 'Alt', 'shift': 'Shift', 'enter': 'Enter', 'return': 'Enter', 'esc': 'Escape',
             'escape': 'Escape', 'tab': 'Tab', 'space': ' ', 'backspace': 'Backspace', 'delete': 'Delete',
             'up': 'ArrowUp', 'down': 'ArrowDown', 'left': 'ArrowLeft', 'right': 'ArrowRight',
             'pageup': 'PageUp', 'pagedown': 'PageDown', 'home': 'Home', 'end': 'End'}
READ_MEMBERS = frozenset({'read_page', 'find', 'get_page_text', 'screenshot', 'zoom', 'list_tabs', 'wait'})
POINTER = {'left_click': ('left', 1), 'right_click': ('right', 1), 'middle_click': ('middle', 1),
           'double_click': ('left', 2), 'triple_click': ('left', 3)}

HIT_TEST = """function() {
  const r = this.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  let hit = this.ownerDocument.elementFromPoint(x, y);
  while (hit && hit.shadowRoot) { const inner = hit.shadowRoot.elementFromPoint(x, y); if (!inner || inner === hit) break; hit = inner; }
  let top = true; try { top = window === window.top; } catch (e) { top = false; }
  return {ok: !!hit && (hit === this || this.contains(hit) || (hit.getRootNode && hit.getRootNode().host === this)), top};
}"""
FORM_INPUT = """function(v) {
  const t = this.tagName, fire = () => { this.dispatchEvent(new Event('input', {bubbles: true}));
                                         this.dispatchEvent(new Event('change', {bubbles: true})); };
  if (this.isContentEditable) { this.focus(); this.textContent = String(v); fire(); return this.textContent; }
  if (t === 'SELECT') {
    const o = [...this.options].find(o => o.value === String(v) || o.text.trim() === String(v));
    if (!o) throw new Error('NO_OPTION'); this.value = o.value; fire(); return o.text.trim(); }
  if (t === 'INPUT' && (this.type === 'checkbox' || this.type === 'radio')) {
    const want = v === true || v === 'true'; if (this.checked !== want) this.click(); return this.checked; }
  if (t === 'INPUT' && this.type === 'password') throw new Error('PASSWORD');
  if (t === 'INPUT' && this.type === 'file') throw new Error('FILE');
  if (t !== 'INPUT' && t !== 'TEXTAREA') throw new Error('NOT_A_FIELD');
  const proto = t === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  this.focus(); Object.getOwnPropertyDescriptor(proto, 'value').set.call(this, String(v)); fire(); return this.value;
}"""
READ_VALUE = """function() { if (this.tagName === 'SELECT') return this.options[this.selectedIndex]?.text.trim() ?? '';
  if (this.type === 'checkbox' || this.type === 'radio') return this.checked;
  return this.isContentEditable ? this.textContent : this.value; }"""


@dataclass
class _Tab:
    id: str
    page: Any
    session: Any
    oop: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)        # frame key -> (session, frame)
    seen: Dict[Tuple[str, int], Tuple[str, str]] = field(default_factory=dict)  # ref key -> (role, name)
    viewport: Tuple[int, int] = (1280, 800)
    read_at: float = 0.0


@dataclass(frozen=True)
class _Node:
    key: Tuple[str, int]
    role: str
    name: str
    props: Mapping[str, Any]
    children: Tuple[str, ...]
    ignored: bool


class BrowserExecutor(RouteExecutor):
    route = Route.BROWSER

    def __init__(self, profile_dir: Path, policy: Policy, download_dir: Path, headless: bool = False,
                 channel: str = 'chrome', viewport: Tuple[int, int] = (1280, 800),
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.profile_dir, self.policy, self.download_dir = Path(profile_dir), policy, Path(download_dir)
        self.headless, self.channel, self.viewport, self.clock = headless, channel, viewport, clock
        self.refs = RefRegistry(Route.BROWSER)
        self.tabs: Dict[str, _Tab] = {}
        self.active = ''
        self.blocked: List[str] = []
        self.changes: List[Dict[str, Any]] = []
        self.dialogs: List[str] = []
        self._driver: Any = None
        self.context: Any = None
        self._next_tab = 0
        self._lock = threading.RLock()
        self._cancelled = threading.Event()

    # Lifecycle ------------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self.context is not None:
                return
            from playwright.sync_api import sync_playwright
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            self.download_dir.mkdir(parents=True, exist_ok=True)
            self._driver = sync_playwright().start()
            try:
                self.context = self._driver.chromium.launch_persistent_context(
                    str(self.profile_dir), channel=self.channel, headless=self.headless, accept_downloads=True,
                    viewport={'width': self.viewport[0], 'height': self.viewport[1]},
                    args=['--force-renderer-accessibility', '--no-first-run', '--no-default-browser-check'])
            except Exception:
                self._driver.stop()
                self._driver = None
                raise
            self.context.set_default_timeout(10_000)
            self.context.route('**/*', self._guard)
            self.context.on('page', self._adopt)
            for page in self.context.pages or [self.context.new_page()]:
                if not any(t.page is page for t in self.tabs.values()):
                    self._adopt(page)

    def close(self) -> None:
        with self._lock:
            try:
                if self.context is not None:
                    self.context.close()
            finally:
                if self._driver is not None:
                    self._driver.stop()
                self.context = self._driver = None
                for tab_id in list(self.tabs):
                    self.refs.drop(tab_id)
                self.tabs.clear()

    def cancel(self) -> None:
        self._cancelled.set()

    def health_check(self) -> Health:
        if self.context is None:
            return Health(False, 'browser not started')
        try:
            live = [t for t in self.tabs.values() if not t.page.is_closed()]
            return Health(bool(live), f'{len(live)} tab(s)', {'tabs': len(live), 'channel': self.channel})
        except Exception as exc:
            return Health(False, type(exc).__name__)

    # Network policy ---------------------------------------------------------
    def _guard(self, route: Any) -> None:
        request = route.request
        url = request.url
        scheme = urlsplit(url).scheme.lower()
        if scheme in ('data', 'blob') and not request.is_navigation_request():
            route.continue_()
            return
        try:
            self.policy.check_url(url)
        except PolicyError:
            self.blocked.append(url)
            route.abort('blockedbyclient')
            return
        if not request.is_navigation_request():
            route.continue_()
            return
        # Follow document redirects ourselves so every hop meets the policy before the browser does.
        try:
            response = route.fetch(max_redirects=0)
        except Exception:
            route.abort('failed')
            return
        location = response.headers.get('location')
        if 300 <= response.status < 400 and location:
            target = urljoin(url, location)
            try:
                self.policy.check_url(target)
            except PolicyError:
                self.blocked.append(target)
                route.abort('blockedbyclient')
                return
        route.fulfill(response=response)

    # Tabs -------------------------------------------------------------------
    def _adopt(self, page: Any) -> None:
        self._next_tab += 1
        tab = _Tab(f'tab-{self._next_tab}', page, self.context.new_cdp_session(page), viewport=self.viewport)
        self.tabs[tab.id] = tab
        if not self.active:
            self.active = tab.id
        else:
            self.changes.append({'type': 'tab_opened', 'tab_id': tab.id})

        def navigated(frame: Any) -> None:
            if frame == page.main_frame:
                self.refs.invalidate(tab.id)
                tab.seen.clear()
                tab.oop.clear()

        def closed(_page: Any) -> None:
            self.refs.drop(tab.id)
            self.tabs.pop(tab.id, None)
            if self.active == tab.id:
                self.active = next(iter(self.tabs), '')

        def dialog(d: Any) -> None:
            self.dialogs.append(d.type)
            d.dismiss()  # Never accept: an accepted confirm() can be consequential.

        def download(d: Any) -> None:
            name = re.sub(r'[^\w.\- ]', '_', d.suggested_filename)[:120] or 'download'
            try:
                target = self.policy.confine(self.download_dir / name, (self.download_dir,))
                d.save_as(str(target))
                self.changes.append({'type': 'download_completed', 'tab_id': tab.id, 'path': str(target)})
            except Exception as exc:
                self.changes.append({'type': 'download_failed', 'tab_id': tab.id, 'reason': type(exc).__name__})

        page.on('framenavigated', navigated)
        page.on('close', closed)
        page.on('dialog', dialog)
        page.on('download', download)

    def _tab(self, tab_id: Optional[str] = None) -> _Tab:
        if self.context is None:
            self.start()
        tab = self.tabs.get(tab_id or self.active)
        if tab is None or tab.page.is_closed():
            raise ControlError(f'Tab {tab_id or self.active!r} is not open; list tabs and choose one.',
                               ErrorCategory.TARGET_NOT_FOUND)
        return tab

    def browser_state(self) -> Dict[str, Any]:
        tabs = []
        for tab in self.tabs.values():
            try:
                tabs.append({'tab_id': tab.id, 'title': tab.page.title()[:300], 'url': tab.page.url[:2000],
                             'active': tab.id == self.active})
            except Exception:
                continue
        state: Dict[str, Any] = {'tabs': tabs}
        if self.changes:
            state['state_changes'], self.changes = self.changes, []
        return state

    # Observation ----------------------------------------------------------
    def _sessions(self, tab: _Tab) -> Iterator[Tuple[str, Any, Optional[str]]]:
        """(frame key, session, frameId) for the main session's frames, then out-of-process frames."""
        tree = tab.session.send('Page.getFrameTree')['frameTree']
        stack = [tree]
        while stack:
            node = stack.pop()
            yield 'main', tab.session, node['frame']['id']
            stack.extend(node.get('childFrames', []))
        for frame in tab.page.frames[1:]:
            key = f'oop:{id(frame)}'
            if key not in tab.oop:
                try:
                    tab.oop[key] = (self.context.new_cdp_session(frame), frame)
                except Exception:
                    continue  # Same-process frame: already covered by the main session.
            yield key, tab.oop[key][0], None

    def _nodes(self, tab: _Tab) -> Tuple[Dict[str, _Node], List[str]]:
        nodes: Dict[str, _Node] = {}
        roots: List[str] = []
        for fkey, session, frame_id in self._sessions(tab):
            try:
                raw = session.send('Accessibility.getFullAXTree', {'frameId': frame_id} if frame_id else {})['nodes']
            except Exception:
                continue  # Frame belongs to another process or detached mid-read.
            prefix = f'{fkey}:{frame_id or ""}:'
            for row in raw:
                backend = row.get('backendDOMNodeId')
                props = {p['name']: p.get('value', {}).get('value') for p in row.get('properties', [])}
                if 'value' in row:
                    props['value'] = row['value'].get('value')
                nodes[prefix + row['nodeId']] = _Node(
                    (fkey, int(backend)) if backend is not None else (fkey, -1),
                    str(row.get('role', {}).get('value', '')), str(row.get('name', {}).get('value', '')).strip(),
                    props, tuple(prefix + c for c in row.get('childIds', [])), bool(row.get('ignored')))
            if raw:
                roots.append(prefix + raw[0]['nodeId'])
        return nodes, roots

    def _on_screen(self, tab: _Tab) -> Optional[set[int]]:
        """Backend ids of main-session nodes whose layout box intersects the viewport."""
        try:
            snap = tab.session.send('DOMSnapshot.captureSnapshot', {'computedStyles': []})
            metrics = tab.session.send('Page.getLayoutMetrics')['cssVisualViewport']
        except Exception:
            return None
        left, top = metrics['pageX'], metrics['pageY']
        right, bottom = left + metrics['clientWidth'], top + metrics['clientHeight']
        visible: set[int] = set()
        for index, doc in enumerate(snap['documents']):
            backend = doc['nodes']['backendNodeId']
            for node_index, (x, y, w, h) in zip(doc['layout']['nodeIndex'], doc['layout']['bounds']):
                if index > 0 or (w > 0 and h > 0 and x < right and x + w > left and y < bottom and y + h > top):
                    visible.add(backend[node_index])
        return visible

    def read_page(self, tab_id: Optional[str] = None, filter: str = '', depth: int = 15,
                  ref: Optional[str] = None) -> Observation:
        if filter not in ('', 'visible', 'interactive', 'all') or not 1 <= depth <= 60:
            raise ControlError('filter must be visible, interactive or all; depth 1-60.', ErrorCategory.INVALID_ARGUMENTS)
        with self._lock:
            tab = self._tab(tab_id)
            nodes, roots = self._nodes(tab)
            on_screen = self._on_screen(tab) if filter in ('', 'visible') else None
            if ref is not None:
                key = self.refs.resolve(self.refs.lookup(tab.id, ref))
                roots = [nid for nid, node in nodes.items() if node.key == key][:1]
                if not roots:
                    raise ControlError(f'{ref} is no longer in the page. Re-read the page.', ErrorCategory.STALE_REF)
            lines: List[str] = []
            refs: List[Ref] = []
            live: List[Tuple[str, int]] = []
            size = 0

            def visit(nid: str, level: int, indent: int) -> None:
                nonlocal size
                node = nodes.get(nid)
                if node is None or level > depth or size > MAX_TREE_CHARS:
                    return
                shown = indent
                if not node.ignored and node.key[1] >= 0:
                    live.append(node.key)
                    interactive = node.role in INTERACTIVE
                    keep = (filter == 'all' or (filter == 'interactive' and interactive)
                            or (filter in ('', 'visible') and (on_screen is None or node.key[0] != 'main'
                                                               or node.key[1] in on_screen)
                                and (interactive or (node.role not in SILENT and node.name))))
                    if keep and node.role not in ('InlineTextBox', 'LineBreak'):
                        state = ''.join(f' {k}' if v is True else f' {k}={v!r}' for k, v in sorted(node.props.items())
                                        if k in ('checked', 'disabled', 'expanded', 'selected', 'focused', 'required',
                                                 'value', 'invalid') and v not in (False, None, '', 'false'))
                        if node.role == 'StaticText':
                            line = f'{"  " * indent}text "{node.name[:300]}"'
                        else:
                            r = self.refs.assign(tab.id, node.key)
                            refs.append(r)
                            tab.seen[node.key] = (node.role, node.name)
                            line = f'{"  " * indent}{node.role} "{node.name[:200]}"{state} [{r.id}]'
                        lines.append(line)
                        size += len(line) + 1
                        shown = indent + 1
                for child in node.children:
                    visit(child, level + 1, shown)

            for root in roots:
                visit(root, 0, 0)
            if ref is None and filter == 'all':  # A full read knows exactly which nodes vanished.
                still = set(live)
                self.refs.retain(tab.id, still)
                for key in [k for k in tab.seen if k not in still]:
                    del tab.seen[key]
            text = '\n'.join(lines)
            if len(text) > MAX_TREE_CHARS:
                text = text[:MAX_TREE_CHARS] + '\n[truncated: scope the read with filter or ref]'
            tab.read_at = self.clock()
            transform = Transform(Frame.VIEWPORT, tab.id, 0, 0, 1, 1, tab.viewport[0], tab.viewport[1], tab.read_at)
            return Observation(Route.BROWSER, tab.id, text, tuple(refs), transform=transform,
                               state={'url': tab.page.url, 'title': tab.page.title()[:300]})

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        return self.read_page(scope, options.get('filter', ''), options.get('depth', 15), options.get('ref'))

    def page_text(self, tab_id: Optional[str] = None) -> str:
        tab = self._tab(tab_id)
        text = str(tab.page.evaluate('() => document.body ? document.body.innerText : ""'))
        return text[:MAX_TREE_CHARS]

    def find(self, query: str, tab_id: Optional[str] = None, limit: int = 20) -> List[Tuple[Ref, str, str]]:
        """Deterministic name/role matching over a fresh interactive read; no model call."""
        words = set(re.findall(r'\w+', query.lower()))
        if not words:
            raise ControlError('find needs a query.', ErrorCategory.INVALID_ARGUMENTS)
        observed = self.read_page(tab_id, 'all')
        tab = self._tab(tab_id)
        scored = []
        for ref in observed.refs:
            role, name = tab.seen.get(self._key(tab, ref), ('', ''))
            hay = set(re.findall(r'\w+', f'{role} {name}'.lower()))
            score = len(words & hay) / len(words) + (.5 if name.lower() == query.lower() else 0)
            if score > 0:
                scored.append((score, ref, role, name))
        scored.sort(key=lambda row: -row[0])
        return [(ref, role, name) for _, ref, role, name in scored[:limit]]

    # Probes for verification -------------------------------------------------
    def probe(self, what: str, **params: Any) -> Any:
        tab = self._tab(params.get('tab_id'))
        if what == 'url':
            return tab.page.url
        if what == 'title':
            return tab.page.title()
        if what == 'value':
            session, node = self._object(tab, self._key(tab, params['ref']))
            return session.send('Runtime.callFunctionOn', {'objectId': node, 'functionDeclaration': READ_VALUE,
                                                           'returnByValue': True})['result'].get('value')
        if what == 'text':
            return tab.page.evaluate('s => document.querySelector(s)?.textContent ?? null', params['selector'])
        if what == 'signature':
            return hash(self.read_page(tab.id, 'all').text)
        if what == 'state':
            return self.browser_state().get(params['key'])
        raise ControlError(f'Unknown browser probe {what!r}.', ErrorCategory.UNSUPPORTED)

    # Target resolution and actionability -------------------------------------
    def _key(self, tab: _Tab, target: Any) -> Tuple[str, int]:
        ref = target if isinstance(target, Ref) else self.refs.lookup(tab.id, str(target))
        if ref.scope != tab.id:
            raise ControlError(f'{ref.id} belongs to {ref.scope}, not {tab.id}.', ErrorCategory.STALE_REF)
        key = self.refs.resolve(ref)
        return key  # type: ignore[return-value]

    def _session(self, tab: _Tab, fkey: str) -> Any:
        if fkey == 'main':
            return tab.session
        if fkey not in tab.oop:
            raise ControlError('The frame holding this element is gone. Re-read the page.', ErrorCategory.STALE_REF)
        return tab.oop[fkey][0]

    def _object(self, tab: _Tab, key: Tuple[str, int]) -> Tuple[Any, str]:
        session = self._session(tab, key[0])
        try:
            node = session.send('DOM.resolveNode', {'backendNodeId': key[1]})['object']['objectId']
        except Exception:
            raise ControlError('The element no longer exists. Re-read the page to get fresh references.',
                               ErrorCategory.STALE_REF) from None
        return session, node

    def _frame_offset(self, tab: _Tab, fkey: str) -> Tuple[float, float]:
        if fkey == 'main':
            return 0.0, 0.0
        frame = tab.oop[fkey][1]
        box = frame.frame_element().evaluate(
            'e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);'
            ' return [r.left + e.clientLeft + parseFloat(s.paddingLeft), r.top + e.clientTop + parseFloat(s.paddingTop)]; }')
        return float(box[0]), float(box[1])

    def _point(self, tab: _Tab, key: Tuple[str, int], action: Action) -> Tuple[float, float]:
        """Auto-wait (read-only) until the target is visible, stable, enabled, unchanged and hit-testable."""
        session, node = self._object(tab, key)
        deadline = self.clock() + action.timeout_s
        last: Optional[Tuple[float, float]] = None
        reason = 'not visible'
        while True:
            action.cancel.raise_if_cancelled()
            if self._cancelled.is_set():
                raise ControlError('Browser actions were cancelled.', ErrorCategory.CANCELLED)
            try:
                ax = session.send('Accessibility.getPartialAXTree', {'backendNodeId': key[1], 'fetchRelatives': False})
                row: Dict[str, Any] = next((n for n in ax['nodes'] if n.get('backendDOMNodeId') == key[1]), {})
                role = str(row.get('role', {}).get('value', ''))
                name = str(row.get('name', {}).get('value', '')).strip()
                seen = tab.seen.get(key)
                if seen is not None and (role, name) != seen:
                    raise ControlError(f'The target changed after it was read (was {seen[0]} "{seen[1][:60]}", now '
                                       f'{role} "{name[:60]}"). Nothing was clicked; re-read the page.',
                                       ErrorCategory.STALE_REF)
                disabled = any(p['name'] == 'disabled' and p.get('value', {}).get('value') is True
                               for p in row.get('properties', []))
                session.send('DOM.scrollIntoViewIfNeeded', {'backendNodeId': key[1]})
                quads = session.send('DOM.getContentQuads', {'backendNodeId': key[1]})['quads']
            except ControlError:
                raise
            except Exception:
                raise ControlError('The element no longer exists. Re-read the page to get fresh references.',
                                   ErrorCategory.STALE_REF) from None
            if disabled:
                reason, last = 'disabled', None
            elif quads:
                quad = max(quads, key=lambda q: abs((q[2] - q[0]) * (q[5] - q[1])))
                dx, dy = self._frame_offset(tab, key[0])
                point = (sum(quad[0::2]) / 4 + dx, sum(quad[1::2]) / 4 + dy)
                if last is not None and abs(point[0] - last[0]) < 1 and abs(point[1] - last[1]) < 1:
                    reply = session.send('Runtime.callFunctionOn', {'objectId': node, 'functionDeclaration': HIT_TEST,
                                                                    'returnByValue': True})
                    if 'exceptionDetails' in reply or 'value' not in reply.get('result', {}):
                        # The page itself or a non-element node: nothing to click, and nothing was sent.
                        raise ControlError('That element (for example the whole page) is not clickable; choose a '
                                           'button, link or field from the read.', ErrorCategory.NOT_ACTIONABLE)
                    hit = reply['result']['value']
                    covered = not hit['ok']
                    if not covered and not hit['top']:
                        tag = tab.page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.tagName', list(point))
                        covered = tag not in ('IFRAME', 'FRAME')
                    if not covered:
                        if not (0 <= point[0] < tab.viewport[0] and 0 <= point[1] < tab.viewport[1]):
                            raise ControlError('Target centre lies outside the viewport.', ErrorCategory.NOT_ACTIONABLE)
                        return point
                    reason = 'covered by another element'
                else:
                    reason = 'still moving' if last else reason
                last = point
            if self.clock() >= deadline:
                raise ControlError(f'Target is {reason}; nothing was clicked.', ErrorCategory.NOT_ACTIONABLE)
            time.sleep(.05)

    def _coordinate(self, tab: _Tab, target: Any) -> Tuple[float, float]:
        if not isinstance(target, Point):
            raise ControlError('A coordinate target is required.', ErrorCategory.INVALID_ARGUMENTS)
        viewport = Rect(0, 0, tab.viewport[0], tab.viewport[1])
        transform = Transform(Frame.VIEWPORT, tab.id, 0, 0, 1, 1, tab.viewport[0], tab.viewport[1],
                              tab.read_at or self.clock(), max_age_s=120)
        try:
            p = transform.to_physical(Point(target.x, target.y, Frame.VIEWPORT, target.source or tab.id),
                                      Layout((Monitor('viewport', viewport, 1.0),)), self.clock)
        except CoordinateError as exc:
            raise ControlError(str(exc), ErrorCategory.INVALID_ARGUMENTS) from None
        return p.x, p.y

    def _target(self, tab: _Tab, action: Action) -> Tuple[float, float]:
        target = action.target if action.target is not None else action.params.get('ref')
        if isinstance(target, Point):
            return self._coordinate(tab, target)
        if target is None:
            raise ControlError('This action needs a ref or coordinate target.', ErrorCategory.INVALID_ARGUMENTS)
        return self._point(tab, self._key(tab, target), action)

    # Actions --------------------------------------------------------------
    def act(self, action: Action) -> ActionResult:
        timer = StageTimer()
        with self._lock:
            try:
                tab = self._tab(action.params.get('tab_id') or action.context.tab or None)
                result = self._dispatch(action, tab, timer)
            except ControlError as error:
                return ActionResult.failure(action, error, timings_ms=timer.result(), state=self.browser_state())
            except Exception as error:
                text = str(error).splitlines()[0][:300] if str(error) else type(error).__name__
                category = (ErrorCategory.POLICY_DENIED if 'ERR_BLOCKED_BY_CLIENT' in text else
                            ErrorCategory.TIMEOUT if 'Timeout' in text else ErrorCategory.UNCERTAIN)
                return ActionResult(action.action_id, False, Route.BROWSER, text=text,
                                    executed=category is ErrorCategory.UNCERTAIN, error_category=category,
                                    timings_ms=timer.result(), state=self.browser_state())
            verified = result.verified
            evidence = result.evidence
            if result.ok and action.expectation is not None:
                with timer.stage('verify'):
                    from ..verify import default_verifier
                    verified, evidence = default_verifier.wait(action.expectation, self.probe, action.timeout_s,
                                                               action.cancel)
            return ActionResult(action.action_id, result.ok and (verified or action.expectation is None),
                                Route.BROWSER, text=result.text, image=result.image,
                                state={**self.browser_state(), **result.state}, executed=result.executed,
                                verified=verified, evidence=evidence,
                                error_category=(ErrorCategory.NONE if result.ok and (verified or action.expectation is None)
                                                else ErrorCategory.VERIFICATION_FAILED),
                                timings_ms=timer.result())

    def _done(self, action: Action, text: str = '', executed: bool = True, verified: bool = False,
              evidence: str = '', **extra: Any) -> ActionResult:
        return ActionResult(action.action_id, True, Route.BROWSER, text=text, executed=executed, verified=verified,
                            evidence=evidence, **extra)

    def _dispatch(self, action: Action, tab: _Tab, timer: StageTimer) -> ActionResult:
        name, p = action.name, action.params
        page = tab.page
        if name == 'navigate':
            url = str(p.get('url', ''))
            with timer.stage('app_wait'):
                if url in ('back', 'forward', 'reload'):
                    {'back': page.go_back, 'forward': page.go_forward, 'reload': page.reload}[url](
                        wait_until='domcontentloaded', timeout=action.timeout_s * 1000)
                else:
                    page.goto(self.policy.check_url(url), wait_until='domcontentloaded', timeout=action.timeout_s * 1000)
            for frame in page.frames:  # Final URLs of every frame must also satisfy the policy.
                if frame.url.startswith(('http:', 'https:')):
                    self.policy.check_url(frame.url)
            return self._done(action, f'Navigated to {page.url} - {page.title()[:200]}', verified=True,
                              evidence=f'final URL {page.url}')
        if name == 'new_tab':
            page = self.context.new_page()
            self.active = next(t.id for t in self.tabs.values() if t.page is page)
            if p.get('url'):
                page.goto(self.policy.check_url(str(p['url'])), wait_until='domcontentloaded')
            return self._done(action, verified=True)
        if name == 'switch_tab':
            target = self._tab(str(p['tab_id']))
            target.page.bring_to_front()
            self.active = target.id
            return self._done(action, verified=True)
        if name == 'close_tab':
            target = self._tab(str(p['tab_id']))
            target.page.close()
            return self._done(action, verified=target.id not in self.tabs)
        if name == 'list_tabs':
            return self._done(action, executed=False, verified=True)
        if name == 'read_page':
            with timer.stage('tree_read'):
                obs = self.read_page(tab.id, str(p.get('filter', '')), int(p.get('depth', 15)), p.get('ref'))
            return self._done(action, obs.text, executed=False, verified=True)
        if name == 'find':
            with timer.stage('tree_read'):
                rows = self.find(str(p['query']), tab.id)
            return self._done(action, '\n'.join(f'{role} "{n[:120]}" [{r.id}]' for r, role, n in rows) or 'No matches.',
                              executed=False, verified=True)
        if name == 'get_page_text':
            with timer.stage('tree_read'):
                text = self.page_text(tab.id)
            return self._done(action, text, executed=False, verified=True)
        if name in ('screenshot', 'zoom'):
            with timer.stage('capture'):
                clip = None
                if name == 'zoom':
                    x0, y0, x1, y1 = (float(v) for v in p['region'])
                    Rect(int(x0), int(y0), int(x1), int(y1))
                    if x0 < 0 or y0 < 0 or x1 > tab.viewport[0] or y1 > tab.viewport[1]:
                        raise ControlError('Zoom region lies outside the viewport.', ErrorCategory.INVALID_ARGUMENTS)
                    clip = {'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0}
                image = page.screenshot(type='png', scale='css', clip=clip)
            tab.read_at = self.clock()
            return self._done(action, executed=False, verified=True, image=image)
        if name == 'wait':
            seconds = float(p.get('duration', 1))
            if not 0 <= seconds <= 30:
                raise ControlError('wait duration must be 0-30 seconds.', ErrorCategory.INVALID_ARGUMENTS)
            end = self.clock() + seconds
            while self.clock() < end:
                action.cancel.raise_if_cancelled()
                page.wait_for_timeout(min(100, (end - self.clock()) * 1000))
            return self._done(action, executed=False, verified=True)
        if name == 'form_input':
            return self._form_input(action, tab, timer)
        if name in POINTER or name in ('hover', 'mouse_move', 'left_mouse_down', 'left_mouse_up'):
            with timer.stage('tree_read'):
                x, y = self._target(tab, action)
            with timer.stage('input'):
                modifiers = [KEY_NAMES.get(m.lower(), m) for m in str(p.get('modifiers', '')).split('+') if m]
                for key in modifiers:
                    page.keyboard.down(key)
                try:
                    if name in POINTER:
                        button, count = POINTER[name]
                        page.mouse.click(x, y, button=button, click_count=count)
                    elif name in ('hover', 'mouse_move'):
                        page.mouse.move(x, y)
                    else:
                        page.mouse.move(x, y)
                        (page.mouse.down if name == 'left_mouse_down' else page.mouse.up)()
                finally:
                    for key in reversed(modifiers):
                        page.keyboard.up(key)
            return self._done(action, f'{name} at ({x:.0f}, {y:.0f})')
        if name == 'left_click_drag':
            start = p.get('from')
            if not isinstance(start, Point):
                raise ControlError('left_click_drag needs a from coordinate.', ErrorCategory.INVALID_ARGUMENTS)
            x0, y0 = self._coordinate(tab, start)
            x1, y1 = self._target(tab, action)
            with timer.stage('input'):
                page.mouse.move(x0, y0)
                page.mouse.down()
                page.mouse.move(x1, y1, steps=12)
                page.mouse.up()
            return self._done(action, f'dragged to ({x1:.0f}, {y1:.0f})')
        if name == 'scroll':
            amount = int(p.get('scroll_amount', 3))
            direction = str(p.get('scroll_direction', 'down'))
            if direction not in ('up', 'down', 'left', 'right') or not 1 <= amount <= 10:
                raise ControlError('scroll needs a direction and 1-10 notches.', ErrorCategory.INVALID_ARGUMENTS)
            x, y = self._target(tab, action) if action.target is not None else (tab.viewport[0] / 2, tab.viewport[1] / 2)
            dx = {'left': -100, 'right': 100}.get(direction, 0) * amount
            dy = {'up': -100, 'down': 100}.get(direction, 0) * amount
            with timer.stage('input'):
                page.mouse.move(x, y)
                page.mouse.wheel(dx, dy)
                page.wait_for_timeout(50)
            return self._done(action, f'scrolled {direction} {amount}')
        if name == 'scroll_to':
            node_key = self._key(tab, action.target if action.target is not None else p.get('ref'))
            self._session(tab, node_key[0]).send('DOM.scrollIntoViewIfNeeded', {'backendNodeId': node_key[1]})
            return self._done(action, verified=True)
        if name == 'type':
            with timer.stage('input'):
                page.keyboard.type(str(p['text']))
            return self._done(action)
        if name in ('key', 'hold_key'):
            return self._keys(action, page, timer)
        raise ControlError(f'Unsupported browser member {name!r}.', ErrorCategory.UNSUPPORTED)

    def _keys(self, action: Action, page: Any, timer: StageTimer) -> ActionResult:
        text = str(action.params.get('text', '')).strip()
        repeat = int(action.params.get('repeat', 1))
        if not text or not 1 <= repeat <= 100:
            raise ControlError('key needs text and repeat 1-100.', ErrorCategory.INVALID_ARGUMENTS)
        chords = ['+'.join(KEY_NAMES.get(k.lower(), k) for k in chord.split('+')) for chord in text.split()]
        with timer.stage('input'):
            if action.name == 'hold_key':
                duration = float(action.params.get('duration', 1))
                if not 0 <= duration <= 30 or len(chords) != 1:
                    raise ControlError('hold_key needs one key and 0-30 seconds.', ErrorCategory.INVALID_ARGUMENTS)
                page.keyboard.down(chords[0])
                try:
                    page.wait_for_timeout(duration * 1000)
                finally:
                    page.keyboard.up(chords[0])
            else:
                for _ in range(repeat):
                    for chord in chords:
                        page.keyboard.press(chord)
        return self._done(action, f'pressed {text}' + (f' x{repeat}' if repeat > 1 else ''))

    def _form_input(self, action: Action, tab: _Tab, timer: StageTimer) -> ActionResult:
        target = action.target if action.target is not None else action.params.get('ref')
        key = self._key(tab, target)
        value = action.params.get('value')
        if not isinstance(value, (str, int, float, bool)):
            raise ControlError('form_input needs a string, number or boolean value.', ErrorCategory.INVALID_ARGUMENTS)
        with timer.stage('tree_read'):
            self._point(tab, key, action)  # Same visibility/identity/enabled checks as a click.
        session, node = self._object(tab, key)
        with timer.stage('input'):
            reply = session.send('Runtime.callFunctionOn', {'objectId': node, 'functionDeclaration': FORM_INPUT,
                                                            'arguments': [{'value': value}], 'returnByValue': True})
        if 'exceptionDetails' in reply:
            detail = str(reply['exceptionDetails'].get('exception', {}).get('description', ''))
            messages = {'PASSWORD': 'Password fields are never filled automatically.',
                        'FILE': 'File inputs need the gated file_upload tool.',
                        'NO_OPTION': f'No option named {value!r}.', 'NOT_A_FIELD': 'The target is not a form field.'}
            reason = next((m for k, m in messages.items() if k in detail), 'The field rejected the value.')
            raise ControlError(reason, ErrorCategory.POLICY_DENIED if 'PASSWORD' in detail or 'FILE' in detail
                               else ErrorCategory.INVALID_ARGUMENTS)
        with timer.stage('verify'):
            current = session.send('Runtime.callFunctionOn', {'objectId': node, 'functionDeclaration': READ_VALUE,
                                                              'returnByValue': True})['result'].get('value')
        expected: Any = (value is True or value == 'true') if isinstance(current, bool) else str(value)
        if isinstance(current, str) and isinstance(expected, str) and not isinstance(value, bool):
            ok = current == expected or current.strip() == expected.strip()
        else:
            ok = current == expected
        if not ok:
            raise ControlError('The field value did not match after input; check the field before repeating.',
                               ErrorCategory.VERIFICATION_FAILED, executed=True)
        return self._done(action, 'field value verified', verified=True, evidence='value read back from the element')


def tool_members() -> Sequence[str]:
    """Members this executor implements (for the ToolRegistry and model-facing adapters)."""
    return ('navigate', 'new_tab', 'list_tabs', 'switch_tab', 'close_tab', 'read_page', 'find', 'get_page_text',
            'screenshot', 'zoom', 'wait', 'form_input', *POINTER, 'hover', 'mouse_move', 'left_mouse_down',
            'left_mouse_up', 'left_click_drag', 'scroll', 'scroll_to', 'type', 'key', 'hold_key')


__all__ = ['BrowserExecutor', 'tool_members', 'READ_MEMBERS', 'Expectation']
