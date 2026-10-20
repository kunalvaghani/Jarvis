# Real versus mocked adapters

| Path | Actual run | Limit |
|---|---|---|
| Generated MCP | Existing offline Docker/SDK, registry, calls, health/unregister | Fixed author/approval, no live account |
| stdio boundaries | Real disposable Python children | Synthetic schemas/results/marker readback |
| Calendar/provider identity | Actual dispatcher/context, intercepted API, synthetic A/B tokens | No provider who-am-I/scopes; stale-label failure |
| Dependent skills | Actual local SkillMemory/SQLite state/retrieval | Literal references; no full version migration |
| Concurrency | 16 threads drift-update the same registry | No registration during task/multi-process stress |
| Recovery | Real hidden Job-owned fixture trees and synthetic disk logs | No actual Jarvis/user apps targeted |
