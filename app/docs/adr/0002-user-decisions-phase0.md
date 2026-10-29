# ADR 0002: User decisions after Phase 0

Date: 2026-10-30 · Status: accepted (user answers 1–5), one item awaiting confirmation

## 1. Test directory

Approved root: `D:\Phython Project\TestCodes`. That folder already holds the user's own files (`auto_wifi_sender.py`, `health_monitor.py`, `game_resources.h`, `python-calculator-with-elegant-ui`). All automated tests and benchmarks are confined to the subfolder **`D:\Phython Project\TestCodes\jarvis-control-tests\`**. Setup/teardown create and remove files only inside it; path confinement in `policy.py` enforces that, with symlinks resolved.

## 2. Browser profiles

The user wants Jarvis's browser to carry the details of their own Chrome profile. The rework prompt also requires acceptance tests to use a profile with no personal sign-ins. Both are kept, as two separate profiles:

| Profile | Path | Used for |
|---|---|---|
| Test | `.jarvis-runtime/test-browser-profile` (new, empty) | Phase 4 harness, controlled and live benchmarks. No personal accounts ever. |
| Personal | `.jarvis-runtime/browser-profile` seeded from the user's Chrome profile | Everyday Jarvis use after Phase 5. Never used by any benchmark. |

**Awaiting confirmation:** which Chrome profile to copy. The folder literally named `Profile 1` was last modified 2024-04-27 (33 MB) and is not in Chrome's current profile list. The active profile is `Default` ("Person 1", 2.8 GB, 3 Google accounts, used 2026-10-30). The copy needs Chrome closed, because Chrome holds its cookie and login databases locked while it runs.

Known limitation to verify after copying: Chrome 127+ protects cookies and passwords with app-bound encryption. Some sign-ins may not carry over to a copied user-data directory and would need one manual sign-in. Chrome 136+ refuses automation of the default user-data directory, which is why a copy is used rather than attaching to the live profile.

## 3. Installs

Approved and installed into `app/.venv` on 2026-10-30. Only additions; no existing package changed version.

| Package | Version | Licence | File |
|---|---|---|---|
| mss | 10.2.0 | MIT | `requirements/runtime.txt` |
| dxcam | 0.3.0 | MIT | `requirements/runtime.txt` |
| uiautomation | 2.0.29 | Apache-2.0 | `requirements/runtime.txt` |
| mypy | 2.4.0 (2.4.1 skipped: released 2 days earlier) | MIT | `requirements/testing.txt` |
| coverage | 7.16.2 | Apache-2.0 | `requirements/testing.txt` |
| pytest-cov | 7.1.0 | MIT | `requirements/testing.txt` |

Also pulled in: `ast-serialize 0.13.1`, `librt 0.16.0`, `mypy_extensions 1.1.0`, `pathspec 1.1.1`. Runtime-manifest import checks for mss/dxcam/uiautomation are added in Phase 2, when Jarvis code first imports them. `uiautomation` changes process state on import, so it must not load during the launcher check before the coordinate module initialises DPI.

## 4. Python 3.11 migration

The user chose to move to 3.11, carefully, with all of Jarvis. The approach is side by side and reversible:

1. Build `app/.venv311` from Python 3.11.9 with the same pinned `requirements/runtime.txt` + `testing.txt`. The current `.venv` is untouched.
2. Run the full suite under 3.11 and compare with the 3.10 baseline (4532 passed / 39 failed / 150 skipped). Every difference is diagnosed before switching.
3. Run `python -m jarvis.launcher --check` under 3.11.
4. Only then point `Start Jarvis.cmd`, `jarvis_bootstrap.py` and `runtime_manifest.json` at `.venv311`, keeping `.venv` as the rollback.
5. Secondary environments move one at a time with their own checks: `.venv-brain`, `.venv-f5`, `.venv-harness`, `.venv-openviking`, `.venv-skills`, `.venv-training` (all 3.10.6). `.venv-deerflow` (3.12), `.venv-hermes` (3.14) and `.venv-hermes-bootstrap` (3.11) already meet the target.

New control-layer code is written to run on both 3.10 and 3.11 until the switch.

## 5. Gmail in the user's Chrome

The user wants Gmail handling inside Jarvis, chosen automatically when a request needs it, not as a separate side path. `gmail_chrome_worker` becomes an **app adapter registered with the router** (Route 3, the user's real Chrome window through UIA). The router selects it from intent ("draft an email to …"); the user does not name it. Safety constraints that remain:

- The configured Gmail API connector (`docs/gmail-api.md`) is preferred when it can do the operation (Route 1 before GUI).
- Send is Tier 2: per-action approval every time, never batched past an unverified state.
- It is excluded from automated benchmarks, because those must not touch real accounts. It gets its own manual acceptance checklist.
