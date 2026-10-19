# Exact claims Codex should try to falsify

1. No commit on `main` or any branch other than `claude` was created by the upgrade (`git log main..claude` lists all 23+ upgrade commits; `main` was moved only by the user-requested push after Phase 5).
2. `ToolRegistry.execute` is the only executor for every new tool (`execution_methods`, `strategy_execute`, adapters, `evolution_*`, `cloud_architect_consult`).
3. No upgrade path replays an uncertain external write (DAG restore, task recovery, trainer, archives).
4. The cloud architect cannot send anything unless: config enabled, free plan confirmed, quota known, three distinct verified local reasoning failures, privacy gate passed, and an approval card accepted. With `cloud_architect.enabled=false` the tool returns `local` without any card.
5. A path, filename, email, URL, secret, internal module name, source snippet or log excerpt in any problem field keeps the problem local (0 outbound requests).
6. The Show Me Once recorder never stores RuntimeIds, keyboard input, field values, password-field clicks, clicks outside the selected window, or injected input.
7. A self-evolution candidate can change only the literal values of one declared surface; any other byte change is quarantined before candidate code runs.
8. The retention gate refuses to evaluate if any file under `evolution_eval/` differs from the committed blob.
9. Experiments never create branches, worktrees or files in the canonical repository.
10. A qualified evolution proposal is never deployed without an approval card, and a failed health check restores the exact previous bytes.
11. The Phase 6 DAG proposal improves held-out *synthetic* makespan by about 15 % (CI excludes zero, reproduced); no claim is made for real tasks.
12. Every AZR training target equals the oracle's answer; no model-written answer is ever a label.
13. Train, validation and held-out AZR splits share no task id and no structure signature; held-out induction families never appear in training.
14. Induction answers execute only inside the network-less container, one forked child per program under CPU/address-space limits.
15. Training stops (after a checkpoint) when any Jarvis GPU lease is active or pending, and resumes bit-exactly.
16. The merged checkpoint's held-out gain (0/165 → 9/165) is significant under the pre-registered policy; the unmerged adapter was rejected on latency; nothing was promoted, registered with Ollama or wired into Jarvis.
17. The Obsidian vault is never written by indexing.
18. The final full regression and launcher check results in [README.md](README.md) are the actual outputs of the logged commands.
