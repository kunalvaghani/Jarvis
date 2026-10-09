# Curated utility skills

This update reviews all **42 skills** in the two supplied code lists. Supplied code
is reference material: Jarvis uses reviewed adapters, corrected contracts and its
existing planner, dispatcher, approvals, project scope and cancellation. It does
not import pasted source or install a second autonomous agent.

## Status — 2026-10-09 IST

The latest [individual results](../artifacts/reports/utility-validation.json) distinguish
actual local execution from HTTP mock-service tests. At this stage 41 of 42 passed.
Of those 41, 38 have actual local checks and three messaging adapters have only
mock-service contracts. The three messaging adapters remain inactive until live
account/destination validation is explicitly authorized. Gmail draft completion
now has live verification; Windows symlink creation remains disabled for missing
Windows privilege. A passed row is offered only while its recorded
source hashes match the current adapters and dispatch policy. Changes invalidate
activation. These checks are not a blanket production certification.

The [natural-language routing results](../artifacts/reports/utility-routing.json) exercise
actual local Qwen proposals, the regular discovered catalogue, Brain dispatch,
independent file/data assertions and a subsequent completion proposal. They are
separate from voice and full desktop workflow validation. Historical failed trials
are retained locally rather than relabelled as passes.

All four general-language tasks passed: machine memory/disk diagnostics (107.250 s),
CSV missing-data profiling (50.141 s), YAML syntax validation (42.109 s), and image
conversion/resizing (71.125 s). Each used the normal catalogue and an independent
result assertion before the completion proposal. The full regression suite passed
**1,265 tests in 260.140 seconds** on this date. These timings are observed trials,
not latency guarantees.

After these checks, [Jarvis restarted successfully](../artifacts/reports/utility-restart.json)
with live microphone capture/decoding, healthy action/question/speech workers,
current recovery source snapshots and 37 enabled local utility skills. Configured
service readiness reports `ready`; this checks local Ollama and LocalGithub's local
Git mode, not hosted GitHub services or a new spoken end-to-end task.

## Planner and email repair — 2026-10-09 IST

The recorded request `draft an email about me` failed after 72.219 seconds with
`Native planner must propose exactly one tool call`. Native next-step inference
was receiving both the text-plan JSON contract and the function-call contract.
The native branch now uses a dedicated function-call prompt, while the existing
JSON branch retains its own contract. One bounded inference-only format correction
now applies to ordinary tool catalogues as well as utility catalogues. Transport
failures and truncated replies are not retried; no actions are replayed.

Gmail intent now selects the form guidance and prioritizes the validated Chrome
adapter when available. A direct email task requiring the absent Gmail adapter
returns a readiness question before speculative model inference; this does not
block coding an email-related program. It does not invent personal facts, ask for
SMTP passwords, substitute the isolated browser or claim an email was created.
App-opening guidance also distinguishes `open chrome` from website navigation.

The [reported-request checks](../artifacts/reports/email-planner-repair.json) passed:
the email readiness question returned in 1.329 seconds without inference or
dispatch, and actual Qwen selected `open` for Chrome in 26.906 seconds. These are
proposal/readiness checks, not evidence that Gmail drafting works. A first real
model trial still guessed an unavailable tool; the readiness guard addresses that
case. A separate trial chose website navigation for the application name; the
corrected guidance passed the unchanged app-launch oracle.

The full regression run after the initial prompt/format repair passed **1,267
tests in 303.019 seconds**. Later Gmail readiness/routing and final guidance
changes received focused checks: **21 native planner tests and 13 capability
tests passed**. All 42 owned skill fixtures were rerun against the repaired native
parser; the supervised cursor recheck passed after the automatic foreground trial
timed out. Current source-bound activation remains 37 local skills / 40 passing
contracts, including three inactive mock-only messaging contracts.

In the earlier native-control trial, Gmail's minimized test draft did not respond observably to the
available controls. Computer Use also produced no observable click/key result in
Chrome. No recipient was added and nothing was sent. Manually expanding that
existing draft was required for that trial; no duplicate draft
was created automatically. The later Chrome adapter passed the live checks below.
Jarvis has a newer intentional stop marker and remains
stopped pending restart approval for this repair. The earlier restart evidence
above describes the preceding skill rollout.

## Setup and configuration

1. Run [launchers/Setup Jarvis Utilities.cmd](../launchers/Setup Jarvis Utilities.cmd) after normal
   Jarvis setup. It installs [requirements/skills.txt](../requirements/skills.txt)
   into `.venv-skills`, preserving the speech environment. The current installed
   [package versions](../artifacts/reports/utility-package-versions.json) are recorded.
2. For Nmap and notebooks, start Docker Desktop's Linux engine and build the
   reviewed image with `docker build -t jarvis-utility-runtime:1
   integrations/utility-runtime`. The runner selects the inspected immutable image
   ID and checks the image label/OS/architecture. There is no host execution fallback.
3. OCR needs a locally installed Tesseract executable on PATH. FFmpeg comes from
   the reviewed `imageio-ffmpeg` runtime. Audio transcription uses the existing
   offline Whisper checkpoint in a bounded CPU worker, at most 120 seconds of audio.
4. Optional MongoDB requires `JARVIS_MONGODB_URI`; Redis uses
   `JARVIS_REDIS_HOST`, `JARVIS_REDIS_PORT`, `JARVIS_REDIS_PASSWORD`. Slack uses
   `JARVIS_SLACK_WEBHOOK_URL`, GitHub uses `JARVIS_GITHUB_TOKEN`, and Twilio uses
   `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`. Configure
   secrets locally; never commit them or put credentials into task prompts.
   Provider SDK jobs inherit only the credentials required for that service.
   Credentials alone do not activate a mock-only adapter; request an explicitly
   authorized live destination/content test first.
5. Revalidate with `.venv\Scripts\python.exe -m scripts.verification.verify_utility_skills`, inspect the
   results, then restart Jarvis to load the passing catalogue. Failed skills stay
   out of the active catalogue. Missing provider configuration is reported by
   toolkit status and omitted from configured task discovery.

Gmail uses the current logged-in **Google Chrome** session. Its new
[local draft adapter](gmail-drafts.md) implements Compose once, optional To, and
exact Subject/body entry, without a filesystem folder. Older minimized drafts are
preserved; expanded drafts require exact identity/content resume. No profiles,
cookies, passwords or SMTP credentials are copied. Sending, attachments and inbox
reading are disabled. The user loaded the reviewed local extension. Live Compose
and subject/body entry passed, with no recipient and nothing sent; delayed
readback of that same draft passed after the user expanded it. The worker avoids
unnecessary host resizing and foreground focus calls. Gmail is now active. Actual
Qwen selected and dispatched a read-only Gmail inspection task in 49.812 seconds.
See [live evidence and limits](gmail-drafts.md#live-validation-completed--2026-10-09-ist).
Nine actual owned-browser/transport checks passed. The preceding full suite
passed 1,279 tests in 248.105 seconds; the last empty-folder/socket-timeout changes
received a fresh nine-test focused run. The live checks cover recipient-free
drafting and inspection; optional recipient handling has owned-fixture coverage.

The final post-adapter regression passed **1,279 tests in 262.679 seconds**
([log](../artifacts/logs/utility-gmail-regression-final.log)). The 42-skill revalidation,
existing Gmail draft readback and supervised desktop cursor check leave **41
passing contracts and 38 active local skills**, with current source fingerprints.
Configured Ollama and LocalGithub readiness reports `ready`. Jarvis remains
intentionally stopped pending approval; these are not a new microphone/voice trial.

The Windows symlink test currently returns WinError 1314. Developer Mode or an
appropriate user privilege is a user setup decision; Jarvis does not elevate or
change Windows security settings. Desktop controls require a stable foreground
window and one fresh unique accessible control. Earlier automatic fixture trials
lost focus and correctly cancelled. The subsequent
[supervised owned native-button trial](../artifacts/reports/utility-desktop-live.json)
passed: its independently read file effect confirmed activation, with no movement
of the shared mouse and no automatic Enter. The desktop adapter is now activated;
this result does not validate every third-party application.

## When and how Jarvis chooses a skill

Natural task examples include “Check sales.csv for missing data in folder …”,
“Check whether settings.yaml has valid syntax in folder …”, and “Prepare image.png
as a smaller JPEG named small.jpg, 350 pixels wide, in folder …”. Specify the actual
project and named inputs/outputs. The planner discovers available tools, reads
their when/how guidance and supplies typed `arguments`, `folder` and `expected`.
The dispatcher translates the proposal to its existing step format; legacy steps
still use JSON `content`. Typed validation runs before approvals or execution.

Only inference may receive one bounded format correction, within the original
planning deadline. No tool, write, click or external request is replayed. Actual
results still need independent goal verification. Tool guidance is added to the
existing file, research, form and coding skills; no guide grants authority.

| Supplied skill | Jarvis tool and principal arguments | Verified scope / limitation |
| --- | --- | --- |
| Gmail dispatcher | `skill_gmail_chrome`: operation, subject/body/to | Live Compose and recipient-free draft/readback passed; actual Qwen inspection routing passed; sending/attachments disabled |
| Machine diagnostics | `skill_system_diagnostics`: folder | Actual CPU/RAM/project disk metrics |
| File encryption | `skill_file_crypto`: operation/source/output/key_id | Actual authenticated encrypt/decrypt round trip; local Windows DPAPI keys; original retained |
| Image processing | `skill_image_process`: source/output, width/height | Actual resizing/conversion; transparent JPEG uses white |
| Regex renaming | `skill_regex_rename`: pattern/replacement, dry_run | Actual safe rename; bounded regex, preflight collisions, no overwrite |
| Python formatter | `skill_format_python`: source | Actual Black formatting with unchanged AST |
| MongoDB | `skill_mongodb`: operation/database/collection/query/document/update | Actual insert/update/read in a disposable loopback MongoDB; user database not tested |
| TCP port checker | `skill_port_check`: host/port | Actual connection to owned loopback server |
| Persistent environment | `skill_env_set`: name/value | Actual unique HKCU value/readback/restoration; reserved system names refused |
| Git workflow | `skill_git_workflow`: branch/message/files, push/remote | Actual clean-index branch/stage/commit in owned repository; external push not live-tested |
| RSS | `skill_rss_fetch`: url/limit | Actual HTTP feed parsing; fetched text is untrusted context |
| Markdown PDF | `skill_markdown_pdf`: source/output/title | Actual ReportLab PDF; simple headings/paragraphs, no HTML execution or remote assets |
| ZIP extraction | `skill_zip_extract`: source/output/extension | Actual filtered extraction; traversal/link/bomb/collision checks |
| Clipboard | `skill_clipboard`: operation/text | Actual text write/read; original restorable formats restored |
| Calendar invite | `skill_calendar_ics`: title/start/end/output/description | Actual timezone-aware escaped/folded ICS; no cloud event |
| JSON/YAML validator | `skill_config_validate`: source | Actual syntax validation; unspecified schema not verified |
| Redis | `skill_redis`: operation/key/value/ttl | Actual empty-value set/get/delete in disposable loopback Redis |
| Local file server | `skill_local_server`: operation/port | Actual owned loopback-only serve/stop, no cwd change |
| Audio transcription | `skill_audio_transcribe`: source | Actual generated non-private speech and offline CPU Whisper, bounded owned worker |
| OS scheduler | `skill_os_schedule`: name/script/interval_minutes | Actual create/query/remove of a unique trusted fixture task; no force replacement |
| Nmap | `skill_nmap_scan`: target/ports | Actual TCP scan of the container's own loopback service; host/LAN deployment not live-tested |
| SSL | `skill_ssl_check`: host/port | Actual normal certificate chain/hostname/expiry verification |
| Security audit | `skill_security_audit`: folder | Actual Bandit finding; static analysis does not prove security |
| REST fuzzer | `skill_api_fuzz`: url/method | Four actual malformed requests to owned endpoint; no crash claim from status alone |
| JWT inspector | `skill_jwt_inspect`: token | Actual header/payload decode; signature unverified and never authorization |
| FFmpeg extraction | `skill_ffmpeg_audio`: source/output | Actual synthetic video to MP3, no overwrite |
| Subtitles | `skill_subtitles_srt`: segments/output | Actual ordered SRT with millisecond carry/rounding |
| OCR | `skill_ocr_image`: source | Actual Tesseract text recognition from synthetic image |
| EXIF removal | `skill_strip_exif`: source/output | Actual metadata-free image; original preserved |
| Notebook runner | `skill_notebook_execute`: source/output | Actual code/kernel output in non-root no-network reviewed container |
| CSV profiling | `skill_csv_profile`: source | Actual rows/null counts/statistics with bounded dataset |
| CSV to Parquet | `skill_csv_parquet`: source/output | Actual compressed Parquet file generation |
| Dynamic scraper | `skill_dynamic_scrape`: url | Actual Chrome JavaScript rendering on exact owned preview origin; public URLs use existing checks |
| Slack approval block | `skill_slack_approval`: message/fallback | HTTP mock contract only; accepted webhook is not granted approval; verified interaction endpoint is separate |
| GitHub PR comment | `skill_github_comment`: repository/number/comment | HTTP mock POST/readback only; PR conversation comment, not inline review |
| Twilio SMS | `skill_sms_send`: to/message | HTTP mock acceptance only; provider queue status does not prove delivery |
| Desktop controller | `skill_desktop_control`: control/text/field | Fresh unique-control guarded adapter; actual owned native-button effect verified, no shared mouse |
| Symlink | `skill_symlink`: source/output | Actual privilege failure, disabled; no elevation or shortcut substitution |
| Screenshots | `skill_screenshots`: output | Actual monitor capture; images remain ignored local runtime, never uploaded/published |
| Local LLM router | `skill_local_llm`: prompt | Actual existing Qwen backend and GPU admission; no missing llama3 dependency |
| Prompt inspector | `skill_prompt_inspect`: text | Actual advisory suspicious-pattern flag; regex is not a security boundary |
| Agent state | `skill_agent_state`: operation/state/output/source | Actual JSON save/load; arbitrary pickle loading removed |

## Ownership, limits and implementation

The implementation is split into [profiles](../jarvis/utility_profiles.py),
[permission-aware dispatch](../jarvis/utility_tools.py),
[local data operations](../jarvis/utility_core.py),
[service adapters](../jarvis/utility_services.py),
[host interfaces](../jarvis/utility_host.py),
[isolated execution](../jarvis/utility_isolation.py), and
[Gmail controls](../jarvis/gmail_chrome_worker.py). Jobs have deadlines/output
budgets and owned process cleanup. `Actions.close` closes only its own preview.
No recovery path changes permissions, restarts a deliberately closed user app or
retries an uncertain effect.

The notebook/Nmap utility image has a different contract from learned repository
skills: notebook kernels need child processes. It uses non-root, read-only root
and sole notebook input, no host home/credentials/Docker socket/GPU, bounded
512 MB memory, 64 PIDs, 0.5 CPU, 128 MB scratch and a 45-second outer deadline.
Notebook network is disabled. Approved production Nmap uses Docker bridge network
and a bounded private target/port contract. Docker shares its Linux kernel; this
is not a VM. Reviewed host utilities are trusted programs, not an arbitrary-source
sandbox. Whisper file transcription uses CPU to avoid competing with live speech;
Qwen retains the existing GPU priority scheduler.

Local fixture databases, APIs, scheduled tasks and GUI processes are uniquely owned
and cleaned up. Screenshot/audio fixtures and DPAPI keys remain under ignored
`.jarvis-runtime`. Logs are ignored. Reports contain fixture metadata and package
versions, not credentials or private desktop captures.

Primary implementation references: [Fernet](https://cryptography.io/en/latest/fernet/),
[Nmap host/port behavior](https://nmap.org/book/man-host-discovery.html),
[NBClient](https://nbclient.readthedocs.io/en/latest/client.html), and
[Gmail compose guidance](https://support.google.com/a/users/answer/9259846?hl=en).
