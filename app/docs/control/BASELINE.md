# Control baseline (legacy) — pending the live round

The user asked on 2026-11-02 to run every live test together after implementation. This file is filled in by the live round:

    python benchmarks/live/cases.py control --pc legacy --web legacy --repeat 5 --telemetry --full
    python benchmarks/live/cases.py control --pc legacy --web legacy --repeat 2 --telemetry --full   # cold: apps closed first
    python scripts/brain_baseline.py <start time> benchmarks/results/control-legacy.json "control legacy"

For each scenario it records:
- verified success and p50/p95 end-to-end time;
- time to first action, actions and model calls;
- wasted retries, focus changes (steals), and peak RAM and VRAM.

The raw JSONL goes to `benchmarks/results/live/C*.jsonl`.
