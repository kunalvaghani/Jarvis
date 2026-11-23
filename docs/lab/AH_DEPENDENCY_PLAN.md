# A–H repair: concrete dependency approval scopes

4 November 2026 IST. Existing environments and shipped flags stay unchanged. Official metadata is retained in [ah-official-dependency-metadata.json](evidence/ah-official-dependency-metadata.json). No package has been downloaded or installed by that metadata audit.

## 1. Mechanics and scientific views

Proposed new `app/.venv-discovery-mechanics` environment, Python3.11, containing MuJoCo3.17.0, Trimesh5.2.0 and Matplotlib3.11.2 plus their resolved dependencies. PyPI reports Windows CPython3.11 wheels for MuJoCo/Matplotlib and a pure-Python Trimesh wheel. Main application NumPy/SciPy/Pydantic and the approved Pint environment are untouched.

Scope requested: binary wheels only from official PyPI/files.pythonhosted.org; maximum250 MB downloaded and2 GB owned disk; lock exact versions/URLs/SHA-256 before installation, inspect licenses and refuse an incompatible or non-reviewed license rather than silently proceeding. No source builds, admin, PATH change, system dependency, paid service, model/GPU download or global activation. No CUDA/driver changes. Fixed CPU-only structured-model workers and code-checked goldens/acceptance may run at most50 invocations, with persistent non-refundable slots, existing daily CPU admission and bounded subprocess deadlines. This does not authorize generated Python/plugin execution on the host; that must remain in the existing reviewed sandbox. No robot/hardware actuation.

This setup removes missing mechanics/mesh/plot dependencies. It does not itself prove B/C, fix autonomous decomposition, or permit an acceptance pass without actual independent evidence.

## 2. Chrono dependency planning only

Official PyChrono10.0.0 Windows release metadata lists a527,155,156-byte Python3.12 package and CUDA/MKL dependencies. Therefore a small CPU-only installation must not be assumed. No Chrono package install is requested in this scope.

Proposed official micromamba2.10.0-0 Windows executable:

- URL: `https://github.com/mamba-org/micromamba-releases/releases/download/2.10.0-0/micromamba-win-64.exe`
- Size:11,723,264 bytes;15 MB binary-download cap.
- SHA-256: `f8b4284bd4eb1134122eaf93b3ea6c7be567e596de5829e1a6f478e34e41974a`, independently published as the official GitHub release-asset digest.
- Place only under `app/.jarvis-runtime/discovery/tools/micromamba-2.10.0-0/`; inspect its license/provenance before execution.

Requested execution: `--version`, reviewed CLI help, then one bounded `create --dry-run --json` resolution for the exact Windows PyChrono10.0.0/Python3.12 release build in a new Jarvis-owned root/cache. Use public projectchrono/release and conda-forge channels only, no user RC configuration, no activation/admin/PATH change or package install. Cap metadata cache at200 MB and the owned planner process at120 seconds. Save the exact dependency/file/hash/license/size plan; stop before fetching package binaries or executing package scripts. A later concrete install plan requires separate approval.

This scope does not approve CUDA libraries/drivers, Chrono installation, a new WSL distro, cloud compute or untrusted generated code. If the solver requires more resources or a different version, record that finding rather than silently changing the scope.
