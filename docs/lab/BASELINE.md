# Baseline evidence and unexecuted gates

## C1 local components/assets — 2026-11-04 IST

The user authorized moving to the next step. Work continues on `lab/phase-c1-components`, preserving all earlier uncommitted work. New modules implement validated component assemblies and separate explicit dependency DAGs, bounded unit-aware parameter change plans, immutable project snapshots in existing Journal/LabMemory, local asset identity/license/hash gates, a small inert artifact cache and a read-only boundary over the existing Drive client. Four explicit C1 neurons use the existing brain; the original foundations/solver implementations are unchanged. [Implementation and usage](C1_COMPONENTS.md).

**Verification:** pre-change scoped baseline **78 passed**, 39.98 s. Final focused regression **204 passed / zero failures / zero skips**, 61.17 s (62.672 s including runner setup), source fingerprint unchanged during execution. Strict neural mypy passes on 18 source files; actual launcher readiness reports ready. [Regression receipt](evidence/c1-regression.json).

**Local text proof:** actual Engine text ingress → Actions → brain → C1 adapters → verifier passed project inspection, 3-degree bounded planning and concept-asset inspection; out-of-bounds input refused. The scratch Journal holds two typed components, two local Source records and one project snapshot; all example source files remain byte-identical. Examples are explicitly synthetic JSON, not real vehicle models or engineering meshes. Only downstream wing geometry/mesh/aero/handling are planned for invalidation; unrelated thermal work stays unaffected. No solver runs. [Proof receipt](evidence/c1-brain-proof.json).

Initial tests found an unsupported neuron `intents` field and two fixture assumptions. The adapter now uses the existing closed Neuron description/source fields, the foundation count is checked against actual registered Lab IDs, and invalid-command testing goes through real ingress rather than a parser that does not recognize Lab syntax. Failed attempts remain private receipts; no core schema was relaxed. Cache idempotence, affine-unit deltas, graph cycles/collisions, source hashes, license/credit vetoes, scenario immutability and invalid-bound refusal are covered.

No new packages/downloads, remote writes, credential reads, services, model/GPU calls, UI changes or repair-campaign resume. Lab flags remain false; brain act / learning shadow and existing control defaults remain unchanged. The 24-call ngspice batch stays exhausted at 24 before/after; its scoped qualification still matches, checked without solver execution. No whole-project suite or live control benchmark was repeated for C1; the earlier 5,181/42/161 full result is historical, not current release acceptance.

**Open gates:** live Drive/catalog retrieval, independent source/identity/license corroboration, large/native asset storage and reconstruction are unexecuted. Drive is tested through an injected read-only client only. Parameter requests produce `PLANNED_NOT_EXECUTED`, never modify source designs/scenarios or run downstream solvers. Spoken/autonomous B6 and scientific A–H remain open. Next plan step is C2 CAD/meshing/rigging adapters after inspecting actual installed tools; any new acquisition needs its separate approval. No stable release tag or full scientific acceptance is claimed.


## B6 bounded ngspice proof — 2026-11-04 IST


Current final focused verification: **177 passed / zero failures / zero skips**, 54.15 s (55.828 s including runner setup), source hash unchanged during the run. It covers divider, foundations, neural registry/mode/learning, flags, refusal, DAG, skills, sandbox and launcher fixtures. Strict neural mypy passes on 18 files; actual readiness reports ready. [Regression receipt](evidence/ngspice-regression.json). These checks do not execute a new full suite, microphone or live control benchmark.

The user separately approved Linux preparation and up to 20 sandbox divider invocations. Official hash-pinned Debian **libngspice0 44.2+ds-1** and **libgomp1 14.2.0-19** were extracted into a private tool folder: **2,641,104 archive bytes**, **9,405,810 extracted bytes**. Copyright/exception files are retained. No package manager or maintainer script ran; no host/core install, PATH change, Docker pull/build or image replacement. Release 44.2 is a compatibility pin, not Windows release 47.

New bounded adapters compile only an ideal DC resistor divider. They use the existing non-root RepositorySandbox and its network/process seccomp restrictions, immutable image, read-only mounts and resource limits. Numeric vectors are independently checked against Ohm/Kirchhoff equations; actual solver receipts are required. Failed or missing outputs have no analytic substitution. Each attempt consumes a durable slot before dispatch, across Journals/restarts.

**Operator-assisted proof passed:** three actual golden cases, three independent verified text-ingress → Actions → brain → sandbox goals, code-checked promotion, and fresh-process reuse without requalification. Final qualification: **19.407 s**; final fresh-process reuse: **3.313 s**. There are 21 immutable Experiment/RunArtifact pairs in the scratch brain Journal. The earlier implementation's qualification was degraded after file-size and invalid-request refusal improvements changed its hash; final source was requalified. [Current learning receipt](evidence/ngspice-brain-learn.json) · [Fresh-process receipt](evidence/ngspice-brain-reuse.json) · [Runtime summary](evidence/ngspice-runtime-summary.json).

**24/24 approved attempts used:** 22 successful calls and two failed initial attempts. The user explicitly approved four additional attempts to requalify the final invalid-request refusal fix. The cap is exhausted and a no-dispatch exhaustion check passed; no further execution is authorized by this batch. The native failure was localized to the pre-init no-spinit API; it remains recorded/charged. Empty private initialization paths resolved it without loosening isolation. Initial successful receipts remain separately labeled historical. The existing Google credential-output incident and all unrelated regression failures remain unresolved as previously recorded.

Shipped Lab flags remain false; production scientific memory was not populated. Six reviewed built-in Lab manifests now include divider execution/verification; learned promotion exists only in the scratch proof Journal. Supported opt-in text: `lab simulate divider 10 V 1000 ohm 1000 ohm`. This models ideal DC resistors only: no temperature response, arbitrary circuit, physical validation or hardware action. The scoped qualification does not grant additional execution beyond the exhausted approved batch. A recognized invalid divider request now remains in the brain and is refused by the typed adapter before solver dispatch, rather than falling back to the general planner.

**B6 remains partial:** actual microphone/spoken acceptance and autonomous research/install/adapter authoring were not performed. This operator-assisted harness is not autonomous G acceptance. Full scientific A–H, current whole-project flags-on/off/live-control comparison and release acceptance remain open. The preceding 5,181/42/161 full-suite result predates this solver extension; do not present it as a fresh whole-suite result for this source. Focused regression and readiness receipts below provide the current verification. Paused repair campaign stays paused.


## Phase B foundations candidate — 2026-11-04 IST

User authorization to follow the current plan supersedes the earlier Gate A stop. Work is on `lab/phase-b-foundations`. New default-off domain modules reuse the existing brain Registry/compiler/dispatcher, Journal, lifecycle, skills and queue. Four explicit Lab neurons support status and real Pint conversions; scientific records stay in the existing Journal. The learning gate qualifies only the reviewed Pint adapter: general autonomous solver acquisition, component DAG/reconstruction and scientific workflows remain incomplete. See [foundations](FOUNDATIONS.md) and [modification log](MODIFICATIONS.md).

Fresh baseline: **5,160 passed / 45 failed / 161 skipped**. Follow-up: **5,181 passed / 42 failed / 161 skipped**, 1,508.30 s; no new failing IDs, source fingerprint unchanged during the run. The follow-up denies production credential access, external network and live model/Blender traffic, so it is not live acceptance. One stale request-safety test fixture was repaired; two other absent baseline failures are not claimed as product fixes. Focused checks: **218 passed / one skipped / zero failures**, 37.0 s. Strict neural mypy passes; compatible launcher check reports ready. [Full receipt](evidence/foundations-full.json) · [Focused receipt](evidence/foundations-focused.json).

Shipped Lab flags remain false; brain act / neural learning shadow and existing control defaults are preserved. Source registry: 306 neurons / 434 synapses with Lab off; 310 neurons with opt-in. Six Google tool contracts and read/write classification were corrected without executing remote writes. No new always-on service or GPU workload. Pint and its five pinned wheel packages were installed only in the approved isolated environment (428,497 downloaded bytes).

Separately approved ngspice preparation is complete: official release-47 Windows archive, 13,814,879 bytes, 811 files, checked paths and observed SHA-256. **No ngspice executable ran and B6 is unmet.** COPYING includes component-specific LGPL/GPL/MPL exceptions; the existing reviewed sandbox is Linux and cannot execute these Windows binaries. [Preparation receipt](evidence/ngspice-preparation.json). Further tool acquisition/execution requires a compatible reviewed environment and its applicable authorization.

An existing baseline assertion exposed OAuth fields in tool output. Generated logs were sanitized; subsequent runs block production credential reads and suppress assertion payloads. The displayed output cannot be retracted. Authorization was not reset/revoked; any Google rotation/reconnection remains user-controlled.

All 42 remaining regression failures, live PC/browser comparison, voice/UI checks, B6 solver proof and scientific A–H (including mandatory G/H) remain open. No stable release tag or full release acceptance is claimed. The unrelated autonomous repair campaign remains PAUSED_BY_USER. Next: reconcile the solver platform/license/sandbox, obtain any additional concrete acquisition approval, then prove a real solver through the existing brain and golden gate. Earlier entries below are historical checkpoints.


2026-11-04 IST. **Not a complete pre-Lab baseline.** No application behavior changed, no Lab feature enabled, no full regression or live PC/browser benchmark result claimed.

## Fresh focused regression

Existing tests: `test_neural_mode.py`, `test_neural_registry.py`, `test_neural_learning.py`, `test_flags.py`, `test_control_bench.py`.

Result: **72 passed in 3.06 seconds**, pytest 8.4.2, Python 3.11.9 in `app/.venv`. Launched with `PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled, and a Python audit hook denying socket connect/bind/sendto, subprocess.Popen, os.system and os.startfile. No production Journal or queue was opened by the inventory collector. Tests use isolated fixture state.

Reproduction from `app/` (PowerShell):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
import sys
def guard(event, args):
    if event in ('socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.sendto',
                 'subprocess.Popen', 'os.system', 'os.startfile'):
        raise PermissionError('Lab audit denies network and external processes: ' + event)
sys.addaudithook(guard)
import pytest
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider',
    'tests/test_neural_mode.py', 'tests/test_neural_registry.py',
    'tests/test_neural_learning.py', 'tests/test_flags.py', 'tests/test_control_bench.py']))
'@ | & .venv/Scripts/python.exe -
```

## Unsuccessful isolation attempt, retained separately

The initial run also selected `test_neural_runtime.py` and `test_neural_viewer.py`: **89 passed, 4 failed, 4 errors in 5.32 s**. Do not add the overlapping pass counts to 72.

Three runtime failures were induced by the audit's deliberate subprocess denial: the code workflow runs Python unittest on scratch copies and could not reach its expected assertions. Four viewer setup errors were caused by denying the fixture's loopback HTTP bind. A rename fixture failed with Windows `WinError 5` in sandbox temporary storage. No product patch was made to mask these conditions. The failing runtime/viewer cases were **not revalidated under compatible isolation**; they remain unexecuted baseline gates, not established regressions or proven harmless product failures.

## Whole suite and desktop benchmark

| Gate | Fresh status | Reason / next action |
|---|---|---|
| Full existing pytest/unittest suite | NOT_RUN | Audit requires no production-state effects. Review fixture effects and run in an isolated environment/copy; blanket subprocess/socket denial is incompatible with some suites. Do not resume campaign trials or frozen application checks |
| Live PC/browser accuracy and mean seconds/task | NOT_RUN | Existing live cases launch apps, alter files/settings and create cloud drafts; they contradict Phase A's read-only execution rule. Select owned scratch roots and accounts, scoped approvals and a controlled desktop window before execution |
| Neural off/shadow/on parity | NOT_RUN | No production application/brain mode was changed |
| Loaded local LLM RAM/VRAM | NOT_RUN | No model started or loaded; stopped services were left alone |
| Supported launcher check | NOT_RUN | `launcher --check` enters preflight and queries services; preflight creates runtime directories. Not needed for a documentation-only audit; schedule with the first application change |
| Paused repair campaign | PRESERVED | No resume, inference probe, retry or task-store modification |

The live benchmark path is `benchmarks/live/cases.py` → `runner.build/run` → real Commands/Actions/brain/control plus independent state readers in `control_cases.py`. `test_control_bench` exercises good/bad oracle fixtures, **not live accuracy or latency**. Run commands for later planning: `python benchmarks/live/cases.py control --pc agent_desktop --web agent_browser --repeat 5`; use the same config, workload, accounts and hardware residency for before/after, report failures, distribution, mean task seconds and uncertainty. Do not execute this merely by copying this document.

Historical README reports (e.g. 4,981 passed and 39 baseline failures on 2026-11-02) are prior evidence with different scope/revisions, not this audit's results. Historical benchmark receipts and failed runs remain authoritative for their recorded contexts. No current claim of no regression is possible without the full gate.

## Hardware/environment observations

Initial psutil observation: RAM total 33,656,832,000 bytes, available 12,627,238,912 bytes; D: free 219,283,427,328 bytes. Collector's later snapshot is in [summary.json](evidence/summary.json); fluctuations are expected. These are current-session snapshots, not controlled idle or LLM-loaded measurements.

`nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,memory.free --format=csv,noheader` returned `NVIDIA GeForce RTX 3050 Laptop GPU, 610.74, 4096 MiB, 0 MiB, 3962 MiB`. Retain the driver's readings as returned; do not infer all nominal VRAM is allocatable. No GPU job or model load occurred.

`wsl --list --quiet` returned `Wsl/E_ACCESSDENIED`. This is insufficient to conclude that WSL2 or a distribution is absent. No escalation, installation or distro change attempted. Tool PATH and package checks cover only this shell and core .venv; isolated environments and external install locations may contain additional tools.

## External retrieval and spend

Firecrawl balance before retrieval: 205 remaining credits, 1,000 plan credits, provider billing period 2026-10-04T12:46:16.951Z through 2026-11-04T12:46:16.951Z. Four official-document scrapes reported one credit each (MCP spec, OpenAlex landing, access, pricing). MCP feedback refunded one credit; pricing feedback refunded zero. Gross four credits, recorded net three; existing plan credits used, no purchase or overage action. Cash value of those credits is not established. No solver API, OpenAlex API request/key creation, coding-agent orchestration or cloud GPU call was made. This chat's model billing is not exposed to repository metering and is not claimed to be zero.

See [external evidence](EXTERNAL_VERIFICATION.md). All remaining catalog versions/licenses are user-supplied targets pending install-time verification, not independently recertified here.
