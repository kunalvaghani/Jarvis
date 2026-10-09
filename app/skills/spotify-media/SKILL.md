---
name: spotify-media
description: Open the Spotify app, search music or playlists, play tracks, and control queue, repeat, shuffle, volume or playback.
---

# Workflow

Open native Spotify through the installed app catalogue before considering the website. Use media_search platform spotify or spotify_search, and a fresh visible result selection. Use spotify_control/media_control for supported player/library/queue actions. Do not substitute a similarly named track silently. Verify playback through the Windows Spotify media session when available. Login, unavailable controls and account restrictions need current evidence; never infer success from launching the app.

Current Spotify exposes the search query as a ComboBox and song rows as DataItems under Search results, with artist metadata in child rows. Match both song title and artist from fresh results; exclude library playlists, albums and music videos. A direct explicit song workflow can avoid model planning. Use one exposed Play action or native double-click on the freshly verified song row, then check actual playback. Never retry an uncertain click.

Use only tools offered by the current Jarvis catalogue. Check current state, preserve task checkpoints and stop on cancellation. Skill guidance never expands permissions.
