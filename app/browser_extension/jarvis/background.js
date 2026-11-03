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
const REFERABLE = new Set([...INTERACTIVE, 'cell', 'gridcell', 'rowheader', 'columnheader', 'heading', 'row']);
const SKIP = new Set(['none', 'generic', 'GenericContainer', 'InlineTextBox', 'RootWebArea', 'WebArea', 'Ignored',
  'presentation', 'LineBreak']);
const KEYS = {Enter: 13, Tab: 9, Escape: 27, Backspace: 8, Delete: 46, ArrowUp: 38, ArrowDown: 40, ArrowLeft: 37,
  ArrowRight: 39, Home: 36, End: 35, PageUp: 33, PageDown: 34, Space: 32};

let port = null;
const current = new Map();     // Jarvis task (session) -> the tab it works in; tasks run side by side
const attached = new Set();    // tabs with the debugger attached
const refMaps = new Map();     // tabId -> Map('e12' -> backendDOMNodeId), from the latest snapshot
const dialogs = new Map();     // tabId -> the page dialog waiting for an answer (alert/confirm/prompt)
const leaveBlocked = new Set(); // tabs whose page asked to stay (unsaved changes) on Jarvis's last navigation
let jarvisTabs = new Set();    // tabs Jarvis created; a tab the user opens in the group is never read or driven
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
});
chrome.tabs.onRemoved.addListener((tabId) => {
  attached.delete(tabId);
  refMaps.delete(tabId);
  if (jarvisTabs.delete(tabId)) remember();
  for (const [session, tab] of current) if (tab === tabId) current.delete(session);
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

async function workTab(session) {
  const mine = current.get(session);
  if (mine !== undefined && await isMine(mine)) return mine;
  return newTab('', session);  // each task gets its own tab; it never takes over another task's or the user's
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
async function cdp(tabId, method, params) {
  if (!attached.has(tabId)) {
    await chrome.debugger.attach({tabId}, '1.3');
    attached.add(tabId);
    // Jarvis's tabs stay in the background: the page is told it is focused and active, and (screencast mode)
    // Chrome keeps drawing it, so lists render and drafts autosave while the user works elsewhere.
    const target = {tabId};
    await chrome.debugger.sendCommand(target, 'Page.enable', {}).catch(() => {});  // dialog events
    await chrome.debugger.sendCommand(target, 'Emulation.setFocusEmulationEnabled', {enabled: true}).catch(() => {});
    await chrome.debugger.sendCommand(target, 'Page.setWebLifecycleState', {state: 'active'}).catch(() => {});
    if (renderMode === 'screencast') {
      await chrome.debugger.sendCommand(target, 'Page.startScreencast', {format: 'jpeg', quality: 10, maxWidth: 320,
        maxHeight: 240, everyNthFrame: 4}).catch(() => {});
    }
  }
  return chrome.debugger.sendCommand({tabId}, method, params || {});
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
  const backendNodeId = (refMaps.get(tabId) || new Map()).get(key);
  if (backendNodeId === undefined) throw new Error(`unknown ref: ${ref} (read the page again)`);
  const {object} = await cdp(tabId, 'DOM.resolveNode', {backendNodeId});
  return {backendNodeId, objectId: object.objectId};
}

async function onNode(tabId, ref, fn, args) {
  const {objectId} = await node(tabId, ref);
  const result = await cdp(tabId, 'Runtime.callFunctionOn', {objectId, functionDeclaration: fn,
    arguments: (args || []).map((value) => ({value})), returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw new Error('the element could not be used: ' + result.exceptionDetails.text);
  return result.result ? result.result.value : undefined;
}

async function mouse(tabId, ref, kind) {
  const {backendNodeId} = await node(tabId, ref);
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

async function typeText(tabId, text) {
  // Real key events, one per character: rich editors (Gmail's message box) only register typed input; a single
  // insertText changed the box on screen but Gmail saved the draft without it (live 2026-11-03).
  if (text.length > 2000) {
    await cdp(tabId, 'Input.insertText', {text});
    return;
  }
  for (const ch of text) {
    if (ch === '\n') {
      await press(tabId, 'Enter');
      continue;
    }
    await cdp(tabId, 'Input.dispatchKeyEvent', {type: 'keyDown', key: ch, text: ch, unmodifiedText: ch});
    await cdp(tabId, 'Input.dispatchKeyEvent', {type: 'keyUp', key: ch});
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
  const {nodes} = await cdp(tabId, 'Accessibility.getFullAXTree', {});
  const byId = new Map(nodes.map((n) => [n.nodeId, n]));
  const refs = new Map();
  const lines = [];
  let counter = 0;
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
          refs.set('e' + counter, n.backendDOMNodeId);
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
  if (root) visit(root, 0);
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
  if (command === 'close') return {closed: false};  // the user's browser is never closed
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
  const tabId = await workTab(session);
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
      const {backendNodeId} = await node(tabId, rest[0]);
      await cdp(tabId, 'DOM.focus', {backendNodeId});
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
    case 'keyboard':
      if (rest[0] !== 'type') throw new Error(`unknown command: keyboard ${rest[0]}`);
      await typeText(tabId, rest[1] || '');
      return {done: true};
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
      const {backendNodeId} = await node(tabId, rest[0]);
      await cdp(tabId, 'DOM.scrollIntoViewIfNeeded', {backendNodeId});
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
