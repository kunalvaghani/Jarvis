# Jarvis YouTube Connector v2 — Commands

Total: **103** typed MCP tools (100 primary + 3 legacy names), all `youtube_*` prefixed.

Every tool maps to an implemented method. Some methods depend on a live YouTube tab, a Google API key or OAuth.

| Tool | Signature | Description |
|---|---|---|
| `youtube_health` | `` | Inspect connector state and API/browser availability |
| `youtube_search_videos` | `query: 'str', limit: 'int' = 5` | Search videos using API key or visible browser |
| `youtube_search_playlists` | `query: 'str', limit: 'int' = 5` | Search playlists using API key or visible browser |
| `youtube_play_video` | `video: 'str'` | Find and play an exact video ID/URL or disambiguated query |
| `youtube_play_playlist` | `playlist: 'str'` | Find/open and play a YouTube playlist |
| `youtube_pause` | `` | Pause active YouTube video with verification |
| `youtube_resume` | `` | Resume active YouTube video with verification |
| `youtube_next_video` | `` | Next recommended video or playlist entry |
| `youtube_previous_video` | `` | Previous playlist entry |
| `youtube_get_status` | `` | Inspect YouTube player status |
| `youtube_seek` | `seconds: 'float'` | Seek to time in seconds |
| `youtube_seek_relative` | `seconds: 'float'` | Seek relative seconds |
| `youtube_skip_forward` | `seconds: 'float' = 10` | Skip forward N seconds |
| `youtube_skip_back` | `seconds: 'float' = 10` | Skip back N seconds |
| `youtube_seek_percent` | `percent: 'float'` | Seek to percent of duration |
| `youtube_seek_to_start` | `` | Seek to beginning |
| `youtube_restart_video` | `` | Restart video |
| `youtube_set_volume` | `percent: 'float'` | Set playback volume percent |
| `youtube_volume_up` | `percent: 'float' = 10` | Raise player volume |
| `youtube_volume_down` | `percent: 'float' = 10` | Lower player volume |
| `youtube_mute` | `` | Mute video |
| `youtube_unmute` | `` | Unmute video |
| `youtube_toggle_mute` | `` | Toggle player mute |
| `youtube_set_speed` | `rate: 'float'` | Set playback speed |
| `youtube_speed_up` | `delta: 'float' = 0.25` | Increase speed |
| `youtube_speed_down` | `delta: 'float' = 0.25` | Decrease speed |
| `youtube_set_video_loop` | `enabled: 'bool'` | Toggle HTML5 current video repeat |
| `youtube_media_status` | `` | Inspect full HTML media player state |
| `youtube_toggle_fullscreen` | `` | Toggle YouTube fullscreen |
| `youtube_toggle_theater` | `` | Toggle YouTube theater layout |
| `youtube_toggle_captions` | `` | Toggle captions via player control |
| `youtube_open_settings` | `` | Open YouTube player settings |
| `youtube_toggle_miniplayer` | `` | Toggle player miniplayer |
| `youtube_toggle_autoplay` | `` | Toggle autoplay through UI |
| `youtube_next_frame` | `` | Advance approximate frame when paused |
| `youtube_previous_frame` | `` | Reverse approximate frame when paused |
| `youtube_get_video_title` | `` | Get tab/video title |
| `youtube_get_current_video_id` | `` | Read active video ID |
| `youtube_get_current_playlist_id` | `` | Read active playlist ID |
| `youtube_get_current_url` | `` | Read current URL |
| `youtube_get_playback_time` | `` | Get player time/duration |
| `youtube_get_volume` | `` | Read volume/mute |
| `youtube_get_speed` | `` | Read playback speed |
| `youtube_reconnect_browser` | `` | Recreate dedicated browser session if disconnected |
| `youtube_browser_reload` | `` | Reload current YouTube page |
| `youtube_open_youtube_home` | `` | Navigate YouTube home |
| `youtube_open_subscriptions` | `` | Open subscriptions page |
| `youtube_open_history` | `` | Open YouTube history |
| `youtube_open_watch_later` | `` | Open Watch Later playlist |
| `youtube_open_library` | `` | Open user library |
| `youtube_open_channel` | `channel: 'str'` | Open channel by ID |
| `youtube_open_playlist` | `playlist: 'str'` | Open playlist by ID |
| `youtube_open_search` | `query: 'str'` | Open visible search results |
| `youtube_open_video` | `video: 'str'` | Open video without asserting playback started |
| `youtube_browser_back` | `` | Navigate back in YouTube tab |
| `youtube_browser_forward` | `` | Navigate forward in YouTube tab |
| `youtube_get_page_diagnostics` | `` | Inspect DOM player presence/controls |
| `youtube_queue_add` | `video: 'str'` | Add single video to Jarvis-managed queue |
| `youtube_queue_add_many` | `videos: 'list[str]'` | Add many videos to Jarvis queue |
| `youtube_queue_list` | `` | List Jarvis-managed queue |
| `youtube_queue_clear` | `` | Clear Jarvis queue |
| `youtube_queue_remove` | `index: 'int'` | Remove video by queue index |
| `youtube_queue_move` | `old_index: 'int', new_index: 'int'` | Reorder queue item |
| `youtube_queue_play_next` | `` | Play next Jarvis queued video |
| `youtube_queue_set_repeat` | `enabled: 'bool'` | Enable repetition of Jarvis local queue |
| `youtube_queue_set_shuffle` | `enabled: 'bool'` | Set Jarvis queue shuffle preference |
| `youtube_queue_shuffle_now` | `` | Randomize Jarvis queue order |
| `youtube_queue_status` | `` | Inspect local queue settings |
| `youtube_queue_play_previous` | `` | Revisit last Jarvis-queued video |
| `youtube_search_channels` | `query: 'str', limit: 'int' = 5` | Search channels with Data API |
| `youtube_search_videos_filtered` | `query: 'str', limit: 'int' = 5, order: 'str' = 'relevance', video_duration: 'str' = 'any'` | Search videos with duration/sort filters using Data API |
| `youtube_get_video_details` | `video: 'str'` | Get video metadata via Data API |
| `youtube_get_video_statistics` | `video: 'str'` | Get video stats via Data API |
| `youtube_get_video_captions_metadata` | `video: 'str'` | Get captions metadata via OAuth |
| `youtube_get_channel_details` | `channel_id: 'str'` | Get channel metadata via Data API |
| `youtube_get_channel_videos` | `channel_id: 'str', limit: 'int' = 10` | Get recent channel videos |
| `youtube_get_playlist_details` | `playlist: 'str'` | Get playlist metadata |
| `youtube_get_playlist_items` | `playlist: 'str', limit: 'int' = 50, page_token: 'str' = ''` | Get list of playlist entries |
| `youtube_get_channel_playlists` | `channel_id: 'str', limit: 'int' = 25` | Get playlists of specified channel |
| `youtube_get_video_comments` | `video: 'str', limit: 'int' = 20` | Read public comments |
| `youtube_get_comment_replies` | `parent_id: 'str', limit: 'int' = 20` | Read comment replies |
| `youtube_get_video_categories` | `region_code: 'str' = 'US'` | Retrieve video categories by region |
| `youtube_get_trending_videos` | `region_code: 'str' = 'US', limit: 'int' = 20` | Retrieve popular videos |
| `youtube_get_my_channel` | `` | Read signed-in channel (OAuth) |
| `youtube_get_my_playlists` | `limit: 'int' = 25` | Read owned playlists (OAuth) |
| `youtube_get_my_subscriptions` | `limit: 'int' = 25` | Read subscriptions (OAuth) |
| `youtube_get_my_liked_videos` | `limit: 'int' = 25` | Read liked videos (OAuth) |
| `youtube_get_my_video_rating` | `video: 'str'` | Read my rating for specified video (OAuth) |
| `youtube_rate_video` | `video: 'str', rating: 'str'` | Like/dislike/unrate video (OAuth, approval) |
| `youtube_create_playlist` | `title: 'str', privacy: 'str' = 'private', description: 'str' = ''` | Create playlist (OAuth, approval) |
| `youtube_update_playlist` | `playlist: 'str', title: 'str', description: 'str' = '', privacy: 'str' = 'private'` | Edit playlist (OAuth, approval) |
| `youtube_delete_playlist` | `playlist: 'str'` | Delete playlist (OAuth, approval) |
| `youtube_add_video_to_playlist` | `playlist: 'str', video: 'str'` | Add video to playlist (OAuth, approval) |
| `youtube_remove_playlist_item` | `item_id: 'str'` | Remove playlist entry (OAuth, approval) |
| `youtube_subscribe_channel` | `channel_id: 'str'` | Subscribe to channel (OAuth, approval) |
| `youtube_unsubscribe_channel` | `subscription_id: 'str'` | Unsubscribe from channel (OAuth, approval) |
| `youtube_add_comment` | `video: 'str', channel_id: 'str', text: 'str'` | Post comment (OAuth, approval) |
| `youtube_reply_comment` | `parent_id: 'str', text: 'str'` | Reply to comment (OAuth, approval) |
| `youtube_delete_my_comment` | `comment_id: 'str'` | Delete own comment (OAuth, approval) |
| `youtube_get_quota_hint` | `` | Get quota guidance and restrictions |
| `youtube_next` | `()` | Legacy compatibility alias for `youtube_next_video` |
| `youtube_previous` | `()` | Legacy compatibility alias for `youtube_previous_video` |
| `youtube_status` | `()` | Legacy compatibility alias for `youtube_get_status` |
