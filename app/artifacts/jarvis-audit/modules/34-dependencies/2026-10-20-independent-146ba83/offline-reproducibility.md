# Offline reproduction plan / current blockers

Preserve working envs and installed models. Build reviewed per-interpreter/platform/CUDA constraints and a complete hash-verified wheelhouse in an explicitly authorized staging environment; include exact Python build, native wheels and browser artifacts. Resolve transitive distributions and licenses, test with indexes disabled, compare package/import/SBOM snapshots, run compatibility/fidelity/ABI tests, then seek approval for promotion. Keep old interpreter/weights until replacement passes. Do not deduplicate environments solely because two share a version: F5 and brain have intentionally incompatible transformer/torch groups.

No clean install, upgrade, uninstall, WSL distro launch or destructive recreation occurred here; those acceptance steps remain BLOCKED. Missing models/packages must produce a clear blocker without downloads. Currently P34-001/002 violate the executor admission part of that boundary.
