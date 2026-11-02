# Adapter plan: legacy control to agent-desktop / agent-browser

Pinned versions: agent-desktop **1.0.2** (JSON envelope v2.5) and agent-browser **0.41.1**, checked on npm and GitHub on 2026-11-02. The install script `scripts/install_control_backends.ps1` puts both into the git-ignored `.jarvis-runtime/tools/control-backends/` and checks their SHA-256 digests. Both run against your installed Chrome 156.

## Switches (legacy is the default; one-line rollback)

| Setting | Values | Rollback |
|---|---|---|
| `JARVIS_PC_BACKEND` or `control.pc_backend` | `legacy` · `shadow` · `agent_desktop` | `JARVIS_PC_BACKEND=legacy` |
| `JARVIS_WEB_BACKEND` or `control.web_backend` | `legacy` · `shadow` · `agent_browser` | `JARVIS_WEB_BACKEND=legacy` |
| `JARVIS_HEADED_INPUT` or `control.headed_input` | `ask` (default) · `allow` · `deny` | `ask` |

`shadow` means legacy acts while the new backend only reads, through runners that refuse every write command. It logs counts and matches, never names (`.jarvis-runtime/logs/control-shadow/`).

## PC: `ControlService.uia()` gives `AgentDesktopExecutor` (`jarvis/control/pc/`)

| Legacy (UIAExecutor op) | agent-desktop | Notes |
|---|---|---|
| `launch` (4 allow-listed apps) | resolver, then `launch <exe> [--arg=path]`; Store apps through `explorer shell:AppsFolder\<AUMID>` and `wait --event window-opened` | `Policy.check_app` still decides what may launch |
| `read_window` / `observe('win-<hwnd>')` | `snapshot --window-id w-<hwnd> [-i] --compact --timeout-ms 8000` | The same `Kind "name" [dN]` lines; refs stable by (role, name, position) |
| `click` / `invoke` / `select` | `click @ref` (headless semantic) | |
| `set_value` | `set-value @ref` | Password fields refused |
| `toggle` (with or without a target state) | `check` / `uncheck` / `toggle` | Idempotent when a state is given |
| `expand` / `collapse` / `scroll` | `expand` / `collapse` / `scroll --direction` | |
| `type` | empty field: `set-value` (headless, verified); otherwise `--headed type` through HeadedGate | Never a headed fallback after a headless failure |
| `key` | `--headed press <combo> --window-id` through HeadedGate | Blocked combos stay blocked: `--force` is never used |
| `focus` | `--headed focus` through HeadedGate | |
| `focus_window` | `focus-window --window-id` | Steals the foreground, as legacy did |
| `close_window` | `find` the window's Close button, then `click` | No `close-app --force` |
| `list_windows`, probes `window_title` / `windows` | `list-windows` | `w-<id>` is the HWND (checked) |
| probes `value` / `name` / `toggle` / `selected` / `expanded` | `get --property` / `is --property` | |
| Save As (`ControlService._save_as`) | unchanged: it composes `key`, `set_value`, `invoke` and checks the file on disk | |
| No-model fast paths | `minimize` / `maximize` / `restore` / `close-app` / `clipboard-set` + `list-windows` / `clipboard-get` | `jarvis/control/pc/fast_paths.py` |

Retry: only `not_delivered` + `retry: safe`. `STALE_REF`, `AMBIGUOUS_TARGET` and `SNAPSHOT_NOT_FOUND` get one fresh snapshot, the same element by role and name, and one retry. Anything delivered (or unreadable, or timed out) is `executed=True`, never repeated, and the caller re-reads. Each task gets a traced session (`session start --name jarvis-<task>`).

## Web: `ControlService.browser()` gives `AgentBrowserExecutor` (`jarvis/control/web/`)

| Legacy (BrowserExecutor op) | agent-browser |
|---|---|
| `navigate` (URL, back, forward, reload) | `open <url>` / `back` / `forward` / `reload`; then `get url`, with `Policy.check_url` on the final URL |
| `new_tab` / `switch_tab` / `close_tab` / `list_tabs` | `tab new` / `tab <id>` / `tab close <id>` / `tab list` |
| `read_page` (filter, ref) | `snapshot [-i] -c`, or `get text @ref` |
| `find` | snapshot plus a local filter |
| `get_page_text` | `read` (agent-readable text, no extra navigation) |
| `form_input` (text / select / checkbox) | `fill` / `select` / `check` / `uncheck`, then `get value` / `is checked` |
| `left_click` / `double_click` / `hover` | `click` / `dblclick` / `hover` |
| `scroll` / `scroll_to` | `scroll <dir> <px>` / `scrollintoview` |
| `type` / `key` | `keyboard type` / `press` |
| `right_click`, `left_click_drag`, `zoom` / screenshot, `hold_key` | **stays on legacy** (unsupported here; returns UNSUPPORTED) |

Every call carries `--content-boundaries` and `--action-policy` (generated: deny `evaluate`, network routing, cookie, storage, state, credential and auth actions; confirm `upload`, `clipboard`, `download`, which ask through the approval card). Page content without its boundary marker is refused. `--allowed-domains` cannot be combined with a Chrome profile, so Jarvis's `Policy.check_url` guards domains (target and final URL), as it does today. Profiles: `test` is Jarvis's persistent profile folder; `personal` is your Chrome `Default` profile (comedywithkh@gmail.com, your choice). State is encrypted with the key in `secrets/agent-browser.key` (git-ignored).

## What stays on the legacy or fallback path

- **Vision route** (`screen_act`) for apps with no accessibility tree (Blender's viewport, games, canvases). Registered as the brain neuron `pc.vision_fallback`.
- **Older desktop tools outside the seam**: `select`, `fill_text`, `type_text`, `save_file`, `media_control`, `spotify.py`, `whatsapp.py`, `desktop_actions.py`, `screen_worker.py`. They keep pywinauto and pyautogui. They move one at a time after the A/B shows agent-desktop wins in their category.
- **Web**: right-click, drag, zoom screenshots and held keys stay on Playwright.
- **Electron CDP handoff** (`launch --cdp` then `agent-browser connect`) is designed but not yet wired. It needs a fresh launch, which would close your running app, so it waits for a scenario that needs it, behind an approval.
- **The FFI DLL** (`agent_desktop_ffi.dll`) is downloaded but unused. The CLI is about 30–80 ms per call; switch to FFI only if the A/B shows the process spawn matters.

## Laya instead of JEV (user request 2026-11-02)

agent-desktop's JEV goal loop asks a paid remote service (TypeSafe) which element to act on, sending a text description of the screen. Jarvis uses **Laya** instead: a small local decision model (`laya-serve` 0.4.21, its own `.venv-laya` with CUDA PyTorch, started by `scripts/start_laya.ps1`). It runs on the GPU, listens on 127.0.0.1:8765 only, uses a key in `secrets/laya.key`, and answers in about 0.2 s warm.

Measured on Calculator (40 controls):
- **JEV unchanged, deciding with Laya:** abstained on every intent. JEV treats any `menu` node (the Windows menu bar) as an open overlay, and Laya is weak on long option lists; its own card gives 0.43 on 77 labels.
- **Jarvis's resolver (`jarvis/control/pc/laya.py`):** controls are shortlisted by name with no model, then Laya chooses among at most 8 or "none". It picked 7 of 8 correctly in about 0.25 s; the eighth was below the bar.

**Live through `ControlService`:** "the digit two", "plus", "the digit three", "equals" gave 2 + 3 = 5, about 1 s per action including the read-back.

Rules:
- It acts only at 0.9 confidence or higher; otherwise it names the closest refs and does nothing.
- It is used only with the agent-desktop backend.
- Screen text goes only to the loopback server.

## Brain neurons

`pc.observe`, `pc.act.semantic`, `pc.act.headed` (approval), `pc.app.launch`, `pc.window.manage`, `pc.clipboard` (approval), `pc.notifications`, `pc.vision_fallback`, `web.read`, `web.observe`, `web.act`, `web.auth` (approval). Each is eligible only while its backend is on. Learning can rank them; it can never grant `--headed`, `--force` or signed-in browsing.
