# Changes and keep decision

- development_browser.py rejects non-root/query/fragment/credential-bearing URLs with a categorical error; validates bounded scenario names, JSON size, fields, text/count/key/attribute types before browser execution. Defaults for existing named-role scenarios retained.
- Chrome contexts now explicitly block service workers, grant no permissions and close WebSockets in addition to existing HTTP routing, fresh storage and download policy.
- development_tools.py constructs one proxy-free opener per instance; existing lock serializes use. Command/build/start/stop/tool names and approval behavior retained.
- New owned browser/build/security/fault tests, reviewed catalog accounting, benchmark/report/hash scripts, README/system-map/guide updates. No dependency/configuration/product UI change; historical artwork and acceptance screenshots preserved. New screenshots are actual authored test-page captures only.

Health-check overhead warm p50/p95 **0.38605/0.39860 → 0.01765/0.01930 ms**; peak traced allocation **7319 → 2352 bytes**. Same fake HTTP200 response and active/dead/closed assertions;25 calls/version in one process. Five initial calls are not fresh-process cold starts. Imports/construction/network/browser/build/GPU excluded. Cached opener retains per-instance memory and moves construction to instance startup; no end-to-end speed or VRAM claim.

Keep: removes repeated allocation and closes observed input/network boundaries. Baseline {'PASS': 25, 'FAIL': 0, 'SKIPPED': 0, 'seconds': 6.737}; final focused {'PASS': 50, 'FAIL': 0, 'SKIPPED': 14, 'seconds': 67.729}; full {'PASS': 2855, 'FAIL': 0, 'SKIPPED': 48, 'seconds': 532.419}. [Exact files](files-changed.json), [before/after hashes](source-hashes.json), [diff](source.patch). No incremental build/cache/HMR optimization claimed without a baseline.
