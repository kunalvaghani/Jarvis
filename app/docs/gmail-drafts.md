# Gmail drafts in existing Chrome

## Implemented flow — 2026-10-09 IST

Jarvis clicks **Compose once**, then fills **Subject** and the message body. It
fills **To only if the user provides a recipient**. Without one, To stays blank;
it does not ask for an address just to create a draft. No project folder is needed.
Sending, attachments and inbox reading are disabled in this adapter.

The user's reference screenshots show an expanded compose panel alongside an older
minimized panel. The adapter preserves older minimized drafts and identifies the
one newly created dialog. If an expanded draft exists, inspect it and resume only
its exact identity and expected unchanged content. Do not replay an uncertain
Compose or write. No private mailbox screenshots are copied into documentation.

Windows accessibility did not reliably activate Gmail's custom controls in prior
live trials. The reviewed [Chrome extension](../integrations/gmail-chrome/manifest.json)
operates on the actual named DOM fields in the existing logged-in Chrome profile.
It does not import cookies, copy profiles, ask for credentials or use SMTP. Jarvis
shows its disposable cue during dispatch; DOM operations do not move the user's
mouse. The cue illustrates the operation, rather than acting as another hardware
mouse device.

## One-time local setup

1. Run [launchers/Setup Jarvis Gmail.cmd](../launchers/Setup Jarvis Gmail.cmd). This is already run
   for the current workspace. It prepares `.jarvis-runtime/gmail-extension/` with
   a random local transport token. This entire installation remains ignored by Git.
2. In the user's logged-in Chrome profile, open `chrome://extensions`, enable
   Chrome's Developer mode, click **Load unpacked**, and choose that directory.
   These are [Chrome's supported unpacked-extension steps](https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world#load-unpacked).
   Chrome's Developer mode is distinct from the Windows setting for symlink creation.
3. Reload the existing Gmail tab and leave Gmail selected in the foreground Chrome
   window. The small content-script heartbeat keeps the extension worker available
   while Gmail exists. It does not transmit page content during idle polling.
4. Complete the authorized `Jarvis skill test` subject/body draft readback, with no
   recipient and nothing sent. Only then refresh the passing validation record and
   restart Jarvis with the enabled capability. Until this actual check passes,
   Gmail remains absent from the active task catalogue.

### Live validation completed — 2026-10-09 IST

The user loaded the reviewed local extension. Jarvis's own worker clicked Compose
once and filled only `Jarvis skill test` into subject and body, with no recipient.
[Immediate independent request readback](../artifacts/reports/gmail-adapter-live.json)
passed. The draft was subsequently minimized; the user expanded that same draft,
and [delayed readback](../artifacts/reports/gmail-adapter-delayed-readback.json) confirmed
the unchanged subject/body and blank recipient. No duplicate was created and
nothing was sent. Minimized drafts must be expanded before field verification.

The worker now avoids resizing an already visible Chrome window and avoids
redundant UIA focus calls on a foreground window. Its draft cue does not use the
shared mouse. The current [skill validation](../artifacts/reports/utility-validation.json)
includes the live Gmail readback. A [real Qwen task](../artifacts/reports/gmail-task-routing.json)
selected Gmail inspection from the normal catalogue and executed through Jarvis's
regular dispatcher in 49.812 seconds. This proves inspection routing, rather than
a new spoken drafting task or email delivery. Gmail is enabled; sending, attachments
and inbox reading remain disabled.

Final regression after the host-window corrections passed **1,279 tests in
262.679 seconds** ([log](../artifacts/logs/utility-gmail-regression-final.log)). The
supervised owned desktop cursor check passed without shared-mouse movement, and
configured Ollama/LocalGithub readiness reports `ready`. These results do not
claim that the intentionally stopped microphone service was restarted.

After source changes rerun setup and reload the extension. The handshake checks
the current source hash; an older loaded adapter is rejected. If the local port is
occupied, setup or dispatch reports the problem; it never stops another process.
If Chrome suspends the adapter, click its toolbar icon and inspect the current
draft before trying a new operation.

## Permissions, lifecycle and checks

The extension requests scripting/tabs/storage permissions and host access to
`https://mail.google.com/*` and loopback HTTP. Its code uses only the authenticated
fixed endpoint `127.0.0.1:29923`. The Jarvis-owned UI worker opens that listener only
for its lifetime and closes it on shutdown. It checks the local token, host,
request identity, current adapter hash and bounded response size. A job is leased
once; a lost response cannot cause automatic redispatch. Uncertain draft creation
is retained in Chrome session storage across service-worker restarts.

Fresh foreground-window/tab checks precede mutation, including after the bounded
Compose wait. Exact subject/body and optional recipient values are read back.
Results contain verification flags and draft IDs, not private inbox or message
contents. The extension's isolated script world prevents website scripts from
directly calling its draft handler.

**Nine regression checks passed** against an actual owned browser fixture:
Compose once; blank To; exact optional recipient; subject/body readback; preservation
of older drafts; identity-specific resume with other drafts; changed-content
rejection; focus-loss cancellation; disabled send/attachments; folder-free native
schema; authenticated one-lease local transport. These are fixture/contract checks,
not a live Gmail pass. Full regression and current skill revalidation results are
recorded in [the utility validation document](utility-skills.md).

Implementation: [DOM adapter](../integrations/gmail-chrome/gmail-content.js),
[Chrome transport](../integrations/gmail-chrome/background.js),
[bounded local bridge](../jarvis/gmail_bridge.py),
[existing Gmail worker](../jarvis/gmail_chrome_worker.py),
[independent browser fixtures](../tests/test_gmail_drafts.py).
