# Actual versus mocked routes

| Route | Actual execution | Limit |
|---|---|---|
| Generated MCP | Offline Docker/SDK, registry/call/health/unregister and data readback | Fixed author/approval |
| Local stdio/token rotation | Real disposable child processes and synthetic token hash readback/redaction | No OAuth/live provider |
| Calendar/Slack | Real ToolRegistry/adapter/context, intercepted API ledger | No real account scopes/events/messages |
| Principal verification | Explicit mocked read-only verifier, default absence fails closed | No production verifier registered |
| Memory/skills/concurrency | Actual SQLite/catalog and 16-thread drift updates | No full migration or registration-during-task proof |
| Recovery | Real owned Windows fixture trees and synthetic disk logs | No running Jarvis/user process targeted |
