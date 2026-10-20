# Actual adapter coverage

| Route | Evidence | Limit |
|---|---|---|
| Local stdio | Real child processes, init/list/call, error/timeout/cancel/death | Synthetic server, local-only markers |
| Generated MCP | Existing offline Docker image and SDK, real registration/invocation/health/unregister | Fixed author and approval callbacks; integrity failure |
| Calendar/Jira/Slack | Source inspection and toolkit credential/approval/error fixture regressions | No real account, scope, consent, refresh or final provider readback |
| Built-in namespace | Two real local stdio servers with same echo name | Explicit wrapper routing, no model-choice proof |
| Ambient secrets | Synthetic env canary excluded from child | Configured trusted host process still has filesystem/OS privileges |
| Memory/skills | 34 real local skill/SQLite/adapter lifecycle tests | No MCP schema dependent-skill version invalidation or account switch proof |
