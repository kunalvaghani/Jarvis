// Keeps this adapter available only while a Gmail tab exists. No page data sent.
const port = chrome.runtime.connect({name: 'gmail-drafts'});
setInterval(() => port.postMessage({wake: true}), 10000);
