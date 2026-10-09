// Local token is generated into the ignored installation directory, never Git.
importScripts('local-config.js');
let polling = false;
async function tick() {
  if (polling) return;
  polling = true;
  try {
    const headers = {'Authorization': 'Bearer ' + JARVIS_LOCAL_TOKEN};
    const response = await fetch('http://127.0.0.1:29923/job', {headers, cache: 'no-store'});
    if (!response.ok) return;
    const job = await response.json();
    if (!job.id) return;
    let result;
    try {
      const windows = await chrome.windows.getAll({populate: true});
      const tabs = windows.filter(w => w.focused).flatMap(w => w.tabs || [])
        .filter(t => t.active && /^https:\/\/mail\.google\.com\//.test(t.url || ''));
      if (tabs.length !== 1) throw new Error('Select Gmail in the foreground Chrome window.');
      const tab = tabs[0];
      const pending = await chrome.storage.session.get('uncertainDraft');
      if (job.request.operation === 'draft' && pending.uncertainDraft)
        throw new Error('A previous Compose operation needs inspection/resume; no duplicate dispatched.');
      if (job.request.operation === 'draft') await chrome.storage.session.set({uncertainDraft: true});
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['gmail-content.js']});
      const output = await chrome.scripting.executeScript({target: {tabId: tab.id},
        func: request => globalThis.__jarvisGmailDrafts.handle(request, async () => {
          const result = await chrome.runtime.sendMessage({type: 'verify-gmail-focus'});
          if (!result?.valid) throw new Error('Gmail tab/window lost focus; no further mutation.');
        }), args: [job.request]});
      if (output.length !== 1) throw new Error('Gmail frame selection changed.');
      result = {result: output[0].result};
      if (result.result?.subject_verified && result.result?.body_verified &&
          ['draft','resume_draft'].includes(job.request.operation))
        await chrome.storage.session.set({uncertainDraft: false});
    } catch (error) { result = {error: String(error.message || error)}; }
    await fetch('http://127.0.0.1:29923/result', {method: 'POST', headers: {...headers, 'Content-Type': 'application/json'},
      body: JSON.stringify({id: job.id, adapter_hash: JARVIS_SOURCE_HASH, ...result})});
  } catch (_) { /* No host running is normal. Never retry a dispatched action. */ }
  finally { polling = false; }
}
chrome.action.onClicked.addListener(() => { tick(); });
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.type !== 'verify-gmail-focus') return;
  chrome.windows.getAll({populate:true}).then(windows => {
    const selected = windows.filter(w=>w.focused).flatMap(w=>w.tabs||[]).filter(t=>t.active);
    reply({valid:selected.length===1 && selected[0].id===sender.tab?.id && /^https:\/\/mail\.google\.com\//.test(selected[0].url||'')});
  }).catch(()=>reply({valid:false}));
  return true;
});
chrome.runtime.onConnect.addListener(port => {
  if (port.name === 'gmail-drafts') { tick(); port.onMessage.addListener(() => tick()); }
});
setInterval(tick, 500);
tick();
