# Phase 4 — Defects found during the phase, measurements and remaining limitations

## Defects found and fixed

| ID | Defect | Root cause | Fix | Proof |
| --- | --- | --- | --- | --- |
| H1 | **During this phase's own measurement run, a stray `ollama serve` started with an empty model store.** While it was the active Ollama on 127.0.0.1:11434, Jarvis's Qwen models were invisible to any client. | OpenViking's bootstrap starts `ollama serve` when none is reachable (Ollama was not running after a reboot). My server environment filter dropped `OLLAMA_MODELS`, so that child used `C:\Users\kunal\.ollama\models` instead of `D:\Ollama\models`. | The owned process tree (mine) was stopped; Ollama restarted through Jarvis's existing `knowledge_worker.ensure_server` (models verified present, nothing deleted, the default store stayed 0 bytes). `VikingMemory.start` now starts Ollama the Jarvis way first, refuses to start when the embedding model is absent, and passes every `OLLAMA_*` variable through. | `test_P04_H1_server_never_starts_without_users_ollama_store`; after the full run [processes-after-regression.txt](processes-after-regression.txt) |
| H2 | Real vault: only 17/49 indexed files had verified source links. | Default OpenViking parsing splits Markdown by headings, so stored files no longer matched sources. | `args.parse_mode = no_split` → 34/49. | real-vault runs |
| H3 | Real vault: remaining unlinked files all had spaces/punctuation in their names. | OpenViking normalizes stored names (`Jarvis Apps.md` → `Jarvis_Apps.md`). | Normalized-name matching with content verification → **46/49**. The remaining three: one empty note (not indexed by OpenViking) and two notes whose stored text differs from the source; they stay `verified_link: false`. | [real-vault-index.json](real-vault-index.json) |
| H4 | Real vault search p50 1,413 ms with erratic 157–2,505 ms. | Worker fallback (process + SDK start) on some queries. | HTTP fast path recorded per query; after H2 all queries used `openviking-find-http`: p50 **127 ms**. | real-vault runs |
| H5 | Path generalization left `C:` from forward-slash Windows paths and missed paths with spaces / UNC paths. | Narrow regex. | Drive, UNC and space-containing paths replaced (slight over-redaction of a trailing word is accepted). | `test_P04_success_and_failure_lessons…` |

## Measurements (actual)

| Measurement | Value | Source |
| --- | --- | --- |
| Lesson retrieval precision@1, token overlap (pre-Phase-4 approach) | **0.583** | [memory-benchmark.json](memory-benchmark.json) (authored 12-query oracle) |
| Lesson retrieval precision@1, ReasoningBank + local embeddings | **0.917** | same |
| Lesson retrieve latency p50 / p95 | 101.4 / 116.4 ms (dominated by the query embedding) | same |
| Exploration: Export attempts until verified, with lessons | **2** | same (real isolated browser) |
| Exploration: without lessons | **never verified in 4 episodes** (repeats the failure) | same |
| Exploration episode wall time p50 | ~2.0 s (browser launch included) | same |
| Real vault (1,194 files; 49 eligible Markdown after exclusions) full index, `vectors_only` | 63.7 s; re-index with no changes 0.51 s | [real-vault-index.json](real-vault-index.json) |
| Real vault search p50 | 127 ms (4 queries, HTTP path) | same |
| OpenViking server RSS (process tree) | ~442 MB | same |
| Real vault unchanged after indexing | **true** (SHA-256 over every file before/after) | same |
| Local embedding latency | query ~113 ms; 32-document batch 11.1 s (CPU path, 405 MiB VRAM in use) | Phase 4 notes |

Idle behaviour: OpenViking is started by the watchdog at Jarvis start (≈ 27–32 s, ~442 MB RSS). Indexing, compaction and
exploration run only from the `SelfEvolution` idle loop (idle, battery, RAM and CPU gates; every 30 min at most; preempted
by user activity through the existing `_cancelled`). No GPU work is scheduled by Phase 4 code; embeddings run in Ollama
(CPU path observed). No GPU/VRAM contention test was run with speech or the planner loaded.

## Remaining limitations (not claimed)

| ID | Limitation |
| --- | --- |
| M1 | **Desktop GUI exploration is BLOCKED**: no verified disposable VM backend. Only the isolated browser and the Blender sandbox explore. |
| M2 | Browser exploration runs only against approved loopback origins; there is no real-website curriculum. |
| M3 | Goal proposal and lesson induction are deterministic; the optional model `summarizer`/proposer is not wired to the local LLM (no live model-authored lessons were produced). |
| M4 | "Lessons improve completion" is shown on a fixture app and the Blender sandbox (real execution, small curricula), not on live user tasks. |
| M5 | L0/L1 summaries are off by default (`semantic_directories: []`); when enabled they are model-generated and were observed to include unsupported claims. |
| M6 | 3 of 49 real vault files lack verified links (H3). |
| M7 | The OpenViking server adds ~442 MB RAM while Jarvis runs; set `viking_memory.enabled: false` to avoid it. |
| M8 | CAPTURED candidates from exploration are recorded for Pillar A but not auto-committed: browser trajectories are not fixture-safe for `verify_execution`. |
