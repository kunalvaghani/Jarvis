# Generated natural conversation

2026-10-15 IST question-worker follow-up: uncertain or malformed local answers
with private/session/app evidence stay local and report a gap rather than trigger
public search. Empty search, unsafe citation URLs and nonexistent citation numbers
are refused. Concurrent callers share one serialized transport; limits are checked
before dispatch, and request status/UUID metadata contains no question or answer.
[Audit evidence and remaining limitations](../artifacts/jarvis-audit/modules/06-questions-context/inventory.md).

Updated 2026-10-14 IST. Jarvis starts quietly and lets the user lead. Greetings,
wellbeing replies and thanks no longer return canned strings. The current
configuration enables `knowledge.natural_conversation` with `qwen3.5:0.8b`.
Conversation is generated with a calm butler style, emotional acknowledgement,
useful concise advice, and recent dialogue. This is language-model generation,
not a claim of human consciousness, independent goals or universal correctness.

## Routing and context

Short social remarks and conversational follow-ups within two minutes use a
compact local path. It retains the latest six messages, up to 500 characters
each, plus a bounded relevant user profile and requested tone. It avoids the
saved-session selector, full catalogue enrichment and the planner's GPU lease.
Explicit research, current facts, code, screen/file questions and selected memory
retain the existing general-question path. Complex/public questions can still
use the configured Groq gateway; private conversation history stays local.

Time, date, weather and other existing utility results become grounding data
for generated wording instead of being returned directly when this mode is
enabled. Behaviour explanations likewise use their existing capability facts
as reference data. Task controls, approvals, action receipts and failures retain
their operational semantics; conversational generation has no action tools and
cannot execute a proposed action. Model wording can still be inaccurate.

## Speed and configuration

The owned question worker starts in the background and primes the local model
and stable prompt. Generation uses `think: false`, streaming, a 2048-token
context, 160-token output ceiling, six CPU threads, and a 30-minute keep-alive.
CPU inference avoids contention with the existing CUDA F5 voice and task GPU
work. No new Python dependency, third-party repository or long-running service
was added. The existing worker timeout, cancellation and shutdown handling apply.
If the model fails, Jarvis reports the failure rather than substituting a stock
conversation answer. The output ceiling does not silently accept truncated text.

Set `knowledge.natural_conversation.enabled` to false to use the general model
path for social replies and direct factual utility wording. Canned social replies
and unsolicited startup greetings remain removed. Change `.model` only to an
installed Ollama model; stronger models can take longer. Restart Jarvis after
changing code or configuration.

Two seconds is a target, not a universal guarantee. F5 now receives completed
conversation phrases while text arrives and plays synthesized chunks early
([delivery and measured limits](f5-voice.md)). Each phrase still needs synthesis;
model loading, transcription, synthesis, busy CPUs,
research and longer reasoning can exceed two seconds. Fast conversation uses a
smaller model, which can give generic or shallow responses and does not replace
the stronger general-question model.

## Research and verification

Firecrawl retrieved official [Ollama chat API](https://docs.ollama.com/api/chat),
[streaming](https://docs.ollama.com/capabilities/streaming), and
[keep-alive/FAQ](https://docs.ollama.com/faq) documentation. The implementation
uses their streaming, thinking controls, prompt history and warm-model retention
methods. It does not download or execute code from search results.

2026-10-14 IST: 148 selected conversation, quick-answer, Groq, voice, launcher,
recovery and GPU tests passed; 20 knowledge tests passed through their required
discovery import path. An earlier named-module run could not import a knowledge
test helper; discovery resolved that test invocation issue. Full launcher
readiness reported `ready`.

The final real question-worker benchmark used four synthetic turns, without
private profile/history, microphone input or speaker playback:

| Turn | First visible text | Full text reply |
|---|---:|---:|
| First greeting, including worker startup/prompt priming | 2.172 s | 2.485 s |
| Rough-day remark | 0.312 s | 0.703 s |
| Follow-up about meetings | 0.406 s | 1.062 s |
| Thanks | 0.406 s | 1.110 s |

These are single-run measurements, not latency percentiles or an acoustic
two-second guarantee. The preliminary longer prompt produced slower, more
verbose replies; the final prompt requests a short sentence. Generated greetings
can still sound conventional even though they are not stored templates. Human
conversation-quality evaluation and full microphone-to-speaker latency remain
unmeasured. Repeat with `python -m scripts.verification.verify_natural_conversation
--worker` from the application environment; results stay in ignored
`.jarvis-runtime/natural-conversation-verification-worker.json`.
