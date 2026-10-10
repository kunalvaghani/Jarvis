# Fast planning, task queue and natural conversation — 2026-10-10 IST

Jarvis now plans and acts one step at a time with far less waiting, keeps a spoken
conversation going like a call, queues the tasks you give it during that conversation
and works through them in the background, and understands natural phrasing such as
"let's make an email" or "let's watch a video on YouTube".

## Try it

Say "Jarvis" once. Jarvis then stays in the conversation until 10 minutes pass without
you speaking, or you say "goodbye", "that's all" or "go to sleep".

- `Jarvis, let's watch a video about cats on YouTube`
- `Go to Wikipedia and open the article about black holes` — said while the first task
  runs, it waits in line: "Okay, I'll do that next."
- `How are you doing?` — answered while tasks keep running
- `What are you working on?` / `What's in the queue?`
- `Cancel this task` stops only the current task; `Stop all tasks` clears the queue
- Cancel one task by describing it (added later on 2026-10-10): `cancel the YouTube one`, `never mind the email`,
  `remove the second task` / `remove number 2` (numbers as read by "what's in the queue"), `cancel the last one`,
  `never mind` (your most recent request), `remove all previous tasks`, `cancel everything except the email`.
  Matching uses positions, then keywords with simple synonyms, then the small model for paraphrases; when two tasks
  match equally, Jarvis asks which one ([task_queue.py](../jarvis/task_queue.py)).
- `Let's make an email` — Jarvis asks what it should say; answer naturally, for example
  `to name at gmail dot com saying the meeting moved to Friday`
- `I want to see a video about cooking on YouTube`, `Let's listen to lofi`
- `Goodbye` ends listening; queued tasks keep running and their results are still spoken

Ordinary talk ("I'm feeling tired today") gets a spoken reply; it is not treated as a task.

## What changed

**Inference speed on this computer.** The planner (`qwen3.5:9b`, 6.6 GB) is larger than
the RTX 3050's 4 GB, so it runs split across GPU and CPU. The [GPU scheduler](../jarvis/gpu_scheduler.py)
already placed 10–12 layers on the GPU. Measurements showed where the rest of the time went,
and each cause is now addressed:

| Cause (measured) | Change |
| --- | --- |
| The model unloaded 30 s after each call; reloading cost ~10 s and lost its cache | `gpu_scheduler.warm_seconds` 1800: stays loaded |
| Ollama picked its own CPU thread count | `gpu_scheduler.cpu_threads` 12 (4 left for speech/UI) |
| A screenshot on every step added ~1,400 prompt tokens (~34 s) | Screenshots only for recovery, unconfirmed outcomes or windows with fewer than six readable controls; planner copies downscaled to 1024 px |
| Every step re-read the whole 7–9k-token prompt: the hybrid Qwen3.5 model reuses its cache only when a prompt **extends** the previous one | Each task's planner calls form one growing conversation ([native_tools.py](../jarvis/native_tools.py)) |
| Extra "decide" and screenshot-verification model calls per step (20–70 s each, and the screenshot check sometimes misjudged the page) | Navigation/read-only steps skip the decide call; verification checks the window change and the next planning call judges the outcome |
| 28 tool definitions (~3,900 tokens) sent for every task | File, terminal, media, live-data and catalogue tools offered only for related requests; skill-guided tools always kept |

**Step-by-step execution and recovery** ([brain.py](../jarvis/brain.py)). Each step is executed as
soon as it is planned. If a step fails, is rejected, or its result is not visible, the reason goes
back to the planner, which plans a different next step from that point, not from the start. This
repeats up to `brain.max_recoveries` (default 5) different approaches. A failed or already-completed
action is never repeated; a repeated proposal is fed back once as a correction. Uncertain outcomes of
actions that could have changed data (files, commands, typing, closing apps, approval tools) still
stop and ask, as required by the repository safety rules.

**Desktop fixes found during live testing:**

- Apps and pages opened by Jarvis are brought to the front ([window_focus.py](../jarvis/window_focus.py)),
  so Jarvis inspects the right window. This uses thread-input attachment and sends no keystroke; an ALT
  tap would switch Notepad into menu-key mode.
- New `type_text` tool for editors whose text area is not a listed field (Windows 11 Notepad, Word).
  It types only text that appears verbatim in the request, into the window just observed.
- Keyboard typing pauses 10 ms per character: Windows 11 Notepad garbled faster input
  ("abc jarvis" became "abc zzzzz"). This also applies to write commands and push-to-write
  ([writing by voice](push-to-write.md)), which replaced dictation mode.
- An exact app name wins: `open chrome` no longer asks "chrome or google chrome?".

**Conversation** ([conversation_intent.py](../jarvis/conversation_intent.py), [actions.py](../jarvis/actions.py),
[engine.py](../jarvis/engine.py), [knowledge.py](../jarvis/knowledge.py)):

- New requests queue behind running work instead of cancelling it (previously a new task replaced
  the running one). Each task has its own cancel token.
- Openers ("let's", "I want to", "can we", "go ahead and") are removed when an action verb follows.
  Hedges ("maybe", "we should", "how about") are never turned into actions.
- Speech no rule recognises is classified as chat or task by simple rules, then by `qwen3.5:0.8b`
  on the CPU (about 1–3 s); on any doubt it is treated as chat.
- "Jarvis" in the middle of a sentence during a conversation is part of what you said, not a new
  wake word (it previously cut the sentence).
- Clarification answers are merged into the original request.
- Small talk never triggers a web search ("how are you doing today?" previously searched the web
  and took 40 s).
- A new topic is answered directly. Jarvis asks which saved conversation to use only when you refer
  to the past ("remember…", "last time", "we discussed…").

## Configuration

In [config/config.json](../config/config.json):

| Setting | Value | Meaning |
| --- | --- | --- |
| `wake_timeout_seconds` | 600 | Silence that ends a conversation (was 90) |
| `suggestion_seconds` | 90 (default) | How long on-screen control suggestions stay active after waking |
| `gpu_scheduler.warm_seconds` | 1800 | Keep the planner loaded (0–3600) |
| `gpu_scheduler.cpu_threads` | 12 | CPU threads for the split model's CPU layers (0 = Ollama default) |
| `brain.planner_images` | `auto` (default) | `always` restores a screenshot on every step; `never` disables them |
| `brain.fused_verification` | `true` (default) | `false` restores the separate screenshot verification call |
| `brain.max_recoveries` | 5 (default) | Different approaches tried before a task pauses |

No new paid API, dependency or service was added. Web answers keep using the existing free search.

## Measurements — live, 2026-10-10 IST

These are live measurements on this computer (RTX 3050 Laptop 4 GB, 16 CPU threads, 31 GB RAM,
`qwen3.5:9b`). Before/after numbers come from the same harness and real tasks; model timings
come from Ollama's own counters.

| Scenario | Before | After |
| --- | --- | --- |
| Planning call, same step, model kept loaded vs cold | 66.6 s | 11.4 s |
| Planning call without a screenshot (cold) | 66.6 s | 34.4 s |
| Next step in a task (prompt reading) | 17.6–24 s | 1.2–5.5 s |
| "Go to Wikipedia and open the article about black holes" | 209 s, failed (screenshot check said no browser) | 68.5 s, finished |
| "Open Notepad and type hello from jarvis" | failed (parsed as app name; no typing tool) | 58.6 s, exact text |
| "How are you doing today?" first spoken words | 40.1 s (web search) | 5.7 s |
| "What is a good quick dinner idea?" | no answer (waited for saved-conversation choice) | 3.7 s |
| Follow-up "Why is that one healthy?" | lost the topic | answered in context, 10.4 s |

The [live verification report](../artifacts/reports/fast-conversation-live.json)
([script](../scripts/verification/verify_fast_conversation_live.py)) passed: both desktop tasks
finished; in the simulated spoken call the YouTube task finished in 3.0 s, the queued Wikipedia task
was acknowledged and finished at 53.7 s, a question was answered at 4.1 s while the task ran, queue
status was reported and an unrecognised statement was answered as chat, with no warnings. Approval
requests were refused by the script; none were raised. The report holds flags and timings only.

The call was simulated by feeding final transcripts to the real voice engine; microphone capture
and spoken playback were not part of this check, and no live microphone session is claimed.

## Limitations

- The first planning call of each task still reads the full prompt (~7–9k tokens, about 15–20 s)
  because the cache cannot be rewound to a shared prefix on this model.
- Generation runs at about 4–6 tokens per second; most of each step's remaining time is the model
  writing its tool call.
- Questions and tasks share one model. A question asked while the planner is mid-call waits for that
  call (up to ~30 s; 21 s observed).
- In call mode Jarvis listens to everything said nearby for up to 10 minutes; lower
  `wake_timeout_seconds` for noisy rooms.
- Approvals for sending, deleting and writing are still a click in the Jarvis window.
- Replying to and forwarding email remain unsupported.

## Verification

- Fixture tests: [test_fast_conversation.py](../tests/test_fast_conversation.py) (22 tests) plus updated
  recovery, queue, engine and conversation-context tests.
- Regression, 2026-10-10 IST: **1,358 tests ran in 213.073 s, OK with one skipped class**
  ([log](../artifacts/logs/fast-conversation-regression.log)). The skipped class is live repository
  isolation, because Docker's Linux engine was unavailable.
- `python -m jarvis.launcher --check` reports `ready`.
