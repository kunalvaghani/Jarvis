// Jarvis Browser: Jarvis works in the user's Chrome, only inside its own "Jarvis" tab group.
//
// - Commands arrive from Jarvis through the native messaging host (com.jarvis.browser); Chrome lets only this
//   extension talk to it, and the host only accepts Jarvis with a per-run token. No web page can reach it.
// - Every command acts on a tab in the "Jarvis" group. A tab outside the group is refused, so the user's own
//   tabs are never read or driven. Tabs open in the background: the user's view is not switched.
// - Pages are read through Chrome's accessibility tree (chrome.debugger, CDP) and written in agent-browser's
//   snapshot format ('- role "name" [ref=eN]'), so Jarvis's browser code and safety rules apply unchanged.
// - There is no command that runs page script from Jarvis, reads cookies or storage, uploads or downloads.
'use strict';

const HOST = 'com.jarvis.browser';
const GROUP_TITLE = 'Jarvis';
const INTERACTIVE = new Set(['button', 'link', 'textbox', 'searchbox', 'combobox', 'checkbox', 'radio', 'menuitem',
  'menuitemcheckbox', 'menuitemradio', 'option', 'tab', 'switch', 'slider', 'spinbutton', 'treeitem', 'listbox']);
const REFERABLE = new Set([...INTERACTIVE, 'cell', 'gridcell', 'rowheader', 'columnheader', 'heading', 'row',
  'LayoutTableCell', 'listitem', 'article', 'img', 'image']);  // named items (Drive lists files as layout cells)
const SKIP = new Set(['none', 'generic', 'GenericContainer', 'InlineTextBox', 'RootWebArea', 'WebArea', 'Ignored',
  'presentation', 'LineBreak']);
const KEYS = {Enter: 13, Tab: 9, Escape: 27, Backspace: 8, Delete: 46, ArrowUp: 38, ArrowDown: 40, ArrowLeft: 37,
  ArrowRight: 39, Home: 36, End: 35, PageUp: 33, PageDown: 34, Space: 32};

let port = null;
const current = new Map();     // Jarvis task (session) -> the tab it works in; tasks run side by side
const attached = new Set();    // tabs with the debugger attached
const refMaps = new Map();     // tabId -> Map('e12' -> {node: backendDOMNodeId, session}), latest snapshot
const frames = new Map();      // tabId -> Map(sessionId -> url) of embedded frames from other sites (OOPIFs)
const dialogs = new Map();     // tabId -> the page dialog waiting for an answer (alert/confirm/prompt)
const leaveBlocked = new Set(); // tabs whose page asked to stay (unsaved changes) on Jarvis's last navigation
let jarvisTabs = new Set();    // tabs Jarvis created; a tab the user opens in the group is never read or driven
const tabSession = new Map();  // tabId -> the Jarvis task (session) that opened it, for its end-of-task clean-up
let renderMode = 'screencast'; // keep hidden tabs drawing ('off' to compare)
const restored = chrome.storage.session.get('jarvisTabs').then((saved) => {
  jarvisTabs = new Set([...(saved.jarvisTabs || []), ...jarvisTabs]);
});

function remember() {
  return chrome.storage.session.set({jarvisTabs: [...jarvisTabs]});
}

// ---- Connection ------------------------------------------------------------------------------------------------
function connect() {
  if (port) return;
  try {
    port = chrome.runtime.connectNative(HOST);
  } catch (error) {
    port = null;
    return;
  }
  port.onMessage.addListener(onMessage);
  port.onDisconnect.addListener(() => { port = null; setTimeout(connect, 3000); });
}

chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
chrome.alarms.create('jarvis-keepalive', {periodInMinutes: 0.5});
chrome.alarms.onAlarm.addListener(() => connect());
chrome.debugger.onDetach.addListener((source) => attached.delete(source.tabId));
chrome.debugger.onEvent.addListener((source, method, params) => {
  // Screencast frames keep a background tab drawing (Gmail renders lists and autosaves only when it draws).
  if (method === 'Page.screencastFrame') {
    chrome.debugger.sendCommand(source, 'Page.screencastFrameAck', {sessionId: params.sessionId}).catch(() => {});
  }
  // "Leave site?" in Jarvis's own tab means unsaved work: always Stay (never discard typed text) and tell Jarvis,
  // which waits for the page to save and tries again. A dialog left open froze a Gmail tab for 4 minutes and
  // leaving lost a typed draft body (live 2026-11-03). Alerts, confirms and prompts are never answered here:
  // they are reported to Jarvis with the next command's error.
  if (method === 'Page.javascriptDialogOpening') {
    if (params.type === 'beforeunload') {
      leaveBlocked.add(source.tabId);
      chrome.debugger.sendCommand(source, 'Page.handleJavaScriptDialog', {accept: false}).catch(() => {});
    } else {
      dialogs.set(source.tabId, `${params.type}: ${String(params.message || '').slice(0, 200)}`);
    }
  }
  if (method === 'Page.javascriptDialogClosed') dialogs.delete(source.tabId);
  // Frames from other sites (Docs' Move dialog, embedded widgets) run as their own targets: track their sessions
  // so reads and actions reach them.
  if (method === 'Target.attachedToTarget' && params.targetInfo && params.targetInfo.type === 'iframe') {
    if (!frames.has(source.tabId)) frames.set(source.tabId, new Map());
    frames.get(source.tabId).set(params.sessionId, params.targetInfo.url || '');
  }
  if (method === 'Target.detachedFromTarget' && frames.has(source.tabId)) frames.get(source.tabId).delete(params.sessionId);
});
chrome.tabs.onRemoved.addListener((tabId) => {
  attached.delete(tabId);
  refMaps.delete(tabId);
  frames.delete(tabId);
  if (jarvisTabs.delete(tabId)) remember();
  for (const [session, tab] of current) if (tab === tabId) current.delete(session);
  tabSession.delete(tabId);
});
connect();

async function onMessage(message) {
  const reply = {id: message && message.id};
  try {
    await restored;
    const session = String((message && message.session) || 'main');
    reply.data = await run(Array.isArray(message.args) ? message.args.map(String) : [], session);
    reply.success = true;
  } catch (error) {
    reply.success = false;
    reply.error = String((error && error.message) || error).slice(0, 500);
  }
  if (port) port.postMessage(reply);
}

// ---- The Jarvis tab group -------------------------------------------------------------------------------------
async function groupIds() {
  return (await chrome.tabGroups.query({title: GROUP_TITLE})).map((g) => g.id);
}

async function groupTabs() {
  // Jarvis's own tabs: created by Jarvis and still in the Jarvis group (a tab dragged out is no longer driven).
  const tabs = [];
  for (const id of await groupIds()) tabs.push(...await chrome.tabs.query({groupId: id}));
  return tabs.filter((t) => jarvisTabs.has(t.id));
}

async function isMine(tabId) {
  return (await groupTabs()).some((t) => t.id === tabId);
}

async function newTab(url, session) {
  const tab = await chrome.tabs.create({url: url || 'about:blank', active: false});
  jarvisTabs.add(tab.id);
  tabSession.set(tab.id, session);
  await remember();
  const ids = await groupIds();
  const window = ids.length ? (await chrome.tabGroups.get(ids[0])).windowId : null;
  if (ids.length && window === tab.windowId) {
    await chrome.tabs.group({tabIds: [tab.id], groupId: ids[0]});
  } else {
    const id = await chrome.tabs.group({tabIds: [tab.id]});
    await chrome.tabGroups.update(id, {title: GROUP_TITLE, color: 'blue'});
  }
  current.set(session, tab.id);
  return tab.id;
}

async function workTab(session, create) {
  const mine = current.get(session);
  if (mine !== undefined && await isMine(mine)) return mine;
  // Only opening a page makes a tab (each task its own; never another task's or the user's). A read or click
  // with no tab fails instead of leaving an empty tab behind.
  if (!create) throw new Error('no Jarvis tab is open for this task; open a page first');
  return newTab('', session);
}

function tabRef(tabId) {
  return 't' + tabId;
}

async function ownTab(ref) {
  const id = Number(String(ref).replace(/^t/, ''));
  if (!Number.isInteger(id) || !await isMine(id)) {
    throw new Error(`no such tab ${ref} in the Jarvis group (other tabs are never driven)`);
  }
  return id;
}

// ---- CDP ------------------------------------------------------------------------------------------------------
async function cdp(tabId, method, params, sessionId) {
  if (!attached.has(tabId)) {
    await chrome.debugger.attach({tabId}, '1.3');
    attached.add(tabId);
    // Jarvis's tabs stay in the background: the page is told it is focused and active, and (screencast mode)
    // Chrome keeps drawing it, so lists render and drafts autosave while the user works elsewhere.
    const target = {tabId};
    await chrome.debugger.sendCommand(target, 'Page.enable', {}).catch(() => {});  // dialog events
    await chrome.debugger.sendCommand(target, 'Target.setAutoAttach', {autoAttach: true, waitForDebuggerOnStart: false,
      flatten: true}).catch(() => {});  // embedded frames from other sites
    await chrome.debugger.sendCommand(target, 'Emulation.setFocusEmulationEnabled', {enabled: true}).catch(() => {});
    await chrome.debugger.sendCommand(target, 'Page.setWebLifecycleState', {state: 'active'}).catch(() => {});
    if (renderMode === 'screencast') {
      await chrome.debugger.sendCommand(target, 'Page.startScreencast', {format: 'jpeg', quality: 10, maxWidth: 320,
        maxHeight: 240, everyNthFrame: 4}).catch(() => {});
    }
  }
  return chrome.debugger.sendCommand(sessionId ? {tabId, sessionId} : {tabId}, method, params || {});
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitLoad(tabId, state, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 30000);
  while (Date.now() < deadline) {
    const tab = await chrome.tabs.get(tabId);
    // 'complete' on a real page (a new tab is 'complete' on about:blank before its navigation starts).
    if (tab.status === 'complete' && tab.url && !tab.url.startsWith('about:blank')) {
      if (state === 'networkidle') await sleep(500);
      return true;
    }
    await sleep(200);
  }
  return false;
}

async function node(tabId, ref) {
  const key = String(ref).replace(/^@/, '');
  const found = (refMaps.get(tabId) || new Map()).get(key);
  if (found === undefined) throw new Error(`unknown ref: ${ref} (read the page again)`);
  const {object} = await cdp(tabId, 'DOM.resolveNode', {backendNodeId: found.node}, found.session);
  return {backendNodeId: found.node, objectId: object.objectId, session: found.session};
}

async function onNode(tabId, ref, fn, args) {
  const {objectId, session} = await node(tabId, ref);
  const result = await cdp(tabId, 'Runtime.callFunctionOn', {objectId, functionDeclaration: fn,
    arguments: (args || []).map((value) => ({value})), returnByValue: true, awaitPromise: true}, session);
  if (result.exceptionDetails) throw new Error('the element could not be used: ' + result.exceptionDetails.text);
  return result.result ? result.result.value : undefined;
}

async function mouse(tabId, ref, kind) {
  const {backendNodeId, session} = await node(tabId, ref);
  if (session) {  // inside an embedded frame: its own coordinates; the element's own events
    await cdp(tabId, 'DOM.scrollIntoViewIfNeeded', {backendNodeId}, session).catch(() => {});
    const events = {hover: 'mouseover', dblclick: 'dblclick', rightclick: 'contextmenu'}[kind];
    await onNode(tabId, ref, events ? `function () { this.dispatchEvent(new MouseEvent("${events}", {bubbles: true})); }`
      : 'function () { this.click(); }');
    return;
  }
  try {
    await cdp(tabId, 'DOM.scrollIntoViewIfNeeded', {backendNodeId});
  } catch (error) { /* not scrollable: click where it is */ }
  let quads = [];
  try {
    quads = (await cdp(tabId, 'DOM.getContentQuads', {backendNodeId})).quads || [];
  } catch (error) { quads = []; }
  if (!quads.length) {
    if (kind === 'hover') throw new Error('the element has no box on the page');
    await onNode(tabId, ref, 'function () { this.click(); }');  // hidden box: the element's own click
    return;
  }
  const q = quads[0];
  const x = (q[0] + q[2] + q[4] + q[6]) / 4;
  const y = (q[1] + q[3] + q[5] + q[7]) / 4;
  await cdp(tabId, 'Input.dispatchMouseEvent', {type: 'mouseMoved', x, y});
  if (kind === 'hover') return;
  const button = kind === 'rightclick' ? 'right' : 'left';
  const clicks = kind === 'dblclick' ? 2 : 1;
  for (let n = 1; n <= clicks; n++) {
    await cdp(tabId, 'Input.dispatchMouseEvent', {type: 'mousePressed', x, y, button, clickCount: n});
    await cdp(tabId, 'Input.dispatchMouseEvent', {type: 'mouseReleased', x, y, button, clickCount: n});
  }
}

async function typeText(tabId, text, delayMs) {
  // Real key events, one per character: rich editors (Gmail's message box) only register typed input; a single
  // insertText changed the box on screen but Gmail saved the draft without it (live 2026-11-03). Canvas editors
  // (Google Docs) drop keys sent back to back in a background tab, so they type with a short pause per key.
  if (text.length > 2000) {
    await cdp(tabId, 'Input.insertText', {text});
    return;
  }
  for (const ch of text) {
    if (ch === '\n') {
      await press(tabId, 'Enter');
    } else {
      await cdp(tabId, 'Input.dispatchKeyEvent', {type: 'keyDown', key: ch, text: ch, unmodifiedText: ch});
      await cdp(tabId, 'Input.dispatchKeyEvent', {type: 'keyUp', key: ch});
    }
    if (delayMs) await sleep(delayMs);
  }
}

async function press(tabId, chord) {
  const parts = String(chord).split('+');
  const key = parts.pop();
  const mods = parts.reduce((m, p) => m | ({Alt: 1, Control: 2, Ctrl: 2, Meta: 4, Shift: 8}[p] || 0), 0);
  const named = KEYS[key];
  const code = named || key.toUpperCase().charCodeAt(0);
  const text = key === 'Enter' ? '\r' : (named || mods & 6 ? '' : key);
  const base = {modifiers: mods, windowsVirtualKeyCode: code, key: key === 'Space' ? ' ' : key};
  await cdp(tabId, 'Input.dispatchKeyEvent', {...base, type: text ? 'keyDown' : 'rawKeyDown', text});
  await cdp(tabId, 'Input.dispatchKeyEvent', {...base, type: 'keyUp'});
}

// ---- Snapshot (agent-browser format) --------------------------------------------------------------------------
function prop(n, name) {
  const found = (n.properties || []).find((p) => p.name === name);
  return found && found.value ? found.value.value : undefined;
}

function quote(text) {
  return String(text || '').replace(/\s+/g, ' ').trim().slice(0, 300).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

async function snapshot(tabId, interactiveOnly) {
  const refs = new Map();
  const lines = [];
  let counter = 0;
  const tree = async (session, depth0) => {
  const {nodes} = await cdp(tabId, 'Accessibility.getFullAXTree', {}, session);
  const byId = new Map(nodes.map((n) => [n.nodeId, n]));
  const visit = (n, depth) => {
    const role = n.role ? String(n.role.value) : '';
    const name = n.name ? String(n.name.value || '') : '';
    let next = depth;
    if (!n.ignored && role && !SKIP.has(role) && !(role === 'StaticText' && !name.trim())) {
      const referable = REFERABLE.has(role) && n.backendDOMNodeId !== undefined &&
        (INTERACTIVE.has(role) || name.trim());
      if (!interactiveOnly || referable) {
        let line = `${'  '.repeat(depth)}- ${role}`;
        if (name.trim()) line += ` "${quote(name)}"`;
        for (const state of ['checked', 'expanded', 'selected', 'disabled', 'pressed']) {
          const value = prop(n, state);
          if (value === true || value === 'true') line += ` [${state}]`;
          else if (state === 'expanded' && (value === false || value === 'false')) line += ' [expanded=false]';
          else if (state === 'checked' && value === 'mixed') line += ' [checked=mixed]';
        }
        if (referable) {
          counter += 1;
          refs.set('e' + counter, {node: n.backendDOMNodeId, session});
          line += ` [ref=e${counter}]`;
        }
        lines.push(line);
        next = depth + 1;
      }
    }
    for (const child of n.childIds || []) {
      const c = byId.get(child);
      if (c) visit(c, next);
    }
  };
  const root = nodes.find((n) => !n.parentId) || nodes[0];
  if (root) visit(root, depth0);
  };
  await tree(undefined, 0);
  for (const [session, url] of frames.get(tabId) || new Map()) {
    let host = '';
    try { host = new URL(url).host; } catch (error) { host = ''; }
    lines.push(`- Iframe "${quote(host)}"`);
    await tree(session, 1).catch(() => lines.push('  - StaticText "(this frame could not be read)"'));
  }
  refMaps.set(tabId, refs);
  return lines.join('\n');
}

// ---- Commands (the agent-browser subset Jarvis uses) ---------------------------------------------------------
async function run(args, session) {
  const [command, ...rest] = args;
  if (command === 'ping') return {ok: true, version: chrome.runtime.getManifest().version, render: renderMode};
  if (command === 'reload') {  // Jarvis updates the extension files, then reloads it (no click in chrome://extensions)
    setTimeout(() => chrome.runtime.reload(), 200);
    return {reloading: true};
  }
  if (command === 'render') {
    renderMode = rest[0] === 'off' ? 'off' : 'screencast';
    return {render: renderMode};
  }
  if (command === 'close') {  // end of a task: close the tabs this task opened (never the browser or user tabs)
    const own = [...jarvisTabs].filter((id) => tabSession.get(id) === session);
    for (const id of own) await chrome.tabs.remove(id).catch(() => {});
    current.delete(session);
    return {closed: own.length};
  }
  if (command === 'tab') {
    const [sub, value] = rest;
    if (sub === 'list') {
      const tabs = await groupTabs();
      return {tabs: tabs.map((t) => ({tabId: tabRef(t.id), title: t.title || '', url: t.url || '',
        active: t.id === current.get(session)}))};
    }
    if (sub === 'new') {
      const id = await newTab(value || '', session);
      if (value) await waitLoad(id, 'load', 30000);
      return {tabId: tabRef(id)};
    }
    if (sub === 'close') {
      const id = await ownTab(value);
      await chrome.tabs.remove(id);
      return {closed: true};
    }
    current.set(session, await ownTab(sub));
    return {tabId: sub};
  }
  const tabId = await workTab(session, command === 'open');
  if (dialogs.has(tabId)) throw new Error(`the page shows a dialog (${dialogs.get(tabId)}); it needs a decision`);
  switch (command) {
    case 'open': {
      if (!/^https?:\/\//i.test(rest[0] || '')) throw new Error('invalid url: only http(s) pages open');
      leaveBlocked.delete(tabId);
      await chrome.tabs.update(tabId, {url: rest[0]});
      await sleep(600);
      if (leaveBlocked.delete(tabId)) {
        throw new Error('unsaved changes: the page asked to stay, so it stayed open (nothing was discarded)');
      }
      refMaps.delete(tabId);
      await waitLoad(tabId, 'load', 45000);
      return {url: (await chrome.tabs.get(tabId)).url};
    }
    case 'back':
    case 'forward':
    case 'reload':
      if (command === 'reload') await chrome.tabs.reload(tabId);
      else if (command === 'back') await chrome.tabs.goBack(tabId);
      else await chrome.tabs.goForward(tabId);
      refMaps.delete(tabId);
      await sleep(300);
      await waitLoad(tabId, 'load', 30000);
      return {url: (await chrome.tabs.get(tabId)).url};
    case 'get': {
      const [what, ref] = rest;
      if (what === 'url') return {url: (await chrome.tabs.get(tabId)).url || ''};
      if (what === 'title') return {title: (await chrome.tabs.get(tabId)).title || ''};
      if (what === 'text') return {text: await onNode(tabId, ref, 'function () { return (this.innerText || this.textContent || "").slice(0, 20000); }')};
      if (what === 'value') return {value: await onNode(tabId, ref, 'function () { return this.value !== undefined ? String(this.value) : (this.innerText || ""); }')};
      // The item ID a list row carries (Drive's data-id): read-only, used to build the item's own address.
      if (what === 'itemid') return {id: await onNode(tabId, ref, 'function () { for (let el = this; el && el !== document.body; el = el.parentElement) { for (const name of ["data-id", "data-target-id", "data-item-id", "data-doc-id", "data-drive-id", "data-folder-id"]) { const v = el.getAttribute(name); if (v && /^[\\w-]{10,}$/.test(v)) return v; } } return ""; }')};
      // Diagnostic: the data-* attribute names (not values) on the element and its ancestors.
      if (what === 'attrnames') return {names: await onNode(tabId, ref, 'function () { const out = []; for (let el = this; el && el !== document.body && out.length < 40; el = el.parentElement) { for (const a of el.attributes) if (a.name.startsWith("data-")) out.push(a.name + (/^[\\w-]{20,}$/.test(a.value) ? "=<id-like>" : "")); } return out; }')};
      throw new Error(`unknown command: get ${what}`);
    }
    case 'is':
      if (rest[0] !== 'checked') throw new Error(`unknown command: is ${rest[0]}`);
      return {checked: Boolean(await onNode(tabId, rest[1], 'function () { return this.checked === true || this.getAttribute("aria-checked") === "true"; }'))};
    case 'snapshot':
      return {snapshot: await snapshot(tabId, rest.includes('-i'))};
    case 'read': {
      const result = await cdp(tabId, 'Runtime.evaluate', {expression: 'document.body ? document.body.innerText.slice(0, 200000) : ""', returnByValue: true});
      return {content: result.result ? String(result.result.value || '') : ''};
    }
    case 'click':
    case 'dblclick':
    case 'hover':
    case 'rightclick':
      await mouse(tabId, rest[0], command);
      return {done: true};
    case 'fill': {
      const {backendNodeId, session} = await node(tabId, rest[0]);
      await cdp(tabId, 'DOM.focus', {backendNodeId}, session);
      // Keys go to whatever has focus; on a page with keyboard shortcuts (Gmail: "e" archives) a stray key acts.
      // Type only when the field itself holds the focus.
      const focused = await onNode(tabId, rest[0], 'function () { this.focus(); const a = document.activeElement; return a === this || this.contains(a); }');
      if (!focused) throw new Error('could not put the cursor in that field, so nothing was typed');
      await onNode(tabId, rest[0], 'function () { if (this.select) { this.select(); } else { const r = document.createRange(); r.selectNodeContents(this); const s = getSelection(); s.removeAllRanges(); s.addRange(r); } }');
      await cdp(tabId, 'Input.dispatchKeyEvent', {type: 'rawKeyDown', key: 'Backspace', windowsVirtualKeyCode: 8});
      await cdp(tabId, 'Input.dispatchKeyEvent', {type: 'keyUp', key: 'Backspace', windowsVirtualKeyCode: 8});
      await typeText(tabId, rest[1] || '');
      return {done: true};
    }
    case 'select':
      return {selected: await onNode(tabId, rest[0], 'function (want) { const o = Array.from(this.options || []).find((x) => x.value === want || x.text.trim() === want); if (!o) throw new Error("no option " + want); this.value = o.value; this.dispatchEvent(new Event("input", {bubbles: true})); this.dispatchEvent(new Event("change", {bubbles: true})); return o.text; }', [rest[1] || ''])};
    case 'check':
    case 'uncheck': {
      const now = await onNode(tabId, rest[0], 'function () { return this.checked === true || this.getAttribute("aria-checked") === "true"; }');
      if (Boolean(now) !== (command === 'check')) await mouse(tabId, rest[0], 'click');
      return {done: true};
    }
    case 'keyboard': {
      // keyboard type <text> [--delay ms] | keyboard insert <text> (one text insertion, for editors that take it)
      const delay = rest[2] === '--delay' ? Math.min(Number(rest[3]) || 0, 200) : 0;
      if (rest[0] === 'type') await typeText(tabId, rest[1] || '', delay);
      else if (rest[0] === 'insert') await cdp(tabId, 'Input.insertText', {text: rest[1] || ''});
      else throw new Error(`unknown command: keyboard ${rest[0]}`);
      return {done: true};
    }
    case 'document': {
      // document text: the open Google Doc's current text, from Docs' own plain-text export of this document
      // (fixed code, same origin, read-only). Docs draws on a canvas, so its text is not in the accessibility tree.
      if (rest[0] !== 'text') throw new Error(`unknown command: document ${rest[0]}`);
      const result = await cdp(tabId, 'Runtime.evaluate', {returnByValue: true, awaitPromise: true, expression: `(async () => {
        const id = (location.pathname.match(/\\/document\\/d\\/([\\w-]+)/) || [])[1];
        if (!id) return null;
        const reply = await fetch('/document/d/' + id + '/export?format=txt', {credentials: 'same-origin'});
        return reply.ok ? (await reply.text()).slice(0, 20000) : null;
      })()`});
      const text = result.result ? result.result.value : null;
      if (text === null || text === undefined) throw new Error('this is not an open Google Doc, or its text could not be read');
      return {text};
    }
    case 'focus': {
      // focus editor: the typing target of canvas editors that are not in the accessibility tree (Google Docs and
      // Slides take keys through a hidden contenteditable in an iframe). Fixed code, nothing from the page or Jarvis.
      if (rest[0] !== 'editor') throw new Error(`unknown command: focus ${rest[0]}`);
      const result = await cdp(tabId, 'Runtime.evaluate', {returnByValue: true, expression: `(() => {
        const frame = document.querySelector('iframe.docs-texteventtarget-iframe');
        const target = frame && frame.contentDocument && frame.contentDocument.querySelector('[contenteditable="true"]');
        if (!target) return false;
        frame.focus(); target.focus();
        return frame.contentDocument.activeElement === target;
      })()`});
      if (!(result.result && result.result.value)) throw new Error('no editor to type into on this page; nothing typed');
      return {focused: true};
    }
    case 'press':
      await press(tabId, rest[0] || 'Enter');
      return {done: true};
    case 'scroll': {
      const amount = Number(rest[1] || 300);
      const dx = rest[0] === 'left' ? -amount : rest[0] === 'right' ? amount : 0;
      const dy = rest[0] === 'up' ? -amount : rest[0] === 'down' ? amount : 0;
      await cdp(tabId, 'Input.dispatchMouseEvent', {type: 'mouseWheel', x: 200, y: 200, deltaX: dx, deltaY: dy});
      return {done: true};
    }
    case 'scrollintoview': {
      const {backendNodeId, session} = await node(tabId, rest[0]);
      await cdp(tabId, 'DOM.scrollIntoViewIfNeeded', {backendNodeId}, session);
      return {done: true};
    }
    case 'wait': {
      if (rest[0] === '--load') {
        await waitLoad(tabId, rest[1] || 'load', 30000);
        return {done: true};
      }
      const ms = Math.min(Number(rest[0]) || 0, 60000);
      await sleep(ms);
      return {done: true};
    }
    default:
      throw new Error(`unknown command: ${command} (not available through the Jarvis extension)`);
  }
}
