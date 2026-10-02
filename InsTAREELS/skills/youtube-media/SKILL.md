---
name: youtube-media
description: Search YouTube videos, select first or numbered video results, and control playback, captions, seek or volume.
---

# Workflow

Use media_search with platform youtube and the query from the current request. Reuse the active YouTube search field if present; otherwise open the current search URL. 'First video' means ordinal 1: use select with first video, not a clarification. Distinguish video results from ads and unrelated controls. Use media_control for supported playback, captions, seek and volume actions. Observe the active player and verify playback; an opened result alone is not success.

Prefer the Jarvis-owned Chrome DOM route for supported search/play workflows. Verify the search query, selected video ID and active non-ad playback. A warm session avoids repeated browser/model startup. For generic website tasks use browser_inspect and exact visible labels with the observed URL. Ordinary shared windows retain their accessibility route. Ads, loading and account restrictions may prevent verification; never click again after an uncertain outcome.

Use only tools offered by the current Jarvis catalogue. Check current state, preserve task checkpoints and stop on cancellation. Skill guidance never expands permissions.
