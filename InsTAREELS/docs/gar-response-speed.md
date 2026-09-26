# Response speed without changing models

Reviewed the local General-Agent-Runtime project at
`D:\Kunals GitHub Repo\General-Agent-Runtime`, starting with `run-gar.bat`,
then the Ollama adapter, planner, router and memory manager. The batch file
installs and starts GAR; it is not itself a fast-answer implementation.
GAR uses direct provider requests, bounded context and response schemas.
Its model router selects models, which was intentionally not adopted because
the requested upgrade must keep Jarvis's current models.

Jarvis already used direct local inference and disabled thinking for its normal
requests. These independently implemented changes remove additional overhead:

- Questions share a hidden, question-only Python worker and HTTP session instead
  of launching and importing Python dependencies for every answer.
- Normal answers use an explicit `answer`/`needs_web` JSON schema. Web verification,
  source links, history and screen handling retain their existing behavior.
- Each brain step discovers installed models once instead of twice. Discovery
  remains fresh on every step; answers and observations are never cached.

Model names, CPU/GPU settings, output limits and code validation are unchanged.
No new dependency or service is added; the existing question worker now stays
alive while Jarvis is running. Its process is checked before each request.
An unexpected exit permits one inference-only retry after a cancellable 0.5s
backoff. Cancellation kills only this owned child, invalidates old responses,
and never publishes a cancelled answer. Quit closes the worker. Timeouts and
model errors stop without retry. Repairs are silent and logged to the transcript
and `.jarvis-runtime/repairs.jsonl`. No desktop action is replayed.

Validation: 297 regression tests passed, including worker reuse, crash recovery,
shutdown during backoff, timeout, cancellation and screenshot forwarding.
Launcher check reported ready. A live local benchmark with unchanged
`qwen3.5:4b` and the same short question produced:

| Sample | Single-shot worker | Reusable worker |
| --- | ---: | ---: |
| First | 9.665 s | 2.951 s |
| Second | 3.017 s | 2.424 s |
| Third | 2.948 s | 2.508 s |

The first single-shot call includes model warmup and is not a fair speedup
comparison. The two subsequent warm samples averaged 2.983 s versus 2.466 s,
about 17% less elapsed time in this small test. These results do not establish
a general task speedup; long generations can still dominate latency.
Reproduce with `.venv\Scripts\python.exe verify_question_speed.py --live`.
