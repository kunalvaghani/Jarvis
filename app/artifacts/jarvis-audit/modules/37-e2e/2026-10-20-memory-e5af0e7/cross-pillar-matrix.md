# Change impact
| Change | Legacy / pillar seam | Invariant | Fresh regression |
|---|---|---|---|
| Test only: failed workbook repeat | API/ToolRegistry → learning → planner | Retrieved hint cannot imply success | JRV-37-017 memory-on/off |
| No production change | P34 dependency / P35 security / P36 status / P37 recovery | Existing boundaries retained | neighbors.xml, 109 pass / 1 skip |
| UI recovery neighbor | queued external mock → crash → UI | No replay; truthful paused status | JRV-37-021 in neighbors.xml |
All 26 acceptance IDs retained in tests.jsonl: one scoped mock UI PASS, 25 BLOCKED. This new seam does not close an additional full acceptance case.
