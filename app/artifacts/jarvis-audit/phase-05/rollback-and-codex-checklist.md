# Phase 5 — Rollback and independent Codex verification checklist

No Codex review evidence exists for this phase.

## Rollback

```powershell
git revert <phase-05-commit-sha>     # on claude
```

Disable without reverting: `cloud_architect.enabled` is already `false` by default; set `demonstration.enabled: false`
to stop Show Me Once offers. Local state (ignored by Git): `.jarvis-runtime/cloud/architect-consent.json`,
`.jarvis-runtime/cloud/architect-log.jsonl`, `.jarvis-runtime/cloud/advice/`, `.jarvis-runtime/demonstrations/`,
`.jarvis-runtime/learning-queues/`.

## Checklist

1. [ ] `git diff <sha>~1 <sha> --stat` matches [files-changed.txt](files-changed.txt); `main` unchanged.
2. [ ] `python -m pytest tests/test_phase05_escalation_demonstration.py -q` → 38 passed (Docker sandbox and an interactive desktop needed for two tests; otherwise they skip as `BLOCKED:`).
3. [ ] Confirm no test or script makes a real cloud request (the adapter is a recording fake).
4. [ ] Read `cloud_architect.privacy_gate`: refusal on any hit; allowlist; provenance required; `screen_payload` applied last.
5. [ ] Read `cloud_architect.eligibility`: every condition from the brief, including the five-attempt budget and free-plan check.
6. [ ] Read `CloudArchitect.evaluate`: advice text never executed; code only via `screen_code` + `verify_in_sandbox`.
7. [ ] Read `demonstration.DemonstrationSession.process`: injected/outside/password filtering; no RuntimeId persisted.
8. [ ] Read `deliberation.FailureRouter.route` and `Brain.recover_task`: authorization stop; show-me-once only after repeated unknown-UI failures; no recursion.
9. [ ] Reproduce the privacy trace: `python scripts/verification/phase05_escalation_benchmark.py --out <new>.json` → `adversarial_cases_leaked: 0`.
10. [ ] Challenge J1/J2 in [security-and-design.md](security-and-design.md).
