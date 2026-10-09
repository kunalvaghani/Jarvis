// Runs in Chrome's isolated extension world, never the website's script world.
if (!globalThis.__jarvisGmailDrafts) {
  const identities = new WeakMap();
  let uncertainCompose = false;
  function id(node) { if (!identities.has(node)) identities.set(node, crypto.randomUUID()); return identities.get(node); }
  function visible(node) { const r = node.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(node).visibility !== 'hidden'; }
  function dialogs() { return [...document.querySelectorAll('[role="dialog"]')].filter(d => visible(d) &&
    (d.querySelector('input[name="subjectbox"]') || /^Compose:|New Message/i.test(d.getAttribute('aria-label') || d.textContent.trim()))); }
  function field(dialog, selector) { const found = [...dialog.querySelectorAll(selector)].filter(visible);
    if (found.length !== 1) throw new Error('Gmail field is missing or ambiguous: ' + selector); return found[0]; }
  function fields(d) { return {subject: field(d, 'input[name="subjectbox"]'),
    body: field(d, '[contenteditable="true"][role="textbox"]'),
    to: field(d, 'input[name="to"],textarea[name="to"],input[aria-label="To recipients"]')}; }
  function recipients(d) { return [...d.querySelectorAll('[email]')].map(e => e.getAttribute('email')).filter(Boolean); }
  function select(request) {
    const all = dialogs();
    const matches = request.draft_runtime_id ? all.filter(d => id(d) === request.draft_runtime_id[0]) :
      all.filter(d => d.querySelector('input[name="subjectbox"]') && visible(d.querySelector('input[name="subjectbox"]')));
    if (matches.length !== 1) throw new Error('Inspect and select one expanded Gmail draft; other drafts are preserved.');
    return matches[0];
  }
  function setInput(node, value) {
    const proto = node.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(node, value);
    node.dispatchEvent(new Event('input', {bubbles: true}));
    node.dispatchEvent(new Event('change', {bubbles: true}));
    if (node.value !== value) throw new Error('Field readback failed; inspect before retry.');
  }
  function evidence(d, request) { const f = fields(d); return {
    draft_created: true, draft_runtime_id: [id(d)], subject_verified: f.subject.value === request.subject,
    body_verified: f.body.textContent === request.body, recipient_set: !!(f.to.value || recipients(d).length),
    sent: false, shared_mouse_used: false}; }
  async function handle(request, guard = async () => {}) {
    if (location.origin !== 'https://mail.google.com' || document.visibilityState !== 'visible') throw new Error('Gmail page is not visible; no input issued.');
    await guard(); // Chrome window/tab continuity, independent of omnibox focus.
    const operation = request.operation;
    if (operation === 'inspect' || operation === 'open') return {gmail_in_existing_chrome: true, compose_available: true,
      opened_existing_profile: true, create_tab_needed: false, credentials_copied: false,
      draft_runtime_ids: dialogs().map(d => [id(d)]), drafts: dialogs().map(d => ({runtime_id: [id(d)],
        expanded: !!d.querySelector('input[name="subjectbox"]') && visible(d.querySelector('input[name="subjectbox"]'))})), sent: false};
    if (operation === 'verify_draft') return evidence(select(request), request);
    if (!['draft', 'resume_draft'].includes(operation)) throw new Error('This adapter supports drafts only; sending is not enabled.');
    if (typeof request.subject !== 'string' || typeof request.body !== 'string' || request.subject.length > 200 || request.body.length > 10000 ||
        (request.to && !/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(request.to))) throw new Error('Provide exact subject/body and optional recipient.');
    if (request.attachments) throw new Error('Attachments are not supported; no draft mutation issued.');
    let d;
    if (operation === 'resume_draft') {
      if (request.to || !request.draft_runtime_id) throw new Error('Resume requires the inspected draft identity and no recipient.');
      d = select(request); const f = fields(d);
      if (f.subject.value !== request.expected_subject || f.body.textContent !== request.expected_body || f.to.value || recipients(d).length)
        throw new Error('Draft content/recipients changed; no overwrite issued.');
    } else {
      if (uncertainCompose) throw new Error('An earlier Compose outcome is uncertain; inspect before another creation.');
      if (dialogs().some(d => d.querySelector('input[name="subjectbox"]') && visible(d.querySelector('input[name="subjectbox"]'))))
        throw new Error('An expanded draft exists; inspect/resume it rather than create a duplicate.');
      const before = new Set(dialogs());
      const buttons = [...document.querySelectorAll('[role="button"],button')].filter(e => visible(e) &&
        (e.getAttribute('aria-label') === 'Compose' || e.textContent.trim() === 'Compose'));
      if (buttons.length !== 1) throw new Error('Compose must be uniquely visible.');
      await guard();
      uncertainCompose = true; buttons[0].click(); // Exactly one creation dispatch.
      const deadline = Date.now() + 4000;
      while (Date.now() < deadline) {
        const added = dialogs().filter(d => !before.has(d));
        if (added.length === 1 && added[0].querySelector('input[name="subjectbox"]')) { d = added[0]; break; }
        if (added.length > 1) break;
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      if (!d) throw new Error('Compose outcome uncertain; inspect before repeating.');
    }
    await guard();
    if (document.visibilityState !== 'visible' || !d.isConnected) throw new Error('Gmail changed after creation; inspect before retry.');
    const f = fields(d);
    if (f.subject.value || f.body.textContent || f.to.value || recipients(d).length) {
      if (operation !== 'resume_draft') throw new Error('New draft is not empty; no overwrite issued.');
    }
    setInput(f.subject, request.subject);
    f.body.textContent = request.body;
    f.body.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: request.body}));
    if (request.to) { setInput(f.to, request.to); f.to.dispatchEvent(new Event('blur', {bubbles: true})); }
    const result = evidence(d, request);
    if (!result.subject_verified || !result.body_verified || (!request.to && result.recipient_set) ||
        (request.to && f.to.value !== request.to && !recipients(d).includes(request.to)))
      throw new Error('Draft readback failed; inspect without replay.');
    uncertainCompose = false;
    return {...result, existing_draft_resumed: operation === 'resume_draft'};
  }
  globalThis.__jarvisGmailDrafts = {handle};
}
