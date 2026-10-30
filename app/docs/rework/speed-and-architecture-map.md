# Jarvis step-by-step speed and architecture map

Date: 2026-10-30. Branch `claude_ControlArchitect`. Host: Windows 11, local Ollama, no cloud calls in tests.

This map follows one request through Jarvis. For each step it lists what runs, what it costs, how accurate it is, and what was changed or is still open. "Measured" means a timing taken on this machine on the date shown. Anything not measured is labelled as such.

## 1. Request path

```
utterance
  -> commands.py parser (rules; website-target rule sends to the planner)
  -> request_safety.refusal()        refuse registry/security/UAC/format/password requests
  -> engine.py -> actions.execute    task / open / run_command / write_text / ...
  -> brain.run (planner loop)
       _initial_steps                 native tool-calling plan (qwen3.5:9b via Ollama)
       per step: navigation decide    skipped for control-route steps
                 tool execution       control routes / app adapters / files / coder / MCP
                 observation          control read (UIA tree / browser AX refs), not a screenshot
       final verify                   one model call over fresh control evidence
  -> Dynamic Island progress (island_control.py tiles per route)
```

## 2. What the planner can see

| Source | Where it enters planning | Notes |
|---|---|---|
| Tool registry (`tools.py`, 34 specs: control 8, desktop 11, dom 4, browser 3, files 3, terminal 1) plus agent tools (`agent_tools.py`: MCP, coding, app adapters) | `native_tools.plan` tool list | `limit_tools` caps the offered set at 14 (core tools plus the companions of selected tools). |
| Route guide (`route_guide.py`) | `execution_strategy.hint()` | Ordered routes per target (spreadsheet, document, Blender, code, notes, text, calculation, drawing, web, media, email, files): structured APIs first, the app's own UI when the user asked for it, vision last. |
| Capability context (`capabilities.py`) | `capability_context` | Browser / pc_control / control_health groups. |
| Memory | `conversation_memory`, `skill_memory` (`step_planning`), `experience_memory`, Obsidian vault, Viking vectors (nomic-embed-text) | Live benchmark runs turn memory off or make it read-only, so runs cannot coach each other. H1 uses read-only memory for the user's profile facts. |
| MCP | `mcp_status` / `mcp_list_tools` / `mcp_call` | Configured servers: `spotify`, `youtube`. Listing and calling each need per-call approval. Blender uses its own adapter. |
| APIs | Gmail API (`gmail_api.py`, needs the user to reconnect), Office/PDF/Blender adapters, `FileAdapter` (create Tier 1, replace Tier 2 by sha256, no delete) | |

## 3. Step timings (measured 2026-10-30)

| Step | Before | After | Change |
|---|---|---|---|
| Planner call, 7.3k-token prompt, 9b on CPU | 174.5 s | n/a | baseline |
| 9b with 12 GPU layers (scheduler default) | 21.9 s | | |
| 9b with 20 GPU layers | 17.5 s | | not applied: the scheduler shares the GPU with vision models |
| 4b on GPU | 6.1 s | | candidate for simple steps (not yet built) |
| 2b on GPU | 2.6 s | | |
| Planning step through the real scheduler client | 40–48 s | 6–29 s | prompt fit to the real 8192 context, tool cap of 14, no decide call for control steps, no screenshot for control steps |
| Vision grounding (qwen3-vl 2b, then 4b on a miss) | | 93.8% on the grounding benchmark | crop-then-ground, label read-back, pre-click patch check |
| Notepad typing | batch SendInput lost characters | paced 15 ms per character for multi-line text | correctness over speed |
| S2 end to end (accepted) | | about 108 s | |

Context overflow was the largest hidden cost. The scheduler caps context at 8192 tokens, but prompts were sized for the model's full window, so Ollama truncated them and calls stalled. `native_tools.effective_context()` now reads the scheduler cap, and `FIT_ORDER` trims the prompt to fit.

## 4. Research applied

| Idea | Source | Status |
|---|---|---|
| Offer only the relevant tools | tool retrieval (arXiv 2602.17046, ToolSEE) | Done: `limit_tools`, `MAX_OFFERED=14` |
| Keep the stable prompt prefix first so the KV cache is reused | Ollama / llama.cpp prefix caching | Partly done: goal key moved last in the JSON; full prefix ordering is open |
| Replay a verified workflow instead of re-planning | Executable Agentic Memory, ActionEngine, AWM; survey arXiv 2609.02309 | Open |
| Small model first, escalate on doubt | RouteLLM / FrugalGPT (caveat: the router itself must be cheap and calibrated) | Done for vision (2b → 4b); open for planning |
| Focus mode: pause background Jarvis loops during a task | | Open |

## 5. Open items, in order

1. Prefix-cache-friendly prompt ordering for planning calls.
2. Plan replay for verified recipes (Notepad save, Calculator, Blender cylinder).
3. 4b cascade for single-tool steps, with a 9b check before anything consequential.
4. Focus mode during a task: pause memory summarising and anticipation loops.
5. Remove the 62 s `visual` call left in one recovery path.
