# Project structure and relocation

The canonical application directory is [`app/`](../). The existing `jarvis.*`
Python imports and supervised Start/Stop entry points remain stable. Relative
model, workspace and configuration values resolve from the application directory,
including when settings are read from `config/`.

## Where files belong

| Folder | Contents |
| --- | --- |
| `jarvis/` | Application modules, bundled `assets/`, `data/`, templates and reviewed vendored code. |
| `config/` | `config.json` and `runtime_manifest.json`. |
| `requirements/` | `runtime.txt`, `brain.txt`, `training.txt`, `harness.txt`, `audit.txt`, `gmail.txt` and `skills.txt`. Root `requirements.txt` includes `runtime.txt`. |
| `launchers/` | Setup, Gmail connection, PC catalog refresh and model upgrade `.cmd` shortcuts. Start/Stop remain at the application root. |
| `scripts/setup/` | Setup Python/PowerShell scripts and `connect_gmail_api.py`. |
| `scripts/catalog/` | `scan_pc.py`, `scan_pc.ps1` and `build_catalog_index.py`. |
| `scripts/models/` | `activate_model.py`, `download_model.py`, `download_training_file.py`, `capture_ollama_diagnostics.py` and `upgrade_models.ps1`. |
| `scripts/training/` | All `train_*`, `export_*` and `qwen_*` maintenance programs. |
| `scripts/skills/` | Skill addition, Hermes catalog building and skill/media memory refresh. |
| `scripts/integrations/` | `vendor_execution_primitives.py`. |
| `scripts/audit/` | Repository, execution-source and polyglot audits. |
| `scripts/verification/` | All `verify_*` programs, preserving their distinct live/fixture/regression purposes. |
| `scripts/preview/` | `preview_development.py`. |
| `tests/` | Regression tests, temporary-layout helpers and synthetic/controlled fixtures. |
| `docs/` | User guides, architecture, audit documents and dated verification context. |
| `examples/` | Maintained examples; generated trial projects belong in artifacts. |
| `integrations/profiles/` | Hermes configuration/catalog/license, Harness patch/license and Kokoro asset manifest. |
| `integrations/references/` | AgenticSeek, SuperAGI, Isair, Microsoft Jarvis, Ultron, UI, Memento and UI-TARS reference families with their licenses and notices. |

Active integration directories and embedded upstream checkouts keep their own
layouts and revisions. Source references and artwork retain their original
attribution; moving a reference does not activate the upstream product.

## Artifacts and local data

| Location | Contents |
| --- | --- |
| `artifacts/reports/` | Loose JSON, JSONL and text reports, including `scenario_results.json`. |
| `artifacts/media/` | Existing images, GIFs, audio and development previews. |
| `artifacts/training/` | Complete `qwen-*` and `coding-*` runs, including their original internal reports and checkpoints. |
| `artifacts/projects/` | Generated development, multilingual and real-world trial projects. |
| `artifacts/research/` | Development research/download evidence. |
| `artifacts/fixtures/` | Loose Python verification fixtures. |
| `artifacts/logs/` | Historical loose artifact logs. |
| `.jarvis-runtime/state/` | File catalog and SQLite index, scan metadata, task state, UI memory and optional project memory. |
| `.jarvis-runtime/logs/` | Application-root worker/server logs. |
| `.jarvis-runtime/backups/` | Configuration backup made before PC scanning. |
| `.jarvis-runtime/legacy-home/` | The preserved former `~/AppData` cache. |

Existing runtime service directories, recovery snapshots, journals and
`.jarvis-runtime/repairs.jsonl` keep their established locations. Historical task
payloads and archived results are preserved rather than rewritten as current
actions. Future script outputs use `jarvis.paths.artifact_path` for consistent
grouping.

Downloaded `models/`, `.venv*/`, `secrets/`, `JarvisFiles/`, `custom-skills/`, runtime
records and logs remain local and ignored. Large dependency directories and model
stores moved intact; the migration inventory records these as retained groups.

## Commands

Run commands from `app/` using its installed interpreter:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m jarvis.launcher --check
.\.venv\Scripts\python.exe -m scripts.audit.audit_repository --help
.\.venv\Scripts\python.exe -m scripts.catalog.build_catalog_index
.\.venv-training\Scripts\python.exe -m scripts.training.train_coding --help
```

Double-click `Start Jarvis.cmd` or `Stop Jarvis.cmd` for supervised use. Setup and
maintenance shortcuts are now in `launchers/`. Verification scripts retain their
original behavior: some use models, owned windows, networks or account-backed
workflows. The unit suite and readiness check are separate from those live checks.

## Compatibility and preservation

On this Windows installation, `InsTAREELS` is an ignored directory junction to
`app`. Existing environment activation paths and absolute local integration paths
continue resolving through it. Repository scans skip junctions. New checkouts use
`app` directly and do not require the alias; recreate environments with setup
commands when deploying to another machine.

The migration inventory, original maintained files and initial staged/unstaged
patches are stored only in `.jarvis-runtime/reorganization/`. No commit, reset,
stash or broad staging is performed. The existing Git index is preserved, so
legacy tracked paths can still appear through the junction until the relocation
is explicitly staged. When preparing a commit, review the saved original staged
patch, remove legacy index paths without deleting the junction target, and stage
the canonical paths deliberately.

No repository contents were intentionally deleted. Destination collisions abort
the move. Bootstrap recovery now includes the path helper; source snapshots cover
maintenance modules as well as application modules.

Three approved repository-skill snapshots now point to their canonical locations;
their pinned source bytes, approval states and outcomes are unchanged. The 37
enabled utility bindings were retained after reviewing the exact path changes and
running regression checks. The original utility validation receipt is preserved
as `artifacts/reports/utility-validation-before-relocation-20261009.json`. The
current receipt records this relocation review separately; its original live
trial dates and account evidence remain historical. No skills were newly approved
or activated by the migration.

## Verification record

The reorganization was performed on **2026-10-09–10 IST**. Ollama was briefly
restarted with explicit approval to release its old working-directory handle;
all 14 available models remained available. Jarvis was left stopped.

Final checks completed on **2026-10-10 IST**:

| Check | Result |
| --- | --- |
| Complete regression suite | 1,315 tests in 210.312 seconds; `OK (skipped=1)`. The actual repository-isolation class requires Docker's Linux engine, which was unavailable. |
| `python -m jarvis.launcher --check` | `ready`; no missing or incomplete requirements; configured Ollama models and LocalGithub available. |
| Preservation inventory | All 61,719 inventoried files and 798 retained groups present; no unexpected modifications or changed retained-group identities. |
| Private state and Git | Original task/UI/catalog/scan/backup hashes match; initial staged binary patch unchanged. |
| Existing environments | All seven interpreters run with the expected canonical prefixes; legacy activation paths remain covered by the junction; Hermes editable import points to its retained checkout. |
| Recovery | All 312 current application/bootstrap/maintenance source snapshots and the configuration backup match final source. Corrupt-helper restoration preserves the damaged copy in an isolated fixture. |
| Compatibility and launchers | Start/Stop execute the fixture bootstrap; canonical/alias routes share the application location and reject a second fixture lock; project scans skip junctions. |
| Catalog and checkpoint | Preserved catalog/index remains accessible and metadata matches; configured moved PC-training checkpoint exists. |
| Documentation | 1,007 local Markdown file/anchor targets checked; no missing targets. |
| Private ignores | Runtime inventory/state, secrets, models, environments, workspaces, custom skills and compatibility junction are ignored. |
| Final process state | No Jarvis application/supervisor process running; deliberate stop marker preserved. |

Detailed inventories, original source copies, patches, host check output and test
logs remain in ignored `.jarvis-runtime/reorganization/`. Large environment,
model and dependency trees were retained intact, rather than independently
rehashing every cached file. Earlier feature measurements in other guides retain
their dates and original validation limits. No live email writes, training jobs,
desktop workflows or microphone sessions were run for this reorganization.

Intermediate runs exposed relocated fixture/path failures, which were corrected;
their logs are retained locally. Sandbox filesystem/socket restrictions and
workspace temporary-directory locks also affected early runs. The final successful
suite ran on the host with its normal temporary directory.
