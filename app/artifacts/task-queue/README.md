# Durable task queue evidence — 2026-10-23 IST

Candidate branch `codex/autonomous-task-queue`. [Behavior, architecture, configuration, commands and open gates](../../docs/autonomous-task-queue.md) · [Cumulative handoff](../../docs/CLAUDE_HANDOFF.md).

Latest follow-up restores the user's earlier voice profile and adds task-bound clarification and independently read-back file receipts. Full release acceptance remains open; the historical checkpoints below are not substitutes for the current run.

| Latest receipt | Scope and result |
|---|---|
| [Final Windows-gate focused regression](windows-gate-focused-regression.txt) | **335 passed in 35.38 s**, including corrected WTS lock detection, admission-order dependencies/control exclusion, punctuation, decision presentation, continuation, privacy and approvals. |
| [Actual production App/Island integration](live-main-app-queue.json) | **Passed**, 10 typed-entry jobs completed and files reopened. Real App event drain revealed Queue, mapped the 20-second question, applied its automatic preference and retained Queue during results. Isolated owned configuration disables microphone, speech, accounts and learning; regular stopped session untouched. Panel screenshot was blank/rejected, so no full-app screenshot is claimed. |
| [Decision presentation and deadline regression](decision-presentation-regression.txt) | **327 passed in 33.91 s**. Includes explicit native Queue presentation, preserving its visible options during streamed/plain background answers, and applying only the automatic preference at the deadline boundary. |
| [Restored-profile focused regression](restored-voice-regression.txt) | **323 passed in 47.93 s**, queue/voice/checkpoints/commands/Groq/WhatsApp/context/anticipation/approval-binding regressions. |
| [Current full application regression](release-full-regression.txt) | **4,054 passed / 150 gated skips / zero failures / one existing COM warning**, **1,098.25 s (18m 18s)**. Complete application suite, not a certification of gated hardware/accounts/endurance. |
| [Current frozen source](release-source-inventory.json) | **513** runtime/config/test/verification Python sources and configuration files hashed before the current full run. |
| [Current source integrity](release-source-integrity.json) | Exit **0**, all **513** frozen source hashes unchanged after the full suite. |
| [Final scope/state check](final-scope-check.json) | Correct branch, unchanged source, restored medium.en/100 ms/fixed endpoint, deliberate Stop marker preserved, no new installs/downloads; full release acceptance remains false. |
| [Actual mixed queue acceptance](live-mixed-intake.json) | **10/10 completed**, seven owned file byte-readback receipts, two actual host memory observations and real Knowledge local-time answer. All three read-only/question jobs completed while the first write worker was held. Actual mapped native choice resolved automatically after **20.05 s**, no fake clock. Typed/injected final text; not physical speech, external accounts or overnight endurance. |
| [Actual process-crash recovery](live-process-crash-recovery.json) | **Passed**. Owned child exited after a real file readback but before completion. A new Actions instance recovered it as PAUSED/uncertain, refused unsafe resume, preserved the file unchanged and completed the separately queued file. No unrelated processes or user files touched. |
| [Actual mixed overnight-mode batch](live-overnight-mixed-batch.json) | **20 jobs: 17 COMPLETED, one deliberate FAILED, one WAITING_DEPENDENCY, one WAITING_APPROVAL**. All 11 expected files/readback receipts verified; existing file preserved; sensitive handler never dispatched; report equals persisted history. Actual presented choice resolved at **20.13 s**. Short fixture batch, not extended endurance. |
| [Corrected physical Windows lock test](live-windows-lock-wts.json) | **Passed**. User locked/unlocked; session remained locked **22.20 s**, gate false across **181 observations**, file deferred throughout, read-only memory check completed while locked, file completed after unlock. |
| [Initial lock-gate failure](live-windows-lock.json) | Initial input-desktop-only gate observed only **1.69 s** during a user-reported 15-second lock. Preserved as a failure; corrected with official WTS session-state gate. |
| [Actual optional power API](live-power-api.json) | **Passed** request/release on an owned thread; default `prevent_sleep=false` unchanged. Does not certify physical sleep or overnight endurance. Corrected desktop gate mean **0.425 ms** over 200 unlocked samples, not a latency percentile or full scheduler cost. |
| [Restored-profile physical microphone receipt](live-headphone-restored-profile.json) | User confirmed earlier behavior restored, but strict receipt is **8/10 files**, two missing commands and preference still pending at Finish. Not passed. [All physical attempts and rollback](../../docs/voice-profile-restoration.md). |
| [Launcher after authorized services startup](launcher-restored-services.txt) | **Ready**, no missing/incomplete components. Main Jarvis and microphone remain stopped. Docker/Ollama startup was explicitly authorized. |
| [Final launcher readiness](launcher-final-check.txt) | **Ready**, no missing/incomplete components after the final WTS/queue fixes. Regular assistant and microphone remain stopped. |
| [Fresh local model inference](model-benchmark-restored-services.json) | Existing 0.8B and 9B each **3/3** public JSON matches through GPU admission. Median **3.855/11.351 s**; first **17.822/34.695 s**, loading/lease and concurrent regression load included. No p95 or speedup claim. |
| [Current native Queue view](native-queue-current.png) | Actual owned native widget including task-bound answer field; synthetic state only, no unrelated desktop. |
| [Previous full failure](full-approval-adapter-failure.txt) | **4,021 passed / 8 failed / 150 skipped**. All eight approval adapters lacked a full App/Actions; optional hook lookup fixed and expanded focused checks passed. |
| [Interrupted for voice restoration](release-interrupted-voice-restoration.txt) | Incomplete run, deliberately stopped to honor the user's requested earlier voice path. |
| [Decision-presentation checkpoint](checkpoint-predecision-presentation.txt) | Incomplete earlier full run, stopped for the subsequently verified deadline/presentation fixes. Not a full pass. |
| [Dependency-burst checkpoint](checkpoint-predependency-burst.txt) | Incomplete earlier full run, stopped to fix a dependency binding to a later admission during a burst. Final focused checks include the fix and control-command exclusion. |
| [Current admission repeat](admission-benchmark-restored-profile.json) | 200 no-effect outcomes persisted; WAL median/p95 **0.6498/0.9720 ms**, dispatch **0.6947/1.0475 ms**, wall **0.942 s**, sampled RSS **20.51→22.86 MB**. Concurrent regression load included; not speech/endurance throughput. |
| [Current documentation links](link-release-check.json) | **777 local targets**, no missing files at the recorded checkpoint; checked again after final documentation. Does not validate remote URLs or Markdown anchors. |
| [Experimental silence comparison](asr-silence-comparison.json) | Five generated/public fixtures per policy. Decoder filtering experiment suppressed silence hallucinations but was reverted from production at the user's request. |
| [Continuation/voice regression](continuation-voice-regression.txt) | **152 passed in 25.77 s** before restored-profile follow-up. |

| Receipt | Scope and result |
|---|---|
| [Focused regression](focused-regression.txt) | **139 passed in 13.54 seconds**. Includes actual temporary-file Engine/Actions work, actual Knowledge worker with mocked inference, native Tk widgets, SQLite persistence and simulated resource/failure/decision tests. |
| [Expanded final focused regression](focused-final-regression.txt) | **300 passed in 29.95 seconds**, including Groq/offline controls, pending WhatsApp free-text prompts, conversation context and anticipation after the final submit/clarification fixes. |
| Earlier complete run | Superseded by preserved approval-adapter failure and the current full run above. Do not treat this historical index row as a pass. |
| [Earlier frozen source](source-inventory.json) | Historical 21-file runtime/config/test/verification checkpoint, superseded by the current 513-file inventory. |
| [Launcher readiness](launcher-check.txt) | Ready, no missing/incomplete components. Optional cloud/account integration was not live checked. |
| [Admission benchmark](admission-benchmark.json) | 200 synthetic no-effect jobs; WAL admission median/p95 0.6600/1.0791 ms versus memory FIFO 0.0045/0.0050 ms. RSS samples are not peaks. This checkpoint preceded final snapshot/report/parser refinements. |
| [Final-source admission repeat](admission-benchmark-final.json) | 200/200 synthetic outcomes; WAL median/p95 **0.6621/0.9406 ms**, dispatch **0.7332/0.8977 ms**. Recorded while full regressions were active; not causal throughput evidence. |
| [Earlier source integrity](source-integrity.json) | Historical 21-file checkpoint only; does not certify current follow-up sources or completion of the full suite. |
| [Configured local model probes](model-benchmark.json) | Installed local 0.8B and 9B, 3/3 public JSON matches each; median 3.446/9.428 s, loading/lease waits included. No cloud request/download and no general quality claim. |
| [Native queue fixture](native-queue-fixture.png) | Actual owned QueueView capture with synthetic persisted task/resource/approval state. No unrelated desktop or private task database captured. Not a real overnight/account run. |
| [Link audit](link-check.json) | New documentation links checked; regenerated after the evidence index was created. |
| [Earlier Tk startup failure](focused-tk-startup-failure.txt) | 138 passed / one Tk library initialization failure. Isolated native test passed; unchanged combined rerun passed 139. Failure retained rather than hidden. |
| [Interrupted checkpoint](checkpoint-interrupted.txt) | Early full run interrupted for source refinements; incomplete, not a pass. |
| [Offline-control checkpoint](checkpoint-offline-control-failure.txt) | An interrupted full run exposed the offline-control bypass regression. The isolated mocked test reproduced it; the public submit path was fixed and the expanded 182-test focused run passed. Incomplete, not a full-suite pass. |
| [Clarification-refinement checkpoint](checkpoint-clarification-refinement.txt) | Full run interrupted to preserve explicitly queued work during a pending free-text prompt. The expanded focused run passed after the fix; this checkpoint is incomplete. |
| [Parser-refinement checkpoint](checkpoint-parser-refinement.txt) | Later full run interrupted to fix deadline/list punctuation before command cleanup; incomplete, not a pass. |

Reproduce from the application directory with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_autonomous_queue.py tests/test_realtime_voice.py tests/test_task_state.py tests/test_jarvis.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m jarvis.launcher --check
.\.venv\Scripts\python.exe scripts/verification/benchmark_task_queue.py --output artifacts/task-queue/admission-benchmark-final.json
.\.venv\Scripts\python.exe scripts/verification/benchmark_queue_models.py --output artifacts/task-queue/model-benchmark-new.json
.\.venv\Scripts\python.exe scripts/verification/render_queue_fixture.py --output artifacts/task-queue/native-queue-fixture-new.png
```

The renderer briefly displays its own synthetic native window and captures only that window with PrintWindow. Off-screen Windows renders were blank and rejected; they are not presented as UI evidence. The actual ten-file integration check is separate from the visual fixture. Physical microphone attempts and user feedback are recorded above; complete speech acceptance remains open. Windows session lock/sleep, live accounts and prolonged overnight operation remain unexecuted. The inspection sandbox denied existing temporary-file rename tests; relevant tests were rerun outside it without weakening runtime controls. No packages, drivers or models were installed for this upgrade.
