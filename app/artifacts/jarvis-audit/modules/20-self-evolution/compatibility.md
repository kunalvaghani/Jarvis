# Official upstream — checked2026-10-16 IST

Firecrawl primary sources: [URLs/release dates](upstream-checks.json). Installed Python3.10.6, pytest8.4.2, psutil7.2.2, Requests2.34.2, pip26.2.1, git version 2.49.1.windows.1; RAM33656832000B; target/same-machine RTX3050 Laptop4GB. No environment install or heavyweight inference run.

[Windows GetSystemPowerStatus](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getsystempowerstatus) and [SYSTEM_POWER_STATUS](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-system_power_status) document the saver flag. Added read-only ctypes query, verified it runs on this Windows machine; fake on/unknown states defer. API does not measure game occupancy or guarantee scheduler/native preemption. Documentation has no package release date; checked date is not a fabricated release.

[pytest9.1.1](https://pypi.org/project/pytest/) released **2026-06-19**, Python≥3.10; [official changelog](https://docs.pytest.org/en/stable/changelog.html) inspected. Installed8.4.2 retained and executed; no claim9.1.1 was installed/tested. Source evaluation now uses pytest so pytest-style security/privacy regressions are included; the old unittest-only command omitted them. [Git worktrees](https://git-scm.com/docs/git-worktree) supply source isolation, not OS security. [Git for Windows2.56.0(2)](https://git-scm.com/install/windows) dated **2026-10-05**, newer than installed2.49.1.windows.1; no installer/system mutation. Trusted owned fixture worktree commands verified on installed Git.

Prior [module19 environment/security evidence](../19-ability-forge/compatibility.md) records Python3.10 end-of-life2026-10-01 and the separate voice-forge audit-hook/Docker boundaries. Neither is fixed by this audit. Current implementation improved instead of assuming a dependency upgrade is better on4GB VRAM. No paid API requirement or model download added.

- **JRV-20-002 BLOCKED:** No native game/GPU occupancy sensor or guaranteed kernel preemption. Cooperative busy/activity/resource callbacks are tested; blocking I/O/native kernels may finish before yielding.
- **JRV-20-003 BLOCKED:** Learner writes lack a transactional completion receipt. Durable `needs_review` prevents uncertain replays, but automatic safe continuation through an interrupted repository write is not proved; no dedicated review/resume UI.
- **JRV-20-006 BLOCKED:** No independent semantic privacy oracle, hardened host patch execution sandbox, shadow evaluation or canary/automatic post-deploy rollback. A source worktree is not security isolation.
- **JRV-20-011 BLOCKED:** Only a single eligible Jarvis Python source target is supported; no lockfile/environment migration rollout or reproducible dependency environment test exists. Dependency inputs invalidate receipts, but are not upgraded by this manager.

Live readiness repair_required: ['ollama: unavailable (ConnectionError)']. GUI/game/native GPU acceptance, arbitrary patch privacy, canary and lockfile rollout remain incomplete;32 fixture IDs do not certify those systems.
