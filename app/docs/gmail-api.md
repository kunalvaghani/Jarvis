# Gmail API — 2026-10-09 IST

> **Update 2026-10-10 IST:** Jarvis can now also send emails, send and delete drafts,
> move emails to Trash and restore them, apply labels, archive, mark read/unread/starred,
> group emails by sender and read emails aloud. See
> [Send, Trash, labels and speech](#send-trash-labels-and-speech--2026-10-10-ist).
> The older sections below are kept as the historical record for their dates.

Jarvis now has OAuth API tools for message search/read and draft creation/read/update.
They use the normal toolkit catalogue, task ranking, dispatcher and runtime approval.
The API is preferred over Chrome controls when connected. To is optional for drafts.
Messages are read without marking them read. Plain-text MIME bodies are returned;
HTML-only bodies become inert text, with no script execution or image/tracker
requests. Attachments are not downloaded. Email contents remain untrusted context.

## Connect locally

1. In Google Cloud, enable Gmail API, configure the OAuth consent screen for your
   project and add your own account as a test user if the app is in testing.
2. Create an OAuth client of type **Desktop app** and download its JSON locally.
   Follow [Google's Python setup guide](https://developers.google.com/workspace/gmail/api/quickstart/python).
3. Run [launchers/Connect Jarvis Gmail API.cmd](../launchers/Connect Jarvis Gmail API.cmd) and enter
   the local JSON path. It installs [optional OAuth dependencies](../requirements/gmail.txt),
   opens Google authorization and waits at most five minutes for local consent.
   The browser may ask you to select the intended account even if Chrome is logged in.
4. After Google authorization, the setup verifies the account API profile and
   writes a source-bound connection marker. Restart an intentionally stopped
   Jarvis only with approval so its workers reload the tool catalogue.

Client JSON stays at its local path; it is not copied into source. Tokens are
Windows DPAPI encrypted in ignored `.jarvis-runtime/gmail-api/token.dpapi` and
bound to the current Windows user. Do not commit downloaded client JSON or paste
its contents into chat. Google grants `gmail.readonly` plus `gmail.compose`:
compose also permits sending at Google's scope level, but Jarvis exposes no send
tool. These scopes are documented in [Google's scope reference](https://developers.google.com/workspace/gmail/api/auth/scopes).
Public distribution requires the applicable Google verification process; this
local setup does not imply a publicly verified OAuth application.

## Tools and verification

### OAuth testing access blocked — 2026-10-09 IST

The supplied local JSON passed Desktop-client and official-endpoint checks. The
first authorization attempt returned Google's **403 access_denied** page stating
that the application is in testing and available only to developer-approved testers.
No token or live API validation was obtained. In the same project as the OAuth
client, open **Google Auth Platform → Audience → Test users → Add users**, add the
exact account selected during authorization and save. Keep the app in Testing for
this local setup, then start a fresh connection attempt. Project ownership alone
does not put an account on the test-user allowlist. See [Google's audience guidance](https://support.google.com/cloud/answer/15549945?hl=en).
The original bounded local authorization listener expires after five minutes;
do not reuse an old consent URL after it expires. No error screenshots or OAuth
state/challenge parameters are published in this documentation. The user then
added the test account and completed fresh authorization successfully. This
initial block is resolved; the token stays Windows DPAPI encrypted locally.

| Tool | Parameters and use |
| --- | --- |
| `gmail_api_list` | content JSON `query`, optional `limit` (1–10), optional boolean `summaries`; default returns message IDs; summaries reads From/Subject/Date metadata and current unread status |
| `gmail_api_read` | exact message ID in value; returns headers/plain/HTML text using full MIME payload, without file attachment downloads |
| `gmail_api_draft` | content JSON `subject`, `body`, optional `to`; saves one draft |
| `gmail_api_list_drafts` | optional query and limit (1–10); returns matching draft IDs using Gmail search syntax |
| `gmail_api_read_draft` | exact draft ID in value; reads content and raw MIME SHA256 |
| `gmail_api_update_draft` | draft ID in value; complete replacement fields plus `expected_sha256` from inspection |

Writes request runtime approval, execute once and read back the saved draft.
Changed draft hashes cancel an update. Gmail does not provide atomic compare-and-set
for draft replacement, so simultaneous edits can still race; avoid editing that
draft elsewhere during an approved update. Existing CC/BCC or attachments block
replacement because this adapter cannot preserve them. Unknown network outcomes require fresh
inspection, never automatic retry. Sending, deletion, labels and attachments are
not implemented by this adapter. HTTP results have bounded size/deadlines;
sessions close after each operation. OAuth refresh failure asks for local reconnection.

Owned fixture tests cover MIME interoperability, optional recipient, changed draft
rejection, read-only behavior, approval/cancellation, header injection, no-send
policy, transport failure/no retry, response budgets and disconnected discovery.
These fixture checks are separate from the successful live API trial below and
the earlier Chrome draft trial.

Verification on 2026-10-09 IST: the full integration regression passed **1,287
tests in 287.269 seconds**. Subsequent HTML-only reading, draft listing, CC/BCC
preservation and API-read readiness changes passed **57 focused tests**, including
**12 Gmail API tests** ([focused log](../artifacts/logs/gmail-api-focused.log)). Local
Ollama/LocalGithub readiness is `ready`. The existing 42-utility recheck plus
supervised desktop fixture leaves **40 passing contracts / 37 active local skills**;
Chrome Gmail could not be revalidated while Google Cloud was selected and is
withheld by its current source-bound record. At that stage API consent was pending.
Jarvis remains intentionally stopped; no new microphone trial is claimed.

## Live account verification completed — 2026-10-09 IST

Fresh consent and the API profile check succeeded after the user added the test
account. The [live Jarvis toolkit trial](../artifacts/reports/gmail-api-live.json) passed:
exact test-subject search, message/draft reading, draft listing, one recipient-free
`Jarvis skill test` draft creation, and a hash-checked update with exact subject/body
readback. Nothing was sent. The local test checkpoint records uncertainty before
each write and blocks replay.

The first trial stopped before any write while inspecting unrelated large drafts.
The completed trial searched the approved test subject first and read only matching
drafts; response budgets remain enforced. No unrelated draft was edited. Published
evidence contains verification flags, not account addresses, tokens or private mail.

Connected-account regression checks exposed an ordinary draft-planning issue:
the external-write intent guard recognized sends but rejected explicitly requested
draft creation/update. The guard now recognizes those requests separately; actual
writes still require runtime approval. All **57 focused checks passed** after this
repair. The six API tools are connected and offered in the catalogue. They use the
OAuth-selected account, which may differ from Chrome's current account. Reconnect
locally to change accounts. Restarting deliberately stopped Jarvis needs approval.

The [actual Qwen routing trial](../artifacts/reports/gmail-api-routing.json) also passed in
39.922 seconds: it chose Gmail API search and the regular Jarvis dispatcher found
the approved test draft without writes. Earlier proposals chose an unfiltered draft
listing or omitted `in:drafts`; those were rejected before dispatch. At that stage
the local draft-list wrapper accepted only a limit; generic subject-search ranking
preferred message search. The later command repair adds the official draft-query
parameter and corrects the prior claim that Google's draft endpoint cannot filter.

The connected-account full regression passed **1,291 tests in 243.492 seconds**
([log](../artifacts/logs/gmail-api-connected-regression.log)). Subsequent final
search-routing/prompt corrections passed **78 focused tests**
([log](../artifacts/logs/gmail-api-final-focused.log)). Configured service readiness is
`ready`; all six API tools are connected, and utility source fingerprints remain
current. These checks are separate from a new spoken end-to-end email task.

Implementation: [adapter](../jarvis/gmail_api.py), [local OAuth setup](../scripts/setup/connect_gmail_api.py),
[tests](../tests/test_gmail_api.py), [send/Trash/label tests](../tests/test_gmail_actions.py).

## Unread email repair — 2026-10-09 IST

The recorded `find my unread emails` task paused after proposing
`application_search gmail` repeatedly. The email intent pattern missed plural
`emails`; native next-step guidance still preferred Chrome, and the command
parser did not recognize the exact phrase. All three paths are corrected.
The existing no-repeat recovery guard remains enforced.

Try these spoken or typed commands after loading the updated Jarvis:

- `Jarvis, find my unread emails`
- `Jarvis, show unread emails`
- `Jarvis, list my unread Gmail emails`

These exact, simple requests use the [read-only workflow](../jarvis/gmail_workflows.py)
through the standard toolkit policy/dispatcher. They search `is:unread`, fetch at
most five From/Subject/Date metadata records and return sender/subject summaries.
More results are explicitly noted; this is not an exhaustive mailbox count.
Messages changed to read by another client during the search are not reported as
currently unread. An empty search completes successfully. Extra filters, body
reads, reply/write requests and multi-action goals are not silently discarded;
they retain normal planning. Try `Find my unread emails from the last seven days
using Gmail API. List sender and subject only.` for a filtered planner task.

API metadata uses Google's valid `format=metadata` with selected headers, not the
invalid `format=snippet` from the supplied helper. The helper's broad permissions
for unrelated Google services, plaintext token storage and direct send operation
were not adopted. Existing Gmail scopes and encrypted credentials remain in use.
See [message formats](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)
and [search syntax](https://developers.google.com/workspace/gmail/api/guides/filtering).

Because adapter activation is source-bound, reviewed updates require an explicit
profile verification. Run `.venv\Scripts\python.exe -m scripts.setup.connect_gmail_api
--verify-existing` from the application directory to verify the current adapter
using an existing encrypted token, without new consent or mailbox writes.
This maintenance command is never automatic recovery. A failed profile check
does not certify the changed source; reconnect locally if authorization expired.

Fixture checks cover routing, parser matching, read-only dispatch, bounded metadata,
identity mismatch, cancellation, missing API/task scope, empty/raced results,
explicit profile verification and no replay. Verified unread results use a trusted
completion type: an email subject containing `paused` or `stopped` cannot pause
the successful task. Genuine failure replies still retain paused status.
During read-only validation, the original paused task and deliberate stop marker
were preserved. Restarting the microphone required approval. No fresh spoken
email-task result is claimed.

The [live unread trial](../artifacts/reports/gmail-unread-live.json) passed through command
parsing, normal Actions task handling, Brain.run and standard API dispatch in
**2.953 seconds**. An independent guard permitted only GET requests and verified
`is:unread` plus metadata-only reads; the existing task-state file remained
byte-for-byte unchanged. No mailbox write or screen/model inference was used for
the exact task. A separate real Qwen proposal correctly selected API search with
`is:unread newer_than:7d` and summaries in **38.579 seconds**; that filtered proposal
was checked without mailbox dispatch. These timings are distinct from speech
recognition/playback and from regression/readiness checks. Published evidence
contains flags and timings, not private email IDs, addresses, headers or bodies.

Final [regression log](../artifacts/logs/gmail-unread-regression.log): **1,291 tests ran
in 226.123 seconds; OK with one skipped test class**. The actual repository
isolation class was skipped because Docker's Linux engine was unavailable; those
live sandbox checks are not claimed by this run. Configured launcher
readiness is `ready`; the API connection marker and existing utility validation
source fingerprints are current. The new workflow has a current recovery source
snapshot. These regression/readiness checks are separate from the live API trial
and do not establish spoken microphone completion.

After final checks, the user explicitly approved restarting Jarvis. The
[startup check](../artifacts/reports/gmail-unread-startup.json) passed: running/listening,
healthy microphone capture and decoder, live action/question/speech workers and
the locally connected API. All six API tools are available in a fresh catalogue.
The normal approved bootstrap cleared the stop marker. The unfinished task remains
retained; it was not automatically replayed. Say `Jarvis, find my unread emails`
for a fresh spoken trial with the updated code.

## Gmail command workflows — 2026-10-09 IST

The latest recorded draft request spent roughly 90 seconds in next-step inference
before cancellation, without an API write. All recognized mail operations now use
the [Gmail domain workflow](../jarvis/gmail_workflows.py) before desktop planning.
Gmail is not searched as a desktop app. The supplied helper's OAuth/REST approach
is reused through the existing shared authenticated [API adapter](../jarvis/gmail_api.py).
Its unrelated Google service scopes, plaintext token file, invalid `snippet` format
and immediate send function are not adopted. No new dependency or permission is
needed for these Gmail operations.

Try these commands after loading the updated code:

- `Draft an email with subject "Meeting tomorrow" and body "Can we meet tomorrow at 3 PM?" Leave the recipient blank.`
- `Write an email to person@example.com with subject "Meeting" and body "Can we arrange a meeting?"`
- `Write an email about arranging a meeting tomorrow; leave the recipient blank.`
- `Read my latest email`
- `Find my unread emails`, followed by `Read the first email`
- `Read the email with subject "Meeting tomorrow"`
- `List my Gmail drafts`
- `Read the Gmail draft with subject "Meeting tomorrow"`
- `Update the Gmail draft with subject "Meeting tomorrow" to have body "Let's meet at 4 PM."`
- `Change the Gmail draft with subject "Meeting tomorrow" to have subject "Meeting at 4 PM"`

Literal field commands skip model inference. More natural requests use a single
typed local Qwen text interpretation, with no screenshot, historical mail or tool
execution. Topic-based writing has separate composition rules: a topic/purpose
is sufficient to write subject and body, while quoted text stays literal. Missing
required targets ask a question; optional recipients stay blank. Addresses are
never guessed from names. Unsupported sending, forwarding, deletion or label
changes return a clear limitation rather than falling back to screen control.
Received/sent emails cannot be edited; updates apply to drafts.
The separately configured SMTP sender retains its existing generic email-send
planning and approval path; this does not add sending to Gmail API. Its unchanged
dispatch regression caught and verified a correction to the new mail routing.

Message selection uses actual returned IDs. Ordinals refer to the latest results
in the current action-worker session; after a restart, list again before choosing
an ordinal. Subject-targeted reads and updates require a unique exact subject,
not the first partial match. The draft endpoint supports `q`, as documented by
[Google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/list).
Partial updates preserve unspecified subject/body/recipient fields. An unchanged
HTML body retains its original MIME payload during header edits; explicitly
replacing a body creates the requested plain-text body. CC/BCC, named file
attachments and unsupported recipient shapes remain guarded limits.

Message-body reads use full MIME payloads and only textual parts, with inert HTML
conversion. Named file attachments are skipped. An ordinary textual body stored
as a Gmail attachment resource may be read; that is distinct from downloading a
file attachment. Decoding has bounded size/structure, and truncated text is
explicitly labelled. Mail is not marked read, and mail content cannot authorize
tools or change the task's trusted completion status.

Approved writes use a [durable journal](../jarvis/gmail_writes.py) under ignored
`.jarvis-runtime/gmail-api/writes/`. It stores a hashed request identity, pending
state and actual draft ID, not body/subject text. An uncertain write remains
blocked across callers/restarts, including after the expected inspection hash
changes. Inspect the recorded draft before any new write; do not delete a pending
marker to force a retry. Denied approvals create no uncertain-write marker. Writes
are never automatically replayed. Subject/body readback and stale-hash checks
remain mandatory; compare-and-set races at Google remain a known limitation.

The initial real topic-composition check asked the user to supply a body because
shared desktop-planner rules conflicted with writing a draft. The interpreter now
uses dedicated email-writing rules. The corrected [read-only command trial](../artifacts/reports/gmail-command-read-live.json)
passed draft reading, message-body reading and actual Qwen composition without
mailbox writes or task-state changes. The [existing approved test update trial](../artifacts/reports/gmail-command-existing-update-live.json)
passed normal command parsing/Actions/Brain/API dispatch: draft read **1.891 s**,
message-body read **1.593 s**, update/readback **4.797 s**, and a separate real Qwen
topic interpretation **26.719 s**. Only the original recipient-free `Jarvis skill
test` draft was updated, with its exact subject/body retained. Nothing was sent.
Creation for the new command path is fixture-tested; a new live test draft needs
the separately requested approval. These checks are separate from a fresh spoken
task and from regression/readiness checks. After final checks, the user chose to
keep Jarvis stopped. Its deliberate stop remains in place; no fresh microphone
startup or spoken Gmail completion is claimed for this command repair. The new
workflow loads on the next user-initiated start.

Final [command regression log](../artifacts/logs/gmail-commands-regression.log):
**1,308 tests ran in 213.031 seconds; OK with one skipped test class**. The live
repository isolation class was skipped because Docker's Linux engine was
unavailable; this run does not claim those isolation checks. The unchanged
configured-tool suite passed all 32 checks after fixing the SMTP routing
regression, and the Gmail command suite passed all ten checks. API MIME/body,
approval, stale-hash and uncertain-write journal checks are included in the full
run. These are regression checks, separate from the live API evidence above.
Final configured launcher readiness is `ready`, with the required Ollama models
and local Git service available. The reviewed Gmail adapter connection remains
current, and the updated runtime imports have recovery source snapshots. This
check does not start the deliberately stopped microphone or replay its task.

## Send, Trash, labels and speech — 2026-10-10 IST

Gmail is now fully voice-driven through the same [API adapter](../jarvis/gmail_api.py)
and [command workflow](../jarvis/gmail_workflows.py). Earlier refusals of sending,
deletion and label changes are replaced by these approved operations:

| Tool | Parameters and use |
| --- | --- |
| `gmail_api_send` | content `to`, `subject`, `body`, optional `cc`; exact addresses, up to 10 each, comma separated |
| `gmail_api_send_draft` | draft ID in value; `expected_sha256` from `gmail_api_read_draft`; the draft must have a recipient |
| `gmail_api_delete_draft` | draft ID in value; `expected_sha256`; permanent draft deletion |
| `gmail_api_trash` / `gmail_api_untrash` | content `ids` (1–25 observed IDs) and optional `preview` lines; Trash is recoverable for 30 days |
| `gmail_api_modify_labels` | content `ids`, `add`, `remove`, optional `preview`; label names or `INBOX`, `UNREAD`, `STARRED`, `IMPORTANT`; missing user labels are created |
| `gmail_api_list_labels` | read-only label names |

`gmail_api_list` now accepts `limit` 1–25 so grouping and bulk changes can see
more than ten messages. "Delete" always means Trash; Jarvis never permanently
deletes received mail. Replying and forwarding are still not supported.

### Spoken commands

- `Send an email to name@example.com with subject "Lunch" and body "Are you free at noon?"`
- `Send an email to name at gmail dot com asking about lunch tomorrow` (speech-style
  addresses are rewritten to `name@gmail.com`; Qwen composes subject and body)
- `Send the draft with subject "Lunch"` / `Send the last draft`
- `Read aloud my latest email`, `Speak the first email`, `Tell me my unread emails`
- `Delete the latest email`, `Delete the email with subject "Invoice"`,
  `Delete all emails from news@example.com`
- `Restore the email with subject "Invoice"`
- `Mark the first email as read`, `Mark all unread emails as read`, `Star the second email`
- `Archive the latest email`
- `Label the first email as Receipts`, `Move the latest email to Work`
  (move also removes it from the inbox), `Move all emails from bank@example.com to Finance`
- `Group my emails by sender`, `List my Gmail labels`
- `Delete the draft with subject "Old notes"`

Literal phrases parse locally. Looser phrasing uses the existing single local Qwen
text interpretation with a wider operation schema. Recipients and label names must
appear in what you said; Jarvis never guesses an address from a name. Ordinals
(`first`, `second` and so on) refer to the most recent list in the current session.
Speaking renders the sender's display name, subject and body without quoted reply
history, capped for playback; the full text stays in the transcript.

### Safety

Every send, Trash, restore, label and draft deletion shows the Jarvis approval card
before anything is changed. Approval is a click in the Jarvis window; there is no
spoken approval. Bulk changes are limited to 25 messages under one approval, and the
card lists each sender and subject. Each write is recorded in the durable
[no-replay journal](../jarvis/gmail_writes.py) and verified by readback (SENT label
and subject for sends, TRASH or label state per message). An uncertain or partial
result is reported, never retried. Draft send/delete re-check the draft hash.

The OAuth scopes now add `gmail.modify` (Trash and labels) to `gmail.readonly` and
`gmail.compose`. Existing tokens without it must be reconnected once with
[launchers/Connect Jarvis Gmail API.cmd](../launchers/Connect%20Jarvis%20Gmail%20API.cmd).
Tokens remain Windows DPAPI encrypted. See [Google's scope reference](https://developers.google.com/workspace/gmail/api/auth/scopes).

### Verification — 2026-10-10 IST

- Reconnection with the added scope completed locally. The adapter source binding was
  reverified with `--verify-existing`.
- **Live feature check:** the [live actions trial](../artifacts/reports/gmail-actions-live.json)
  ([script](../scripts/verification/verify_gmail_actions_live.py)) passed through real
  command parsing and Actions/Brain/API dispatch on the connected account: send to
  the account's own address, read aloud, mark read, star, label (with label creation),
  move, list labels, group by sender, Trash, restore, draft create plus send, and
  draft create plus delete. Its approval handler accepted only mail carrying that run's
  unique subject tag. Test mail was moved to Trash afterwards and the test label removed.
  14 mailbox writes; per-command times were 1.2–4.1 s, and 11.8 s for grouping 25 messages.
  A separate real Qwen interpretation of natural send and move requests passed in 61.5 s.
  An initial run stopped before any write on a workflow bug (tool discovery returned
  rows, not names). A read-only search confirmed nothing was sent; the bug was fixed
  and covered by a fixture.
- **Fixture tests:** [test_gmail_actions.py](../tests/test_gmail_actions.py) adds 19 tests
  for the adapter and spoken commands. They cover recipient and header validation,
  unverified-send reporting without resend, draft hash and recipient checks, per-message
  readback, approval denial and cancellation, the journal for every write tool, the
  deferred-discovery cap and interpreter label and operation checks.
- **Regression:** the full suite ran **1,334 tests in 200.313 s, OK with one skip**
  ([log](../artifacts/logs/gmail-actions-regression.log)). The skipped class is live
  repository isolation, because Docker's Linux engine was unavailable. Launcher
  readiness is `ready`. After the live trial, only the planner write-intent pattern for
  the two send tools changed; it is covered by the regression run.
- Jarvis was not running during these checks. No spoken microphone trial is claimed.
  The new commands load on the next start.
