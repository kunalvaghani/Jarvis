# Finding reconciliation at e5af0e700517bac5fb48dcebc8f6cc9c9df9a369

| Finding | Current state | Fresh evidence |
|---|---|---|
| P99-R1 prior P34-P37 integration | RESOLVED for earlier production repairs: integrated at 3fbfbf68b6e5cd964191db2c3245efbc2f5a3772; independently exercised at e5af0e700517bac5fb48dcebc8f6cc9c9df9a369 | full.xml, baseline.xml; source-hashes.json |
| P37-001..004 | integrated fixes retained | lifecycle/consent/no-replay/task regressions in fresh baseline/full |
| JRV-37-021 actual UI-consumer gap | PASS in requested mock-send scope | portable process-crash/restart/Tk text test and journal |
| P34-R1/R2/R3 original implementation cases | code+fixture repair independently verified; live gates still BLOCKED | 66 mocked dependency tests within 104 baseline; fresh full suite |
| Global verifier / cloud provenance / native target lifetime | OPEN P1, not closed by one passing UI path | failures.md and cumulative handoff |
| IR-004/V2-003 deep cwd | still OPEN P2, source unchanged here | inherited V2 reproduction and failed alternatives |

New portable test has no integration SHA yet. No production patch proposed in this continuation. Preserve historical uncommitted-candidate verdicts as dated evidence, not current integration state.
