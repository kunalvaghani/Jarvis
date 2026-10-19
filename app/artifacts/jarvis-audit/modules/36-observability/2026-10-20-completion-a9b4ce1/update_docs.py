"""Publish dated local verification and append unresolved work to the standing handoff."""
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
packet = 'artifacts/jarvis-audit/modules/36-observability/' + OUT.name
data = json.loads((OUT / 'baseline.json').read_text(encoding='utf-8'))
final, supplement = data['runs']['final-regression'], data['runs']['supplemental']
counts = f"{final['PASS']} passed / {final['FAIL']} failed / {final['SKIPPED']} skipped"

def block(path, body):
    text = path.read_text(encoding='utf-8')
    wrapped = '<!-- prompt36-observability -->\n' + body + '\n<!-- /prompt36-observability -->\n\n'
    if '<!-- prompt36-observability -->' in text:
        text = re.sub(r'<!-- prompt36-observability -->.*?<!-- /prompt36-observability -->\s*', lambda m: wrapped, text, flags=re.S)
    else:
        text = text.replace('<!-- prompt35-security -->', wrapped + '<!-- prompt35-security -->', 1)
    path.write_text(text, encoding='utf-8')

block(APP / 'README.md', f'''**2026-10-20 — Prompt 36 local observability repairs completed; release NOT READY.** Independent final relevant regression: **{counts}**. Separate evaluator/GPU admission fixtures: **{supplement['PASS']} passed / {supplement['SKIPPED']} skipped**. Overlapping runs are not summed. Tests use synthetic/owned fixtures and recording-fake providers; no real messages, cloud requests, mic/recording, inference, training, installs or deployment.

Tool events now carry monotonic nanoseconds and an opaque process clock ID alongside wall time; the host TaskState UUID is captured per registry call and shared with nested events. Skill history stores bounded metadata instead of arbitrary readback/error text, keeps JSON valid, and reports malformed legacy evidence. Selected-only tasks earn no execution/fallback/verified credit; explicitly refuted bound steps cannot earn verified credit. Cloud decision logs are version 2: categorical decisions, hashed correlation and payload size/digest, with no payload/advice/raw reason. Privacy-denied consultations are recorded without their contents.

Optional logging failures degrade diagnosis without repeating or bypassing tool policy. Journal append caps are **32 MiB for agent events / 8 MiB for cloud decisions**; existing evidence is preserved, with no automatic deletion or rotation. Historical raw files are not migrated. Five mocked read-only calls correlate through actual TaskState; 100 synthetic near-duplicate lesson trajectories produce one stored lesson, with DB growth measured.

Fresh benchmarks save **500 paired warm samples per two synthetic helper scenarios**, plus first-call pairs, raw data, source hashes, host profile, p50/p95/variance and a limited paired-mean CI. They measure safety overhead, not real assistant latency or throughput. Historical benchmark aggregates/code exist, but historical per-sample raw data was not found. Full voice/model/Verify/UI/background traces, global completion truth, physical stress/leak alerts and all-sink/dashboard acceptance remain incomplete. Isolated readiness remains `repair_required`. [Evidence]({packet}/verdict.md) · [Raw samples]({packet}/raw-samples.csv) · [Trace schema]({packet}/trace-schema.md) · [24-case denominator]({packet}/coverage-summary.json) · [Cumulative Claude handoff](docs/CLAUDE_HANDOFF.md).''')

block(APP.parent / 'README.md', f'''**2026-10-20 — Prompt 36 telemetry repairs verified locally; release NOT READY.** **{counts}** in the final relevant run. Repairs cover skill counter/evidence integrity, host task/monotonic correlation, bounded optional journals and metadata-only cloud decisions. Paired synthetic helper measurements are labelled as overhead, not real throughput. [Application details](app/README.md) · [Evidence](app/{packet}/verdict.md) · [Cumulative Claude handoff](app/docs/CLAUDE_HANDOFF.md).''')

handoff = APP / 'docs/CLAUDE_HANDOFF.md'
text = handoff.read_text(encoding='utf-8')
section = f'''## Prompt 36 — completed local observability repairs

**2026-10-20**, base a9b4ce1 plus retained P34/P35 and uncommitted P36 changes on codex-review. [Verdict](../{packet}/verdict.md), [patch/layer caveat](../{packet}/source-layers.json), [source hashes](../{packet}/source-hashes.json), [new tests](../tests/test_prompt36_observability.py), [24 case dispositions](../{packet}/tests.jsonl). The tracked-file diff overlaps P35 tool/cloud/skill changes; do not discard prior work when applying or reversing it. New test source is separately hashed. No fix commit, merge or deployment.

- **P36-001:** skill event evidence is bounded metadata, never JSON-string truncation or arbitrary text; failure detail withheld. Legacy evidence is sanitized on metrics read, malformed records counted. Historical DB/file contents are not silently deleted or migrated.
- **P36-002:** an explicitly refuted bound tool step cannot earn completed_verified credit even when a task claims completion. This is a counter guard; global task/UI truth and verifier provenance remain open below.
- **P36-003:** selected/no execution remains selected only; another executed route may count fallback. SQLite task/skill/event uniqueness survives reopen/repeated finish hooks.
- **P36-004:** host TaskState UUID captured per registry call, monotonic_ns and opaque clock_id added; wall time retained. Five mocked read-only dispatches produce actual correlated lifecycle rows. No universal voice-to-speech trace claimed.
- **P36-005:** journal OS failures/caps do not replay/block permitted calls or bypass deny policy. Agent journal cap 32 MiB, cloud cap 8 MiB, no automatic rotation/deletion. Diagnosis flags indicate lost/limited telemetry.
- **P36-006:** cloud decision v2 records categorical blocked/sent/returned states, hashed IDs and payload size/digest; no raw payload/advice/reason text. Mock outbound capture remains separate from production telemetry.

Final relevant regression: **{counts}**. Separate evaluator/GPU admission run: **{supplement['PASS']} pass / {supplement['FAIL']} fail / {supplement['SKIPPED']} skip**, not added to overlapping tests. Targeted final 59 pass. Baseline 128 pass/1 fail/1 skip: missing isolated Hermes data, not an intermittent flake. Original installed catalog verified with 210 rows and routed read-only for final tests; no assertions waived or packages installed. Initial new tests omitted two required folder arguments; corrected pinned-source probes establish the actual trace/logging defects. The probe's missing temporary directory was a harness correction, not an app fix.

Fresh 500 warm pairs per two synthetic scenarios plus first-call pairs yield 2,004 raw observations, source/host/seed provenance, variance and limited paired-mean confidence approximation. Current versus pinned 36fbf3ce median UI helper: 0.0552 vs 0.0316 ms; empty lease read: 0.18865 vs 0.1818 ms. These are overhead measurements on synthetic objects/files, not assistant speed/throughput, COM, model or voice latency. Historical raw N=500 data was not found; old aggregate/code preserved. See [raw samples](../{packet}/raw-samples.csv) and methodology. 100 synthetic near-duplicate trajectories create one lesson; DB grows from 40,960 to 65,536 bytes. No general semantic novelty/storage-bound claim.

Final skips: isolated OpenViking runtime guard, native symlink privilege, live DPI/multimonitor, UAC secure desktop and legacy arbitrary PDF-edit capability. Supplemental skip: forced stuck-CUDA-kernel interruption. Preserve capability unavailability; do not bypass validation or install an editor/runtime merely to turn this audit green.

## Prompt 36 — unresolved gates for Claude

| ID / status | Evidence / remaining problem | Required next action |
|---|---|---|
| **P36-R1 UNVERIFIED — verifier and global completion truth** | Explicit false readback stops verified skill credit, but host goal_verified provenance, historical/direct event insertion and all UI/task status consumers are not uniformly independent/version-bound. | Trace actual postconditions into authoritative counters/UI; inject self-claims, stale/conflicting/missing verifiers and ensure no verified count, green completion or trust promotion. Keep P31/P35 verifier handoffs open. |
| **P36-R2 BLOCKED — whole-pipeline/live performance** | Only task/tool/nested metadata correlation established. No actual ten warm commands/cold first tokens, live voice during LoRA/DGM, matched API/UIA/GUI, or 100-action RAM leak alert. | Add safe end-to-end STT/router/model/DAG/Verify/memory/UI/speech/recovery IDs, then run owned physical/model fixtures when authorized. Capture p95, cancellation, actual VRAM/RSS and failures. Never relabel helper measurements as throughput. |
| **P36-R3 UNVERIFIED — retention/export/dashboard** | Thread-local context and per-process append locks/caps tested. Cross-process journal integrity, crash persistence, sticky loss-status consumer behavior, complete dashboards/denominators and old raw log migration not proven. | Exercise concurrent writers/crashes/blocked sinks; define diagnosis/loss counters and export policy; audit every dashboard so failed/blocked/unrun remain visible. Preserve old files; obtain needed authorization for destructive migration/deletion. Broader privacy and reparse races carry forward. |
| **P36-R4 BLOCKED — evidence/measurement gaps** | Original raw N=500 samples unavailable; fresh replication saved. No intermittent flake, exact accuracy/p95 tradeoff or loss-down/heldout-down training experiment. | Preserve old aggregate provenance, collect new matched fixtures/seeds/manifests and label synthetic/live separately. Validate comparator manifest rejection and report held-out regressions without promotion. Do not invent missing historical samples. |

Still-blocked exact cases: 001/002 real warm/cold response latency; 003 full all-stage trace; 005 accuracy/p95 tradeoff; 006 intermittent flake; 007 actual GPU stress; 009 streamed-but-unverified final completion; 010 memory leak alert; 014 global UI status; 017 actual held-out training regression; 019 matched API/UIA/GUI; 022 physical foreground/background stress; 023 all dashboard truth; 024 every export/historical privacy. Individual fixture proofs are bounded in tests.jsonl. Isolated launcher --check remains repair_required; no service/model/setup was started to clear it. Full release **NOT READY**. Continue appending future unresolved work here.

'''
if '## Prompt 36 — completed local observability repairs' not in text:
    text = text.replace('## Prompt 35 — completed local security repairs', section + '## Prompt 35 — completed local security repairs', 1)
handoff.write_text(text, encoding='utf-8')

guide = APP / 'docs/CRASH_RECOVERY.md'
content = guide.read_text(encoding='utf-8')
addition = f'''
## Observability boundary — 2026-10-20

Optional journal failures degrade diagnosis without repeating a tool/consultation or overriding policy. Agent/cloud append caps preserve old files (32/8 MiB); no automatic deletion. Tool rows carry host task/monotonic clock metadata; cloud v2 rows retain categorical decisions and digests, not payload/advice. Skill history stores bounded metadata and reports malformed old evidence. Missing telemetry cannot establish verification or authorize retry.

[Prompt 36 verification](../{packet}/verdict.md): {counts}; remaining whole-pipeline/live/export gates are in the [Claude handoff](CLAUDE_HANDOFF.md). Historical raw logs remain untouched; these changes are not an all-log privacy or live recovery certificate.
'''
if '## Observability boundary — 2026-10-20' not in content:
    heading, rest = content.split('\n', 1)
    guide.write_text(heading + '\n' + addition + rest, encoding='utf-8')
print('Updated both READMEs, recovery guidance and cumulative handoff.')
