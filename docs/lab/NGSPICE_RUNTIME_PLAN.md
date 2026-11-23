# B6 Linux ngspice proof proposal

## Current authorization supersedes the old 24-attempt stop — 2026-11-04 IST

The user explicitly authorized **50 free-local ngspice attempts**. Exact scope `user-approved-free-local-divider-proof-50-2026-11-04`; earlier 24 attempts are retained, not reset. Current usage **37/50**. Existing library hashes, fixed ideal-divider topology, non-root/no-network sandbox, CPU/RAM/PID/host limits and no host fallback remain unchanged. Windows release 47 remains preparation-only. No new package/download/image/system change.

Requalification/fresh reuse passed (20.594 s / 3.703 s), as did five real numeric boundary cases and synthetic offline speech-file → existing brain → sandbox. A narrow units-normalization fix handles ASR-attached V/Ω. Live microphone/approval UI and autonomous research/install/authoring are still open. [Boundary receipt](evidence/ngspice-fifty-edge-cases.json) · [Speech-file receipt](evidence/b6-speech-file-proof.json) · [Current checks](evidence/c2-local-verification.json). Earlier proposal and exhausted-24 statements below describe the prior checkpoint only.

2026-11-04 IST. Status: **user approved Linux preparation and bounded sandbox tests; operator-assisted proof executed**. The Windows release-47 preparation approval remains preparation-only.

The existing immutable Jarvis repository sandbox is Debian 13 (trixie), Linux amd64, image `sha256:fc3e504b26346d8fcfcadbb393fb7020c4f2b92c81f78c188b3711d2f40a9e0e`. A read-only, network-disabled metadata probe found libc/libgcc/libstdc++ but no libgomp. Do not replace the image or install host packages.

Use the official [ngspice shared-library interface](https://ngspice.sourceforge.io/shared.html) through the **existing RepositorySandbox runner**, including its seccomp process/network restrictions, non-root user, read-only source, 256 MB RAM, 16 PIDs, 0.5 CPU and five-second CPU limit. The adapter accepts only bounded scalar inputs for a fixed DC resistor divider; no user netlist, arbitrary SPICE command, model/plugin file, shell, network or hardware action. Results must be checked independently against Ohm's law and Kirchhoff's current law. This proves only an ideal resistor DC model, not temperature response, battery physics or general circuit support.

Proposed acquisition: download the following two Debian amd64 archives via HTTPS to a new Jarvis-owned private runtime folder; **10 MB cumulative download cap, 32 MB extracted-file cap**. Verify the official SHA-256 below before parsing. Extract only package data, inspect copyright/control metadata, and never run package maintainer scripts. Preserve licenses. No dpkg/apt install, system PATH change, Docker pull/build, image replacement or core environment mutation.

| Package | Version | Bytes | Official SHA-256 |
|---|---|---:|---|
| libngspice0 | 44.2+ds-1 | 2,503,956 | d1b9dec8b93f8785c6e8bf6ecea05fc94d6b4c7e60ee8e7df0589e3a2a62822a |
| libgomp1 | 14.2.0-19 | 137,148 | 72b7a1a33c48f3195efeb044111b34ae684b1e640bb6495c832443b798601cd5 |

Official metadata: [libngspice0 download/checksum](https://packages.debian.org/trixie/amd64/libngspice0/download), [libgomp1 download/checksum](https://packages.debian.org/trixie/amd64/libgomp1/download). Paths: `https://deb.debian.org/debian/pool/main/n/ngspice/libngspice0_44.2+ds-1_amd64.deb` and `https://deb.debian.org/debian/pool/main/g/gcc-14/libgomp1_14.2.0-19_amd64.deb`.

Version 44.2 is a deliberate compatibility pin for this proof, **not release 47**. Debian runtime libraries and their license exceptions require review; the already-inspected Windows COPYING cannot attest to these different archives. If hashes, ABI, dependencies, license/security gate or sandbox fail, stop transparently. No automatic download of additional dependencies or host fallback.

Execution scope after approval and review: bounded divider golden cases and independent verified uses through the existing brain, using a scratch Journal/configuration first, plus fresh-session reuse timing. At most 20 solver invocations for this proof, each using the existing runtime limits and a 15-second host timeout; no retries after an uncertain result. Keep shipped Lab flags off. Registration/promotion requires actual golden and independent code-checked uses, never synthetic fixtures. Voice/microphone acceptance remains a separate unexecuted gate.

The master prompt and repository rules require concrete approval for every install/download and unknown-tool execution. This proposal does not itself grant that approval.

Final current evidence: [runtime summary](evidence/ngspice-runtime-summary.json), [learning](evidence/ngspice-brain-learn.json), [fresh-process reuse](evidence/ngspice-brain-reuse.json). The user subsequently approved four additional attempts (24 total), all now consumed, including two failed initial calls; no additional execution beyond the batch is inferred. Spoken and autonomous acquisition acceptance remain unexecuted.

Final invalid-request refusal and proof-cap boundary tests pass; final qualification/reuse 19.407 s / 3.313 s, focused suite 177 passed. The original 20-attempt preparation proposal above is historical; the four-attempt extension was separately approved and recorded. No execution beyond 24 is inferred.
