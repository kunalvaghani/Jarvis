# Retained scoped changes

- capabilities.py shares per-query ranking inputs and caches bounded description tokens; scores tool bindings once, retaining existing intent priorities/prerequisites and deterministic ties. Catalog exposes guide provenance/trust. No semantic inference/model added.
- skill_memory.py bounds UTF-8 reads and tool metadata, normalizes CRLF, records origin/relative source/content hash, constrains vault paths, sanitizes guide diagnostics. Verified recipe reuse tracks observed attempts and sorts equally relevant procedures by smoothed success rate before recency. Legacy rows remain compatible.
- hermes_skills.py validates bounded unique metadata/resources and mandatory SKILL.md, checks budgets before reads and caps binary read size before hash/length validation. No upstream code/version installation.
- utility_profiles.py exposes missing_environment/validation_unavailable/stale_validation/ready states and disables missing/malformed/stale activation; current policy/credentials still apply. Existing historical validation record preserved.
- agent_tools.py local guide readback adds provenance, untrusted label and current-policy execution contract; tool names and workflows preserved.
- Tests add32 catalog scenarios and9 supplemental assertions; reviewed catalog accounting handles the explicit PDF blocker. Runtime manifest and dated linked docs describe contracts/census/limits. No new dependency, service, UI or real external action. Existing user changes retained.

See source.patch, source-hashes.json and files-changed.json. No commit or deployment was performed.
