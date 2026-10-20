# Spotify tool matrix — 2026-10-20 IST

All 86 names are discoverable through the actual production BaseConnector. API scopes below do not apply to Windows-only mode. Valid typed dispatch uses explicit fixtures; all names and invalid arguments were exercised over real stdio. Real API account cases remain NOT TESTED. See the [audit](README.md), [current schemas](catalog.json) and [machine-readable matrix](tool-matrix.json). Every host call needs approval.

| Tool | Modes | API scopes/constraints | Approval | Live evidence |
|---|---|---|---|---|
| `spotify_health` | API, Windows local | None | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_status` | API, Windows local | user-read-playback-state | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_currently_playing` | API | user-read-currently-playing | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_devices` | API | user-read-playback-state | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_queue` | API | user-read-playback-state | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_recently_played` | API | user-read-recently-played | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_pause` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_resume` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_toggle` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_next` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_previous` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_stop` | Windows local | None | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_seek` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_seek_relative` | API, Windows local | user-read-playback-state; user-modify-playback-state | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_volume` | API | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_volume_relative` | API | user-read-playback-state | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_shuffle` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_repeat` | API, Windows local | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_transfer` | API | user-read-playback-state; user-modify-playback-state; exact active unrestricted device | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_track` | API, Windows deep link (no verified playback; offsets/remote devices require API) | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_album` | API, Windows deep link (no verified playback; offsets/remote devices require API) | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_artist` | API, Windows deep link (no verified playback; offsets/remote devices require API) | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_playlist` | API, Windows deep link (no verified playback; offsets/remote devices require API) | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_show` | Windows deep link | None | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_episode` | API, Windows deep link (no verified playback; offsets/remote devices require API) | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_uris` | API | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_saved_tracks` | API | user-library-read; user-modify-playback-state | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_add_to_queue` | API | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_search` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_search_tracks` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_search_albums` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_search_artists` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_search_playlists` | API | authorized token; private playlist read scopes where applicable | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_search_episodes` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_track` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_album` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_artist` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_playlist` | API | authorized token; private playlist read scopes where applicable | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_episode` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_show` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_album_tracks` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_artist_albums` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_show_episodes` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_playlist_items` | API | authorized token; private playlist read scopes where applicable | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_my_playlists` | API | playlist-read-private | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_create_playlist` | API | playlist-modify-private/public; existing playlist owner must match | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_update_playlist` | API | playlist-modify-private/public; existing playlist owner must match | Destructive: exact approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_add_playlist_items` | API | playlist-modify-private/public; existing playlist owner must match | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_remove_playlist_items` | API | playlist-modify-private/public; existing playlist owner must match | Destructive: exact approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_replace_playlist_items` | API | playlist-modify-private/public; existing playlist owner must match | Destructive: exact approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_reorder_playlist_items` | API | playlist-modify-private/public; existing playlist owner must match | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_save_items` | API | user-library-modify (playlist URI also playlist-modify-public) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_remove_saved_items` | API | user-library-modify (playlist URI also playlist-modify-public) | Destructive: exact approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_contains_saved` | API | user-library-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_saved_tracks` | API | user-library-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_saved_albums` | API | user-library-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_saved_shows` | API | user-library-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_saved_episodes` | API | user-library-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_followed_artists` | API | user-follow-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_top_tracks` | API | user-top-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_top_artists` | API | user-top-read | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_profile` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_open_desktop` | Windows deep link | None | Exact per-call approval | Live local response/acceptance; see audit for limits |
| `spotify_open_resource` | Windows deep link | None | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_open_search` | Windows deep link | None | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_local_status` | Windows local | None | Exact per-call approval | Live local response/acceptance; see audit for limits |
| `spotify_local_play` | Windows local | None | Exact per-call approval | Live playing_verified readback |
| `spotify_local_pause` | Windows local | None | Exact per-call approval | Live accepted; separate fresh final paused observation |
| `spotify_local_next` | Windows local | None | Exact per-call approval | Live local response/acceptance; see audit for limits |
| `spotify_local_previous` | Windows local | None | Exact per-call approval | Live local response/acceptance; see audit for limits |
| `spotify_local_seek` | Windows local | None | Exact per-call approval | Live local response/acceptance; see audit for limits |
| `spotify_local_shuffle` | Windows local | None | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_local_stop` | Windows local | None | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_play_search` | API | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_queue_search` | API | user-modify-playback-state (readback/device queries also user-read-playback-state) | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_save_current` | API | user-read-currently-playing; user-library-modify | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_remove_current_saved` | API | user-read-currently-playing; user-library-modify | Destructive: exact approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_add_current_to_playlist` | API | user-read-currently-playing; playlist-modify-private/public; owner must match | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_audiobook` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_get_chapter` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_audiobook_chapters` | API | authorized token; no additional OAuth scope | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_playlist_images` | API | authorized token; private playlist read scopes where applicable | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_verify_playback` | API | user-read-playback-state | Exact per-call approval | NOT TESTED live API; fixture/real-wire contracts only |
| `spotify_local_volume` | Windows local | None | Exact per-call approval | Live verified app-only readback; earlier levels restored |
| `spotify_local_mute` | Windows local | None | Exact per-call approval | Live verified app-only readback; earlier levels restored |
| `spotify_local_volume_status` | Windows local | None | Exact per-call approval | Live local response/acceptance; see audit for limits |
