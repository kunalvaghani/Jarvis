# Copyright (c) ModelScope Contributors. All rights reserved.
# Portions adapted from Ultron under Apache-2.0; see integrations/ULTRON-LICENSE.
"""Local, read-only recall helpers. Memories are evidence, never action queues."""
from datetime import datetime, timezone
import math
import re
import time
from functools import lru_cache

@lru_cache(maxsize=4096)
def _iso_timestamp(value):
    stamp = datetime.fromisoformat(value)
    return (stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)).timestamp()


def hotness(last_hit_at, now=None, alpha=0.03):
    """Adapt Ultron's continuous time decay to UTC and Unix timestamps."""
    if last_hit_at is None:
        return 0.0
    try:
        if isinstance(last_hit_at, str):
            last_hit_at = _iso_timestamp(last_hit_at)
        last_hit_at = float(last_hit_at)
        if not math.isfinite(last_hit_at):
            return 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0
    days = max(((time.time() if now is None else now) - last_hit_at) / 86400.0, 0)
    return math.exp(-alpha * days)

def hotness_many(stamps, now=None, alpha=.03):
    """Vectorized numeric batches; bounded cached parsing for persisted ISO dates."""
    if len(stamps)<32:
        return [hotness(value,now,alpha) for value in stamps]
    import numpy as np
    now = time.time() if now is None else now
    values=[]
    for value in stamps:
        try:
            values.append(_iso_timestamp(value) if isinstance(value,str) else float(value))
        except (ValueError,TypeError,OverflowError):values.append(float('nan'))
    values=np.asarray(values,dtype=np.float64)
    return np.where(np.isfinite(values),np.exp(-alpha*np.maximum((now-values)/86400.,0)),0.).tolist()


def memory_score(relevance, last_hit_at, now=None):
    # Adapted from MemoryService.search's weighted time-decay score.
    return relevance * (0.2 + 0.8 * hotness(last_hit_at, now))


_STOP = set("the a an and to in on of for with please open launch start show do this that".split())


def recall_tasks(tasks, goal, kind, limit=3, now=None):
    """Return compact summaries of relevant verified successes, without plans."""
    words = set(re.findall(r"\w+", goal.casefold())) - _STOP
    if not words:
        return []
    ranked = []
    for task in tasks:
        if not isinstance(task, dict) or task.get("kind") != kind or task.get("status") != "completed":
            continue
        if not any(item.get("stage") == "verified" for item in task.get("checkpoints", [])):
            continue
        # An uncertain later action invalidates a previously verified checkpoint.
        uncertain = False
        for item in task.get("checkpoints", []):
            if item.get("stage") in {"acting", "action_attempted"}:
                uncertain = True
            elif item.get("stage") == "verified":
                uncertain = False
        if uncertain or any(item.get("attempted") for item in task.get("failures", [])):
            continue
        title = str(task.get("goal", ""))[:240]
        other = set(re.findall(r"\w+", title.casefold())) - _STOP
        overlap = len(words & other) / max(len(words | other), 1)
        if overlap < 0.35:
            continue
        ranked.append((overlap, task.get("updated_at"),
                       {"goal": title, "summary": str(task.get("result", ""))[:400]}))
    weights=hotness_many([row[1] for row in ranked],now=now)
    ranked=[(row[0]*(.2+.8*weight),row[2]) for row,weight in zip(ranked,weights)]
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    result, seen = [], set()
    for _, memory in ranked:
        key = memory["goal"].casefold()
        if key not in seen:
            result.append(memory)
            seen.add(key)
        if len(result) >= max(0, min(limit, 3)):
            break
    return result if limit > 0 else []
