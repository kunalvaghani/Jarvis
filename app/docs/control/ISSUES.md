# Control migration: open issues

| # | Issue | Status |
|---|---|---|
| 1 | The UAC, secure-desktop and locked-screen scenarios cannot be triggered safely (the standing rule is never to automate UAC). They are covered by recorded-envelope tests of `PERM_DENIED` and the elevated-target mapping, not by a live scenario. | accepted |
| 2 | Google Docs and Sheets oracles confirm by Drive search in a fresh, read-only session on your profile (independent of the acting session), plus the answer for the Sheets sum. They do not read individual cells. | accepted |
| 3 | WhatsApp, Discord, tray and Task Manager scenarios are read-only, so their oracles can check only an answer and that nothing was sent; their accuracy is softer. | accepted |
| 4 | agent-browser `--profile Default` while your own Chrome is open is untested: Chrome may refuse two processes on one profile. To be checked in the live round; fallback is a copied profile folder. | live round |
| 5 | The Electron CDP handoff is not wired (it needs a fresh launch, which closes your app). | deferred |
| 6 | The older desktop tools outside `ControlService` (`select`, `fill_text`, `type_text`, `save_file`, `media_control`, `spotify.py`, `whatsapp.py`) still use pywinauto and pyautogui. | after the A/B |
| 7 | C41 (focus steal) counts every foreground change, including the user's own. The user must keep working in one window during it. | accepted |
