# Prompt22 web/app audit — 2026-10-16 IST

**18 catalog PASS /14 BLOCKED /0 FAIL /0 SKIPPED /0 NOT RUN.** [32 exact IDs](tests.jsonl). Baseline {'PASS': 25, 'FAIL': 0, 'SKIPPED': 0, 'seconds': 6.737}; combined focused {'PASS': 50, 'FAIL': 0, 'SKIPPED': 14, 'seconds': 67.729}; full tests-directory run {'PASS': 2855, 'FAIL': 0, 'SKIPPED': 48, 'seconds': 532.419}. Focused evidence combines the final47 PASS/7 skips and separately executed3 PASS/7 skips; full tests-directory run excludes the additional scripts/verification supplement. All executable assertions passed, while incomplete full-case contracts remain BLOCKED. [Commands](commands.txt), [full XML](full-regression.xml), [exact skips](full-regression-skip-reasons.json).

Actual existing trusted authored dashboard TypeScript/Vite build, owned temporary static previews, installed headless Chrome desktop/mobile/reduced-motion checks with project-local axe, deliberate overflow/dead-button failures, isolated mock remote API, Unicode DOM readback, cancellation/timeout and owned process cleanup. Five independent status sessions ×20 rounds use no model/GPU. Network/RAM/process faults and planner responses are fakes; these do not prove native memory pressure handling or arbitrary generated applications. No dependency installs, private account/browser-profile reuse, external sends, personal deletes, OS settings, native packaging, model downloads or publication. Build writes only the pre-existing authored acceptance artifact output; generated test projects and snapshots are owned temporary fixtures.

Supplemental executed readback: [actual Vite build served unchanged](built-preview-proof.json), [exact port3000 collision](port3000-proof.json). The first port supplement encountered a Windows temporary-file cleanup lock after process assertions; fresh owned retained fixture rerun passed. File cleanup was not retried and no unrelated state was removed.

| Claim | Real implementation / entry point | Evidence / boundary |
| --- | --- | --- |
| Development selection | Coder.run checks configured backend before legacy development.run; detect_stack/scaffold belong to staged workflow | Configured jarvis uses codex_workload/native and its own checks; these legacy staged browser checks are not automatically applied to every native task. Explicit development_* tools remain registered separately in agent_tools |
| Design/generation | design spec→bounded plan→≤3 files/batch; scoped paths and existing approvals | Baseline batch/cancellation/path assertions; no model-generated app acceptance in this audit |
| Tool registration | development_api.TOOLS→execute; task folder/TaskState and _approve | Status read-only; start/build/install require caller execution approval; forged planner feedback rejected |
| Dependency/build | DevelopmentTools.install/build | Existing npm ci versus reviewed install/hook/source guards; actual installed tsc/Vite ran; no dependency change/install |
| Port/lifecycle | start_preview selects OS port, loopback bind and strictPort; OwnedJob | Actual occupied-port/owned-stop fixture; no unrelated process kill; released-port bind race remains a fail/pause risk |
| Browser admission | tools.inspect exact project/url; development_browser.preview_url | Credential-free root http127.0.0.1:port only; query/fragment/path rejected before browser work without echoing fake secret |
| Auth/network | isolated one-shot Chrome context per view | permissions empty, downloads disabled, service workers blocked; external HTTP blocked and all WebSockets closed; no real account context |
| Browser proof | validate_tests→finite step actions→axe/layout/keyboard/console/scenarios | Strict bounded names/values/counts/JSON; actual dead button/overflow fail; ≥3 assertions and interaction required; screenshots alone not proof |
| Recovery | main watchdog development preview→healthy/repair; stop/close | Failed owned process stops and records status, requires continuation; no automatic build/install/server/click replay |
| Learning | development_learning.record/recall fingerprint | Incomplete or stale code cannot become verified success; versions/framework scope retained |
| Health performance | DevelopmentTools._opener under existing RLock | Reuses proxy-free opener; no per-call construction; network still serialized under lock, not an event-loop latency guarantee |

- **JRV-22-002 BLOCKED:** Production preview uses Vite preview/Next start/exported static files, not a development HMR lifecycle.
- **JRV-22-004 BLOCKED:** Exit status and raw build diagnostics exist; no benign-versus-regression warning classifier.
- **JRV-22-008 BLOCKED:** Watchdog stops owned failed preview and requests explicit continuation; no safe automatic restart contract. Project/server code can have side effects, so it is not silently replayed.
- **JRV-22-010 BLOCKED:** Browser contexts isolate cookies/storage and permissions; project build/server code still runs as host user without filesystem confinement.
- **JRV-22-011 BLOCKED:** Reviewed install/lock guards exist; no reproducible dependency-upgrade API-break compatibility oracle.
- **JRV-22-019 BLOCKED:** Owned child jobs stop on exit; no durable preview crash-resume protocol.
- **JRV-22-032 BLOCKED:** Raw build/browser logs may contain credentials; complete credential-redacted trace contract missing.
- **JRV-22-018 BLOCKED:** Stop/timeout smoke checks do not prove consistent TaskState cancellation during planning and readback.
- **JRV-22-021 BLOCKED:** Token URL refusal does not prove the complete fake-cloud/private-context/log-redaction contract.
- **JRV-22-023 BLOCKED:** Explicit one-file scope does not prove positive-versus-negative development-intent execution semantics.
- **JRV-22-025 BLOCKED:** Injected MemoryError stops launch, but RAM/GPU admission and core-command responsiveness under pressure are unproved.
- **JRV-22-026 BLOCKED:** Repair avoids restart; durable identical-event and uncertain-write deduplication across the complete flow is unproved.
- **JRV-22-027 BLOCKED:** Health microbenchmark is measured; full development request cold-start/RSS/VRAM benchmark is absent.
- **JRV-22-030 BLOCKED:** Pre-launch faults/dead-process checks do not prove active-worker disconnect recovery with durable task provenance.

Read system-map, web-app-development, relevant native guide, linked tooling/build/preview runners and real registration/callers; historic2026-10-02 model/fixture claims remain dated. Branch **audit/12-tool-registry**, HEAD **9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6**, inherited Prompt21/user diffs preserved. No audit commit or checkout reset; before-image snapshots isolate this module. Order: source/contract trace→baseline→reproduction→small fixes→upstream→A/B→owned build/browser/fault assertions→frozen full/readiness→catalog/docs. [Environment](environment.json), [changes](changes.md), [compatibility](compatibility.md), [rollback](rollback.md).

Health-check overhead warm p50/p95 **0.38605/0.39860 → 0.01765/0.01930 ms**; peak traced allocation **7319 → 2352 bytes**. Same fake HTTP200 response and active/dead/closed assertions;25 calls/version in one process. Five initial calls are not fresh-process cold starts. Imports/construction/network/browser/build/GPU excluded. Cached opener retains per-instance memory and moves construction to instance startup; no end-to-end speed or VRAM claim. [Raw samples](benchmarks.csv), [scope](benchmark-summary.json).

![Actual headless Chrome capture of hand-written owned test page](fixture-desktop.png)

Actual1440×1000 headless Chrome fixture screenshot, not Jarvis UI or a model-generated website. Hand-written local markup, no third-party artwork. [Mobile](fixture-mobile.png), [reduced motion](fixture-reduced-motion.png). Screenshots accompany executable DOM/axe assertions; they are not independent functional proof.
