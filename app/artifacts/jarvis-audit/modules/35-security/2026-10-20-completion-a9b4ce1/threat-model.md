# Threat model and explicit boundaries

| Untrusted entry point | Host boundary / observation | Remaining limit |
|---|---|---|
| Web/DOM, document/PDF/OCR, repo README, screenshots/UIA labels | Brain request validation, task allowlist, ToolRegistry and handler approvals | Complete taint/origin binding across live ingestion not proved |
| Email/provider/tool responses | Cannot carry host approval; uncertain effect must remain uncertain | Exact account/principal/source identity and real crash receipts incomplete |
| ReasoningBank/Obsidian/OpenViking | Data-only guidance; contaminated SQLite to scoped executor refused | No universal retrieval provenance/tenant proof |
| Generated SKILL.md / MCP / repository code | Skill metadata/policy checks, immutable generated source checks, sandbox/env scopes | Native extensions/audit hooks not a kernel security boundary; live hostile containers partly unavailable |
| Cloud architect input/output | Off by default, consent, bounded generic payload checks, recording fake transport; untrusted code static/sandbox gate | Caller provenance labels and regex markers do not establish generic semantics |
| AZR proposals/datasets | Independent oracle plus privacy screening/quarantine | General private-data origin/semantic integrity and public export review incomplete |
| DGM/EEVEE candidates | Protected surfaces and sealed independent evaluator; real disposable tamper tests | No production promotion performed |
| Show Me Once / cursor events | Host approval required before observation/recording, injected inputs ignored | Physical origin/window scoping and password/title privacy live acceptance incomplete |
| API paths | Resolved root containment; native junction escape refused | Reparse mutation after approval before write still unverified |
| Debug logs/errors/artifacts | Known credential redaction; untrusted ability exceptions withheld | All-sink Unicode/proprietary-content classification not complete |

Attacker-controlled reassuring prose never constitutes authorization. Mock success is not actual postcondition readback. Candidate code cannot decide evaluator policy or authorize its own promotion. Residual trust in host outcome construction is explicit, not a cryptographic provenance guarantee.
