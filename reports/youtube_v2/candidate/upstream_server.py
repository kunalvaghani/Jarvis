"""Generated MCP adapter for the extended YouTube connector. Do not edit manually.
Generate with python generate_server.py; do not print to stdout in MCP runtime.
"""
from __future__ import annotations
from mcp.server.fastmcp import FastMCP
from youtube_connector.youtube_v2 import YouTubeConnector

mcp = FastMCP("jarvis-youtube")
connector = YouTubeConnector()

@mcp.tool()
async def youtube_health() -> dict:
    """Inspect connector state and API/browser availability."""
    return await connector.health()

@mcp.tool()
async def youtube_search_videos(query: 'str', limit: 'int' = 5) -> dict:
    """Search videos using API key or visible browser."""
    return await connector.search_videos(query=query, limit=limit)

@mcp.tool()
async def youtube_search_playlists(query: 'str', limit: 'int' = 5) -> dict:
    """Search playlists using API key or visible browser."""
    return await connector.search_playlists(query=query, limit=limit)

@mcp.tool()
async def youtube_play_video(video: 'str') -> dict:
    """Find and play an exact video ID/URL or disambiguated query."""
    return await connector.play_video(video=video)

@mcp.tool()
async def youtube_play_playlist(playlist: 'str') -> dict:
    """Find/open and play a YouTube playlist."""
    return await connector.play_playlist(playlist=playlist)

@mcp.tool()
async def youtube_pause() -> dict:
    """Pause active YouTube video with verification."""
    return await connector.pause()

@mcp.tool()
async def youtube_resume() -> dict:
    """Resume active YouTube video with verification."""
    return await connector.resume()

@mcp.tool()
async def youtube_next_video() -> dict:
    """Next recommended video or playlist entry."""
    return await connector.next_video()

@mcp.tool()
async def youtube_previous_video() -> dict:
    """Previous playlist entry."""
    return await connector.previous_video()

@mcp.tool()
async def youtube_get_status() -> dict:
    """Inspect YouTube player status."""
    return await connector.get_status()

@mcp.tool()
async def youtube_seek(seconds: 'float') -> dict:
    """Seek to time in seconds."""
    return await connector.seek(seconds=seconds)

@mcp.tool()
async def youtube_seek_relative(seconds: 'float') -> dict:
    """Seek relative seconds."""
    return await connector.seek_relative(seconds=seconds)

@mcp.tool()
async def youtube_skip_forward(seconds: 'float' = 10) -> dict:
    """Skip forward N seconds."""
    return await connector.skip_forward(seconds=seconds)

@mcp.tool()
async def youtube_skip_back(seconds: 'float' = 10) -> dict:
    """Skip back N seconds."""
    return await connector.skip_back(seconds=seconds)

@mcp.tool()
async def youtube_seek_percent(percent: 'float') -> dict:
    """Seek to percent of duration."""
    return await connector.seek_percent(percent=percent)

@mcp.tool()
async def youtube_seek_to_start() -> dict:
    """Seek to beginning."""
    return await connector.seek_to_start()

@mcp.tool()
async def youtube_restart_video() -> dict:
    """Restart video."""
    return await connector.restart_video()

@mcp.tool()
async def youtube_set_volume(percent: 'float') -> dict:
    """Set playback volume percent."""
    return await connector.set_volume(percent=percent)

@mcp.tool()
async def youtube_volume_up(percent: 'float' = 10) -> dict:
    """Raise player volume."""
    return await connector.volume_up(percent=percent)

@mcp.tool()
async def youtube_volume_down(percent: 'float' = 10) -> dict:
    """Lower player volume."""
    return await connector.volume_down(percent=percent)

@mcp.tool()
async def youtube_mute() -> dict:
    """Mute video."""
    return await connector.mute()

@mcp.tool()
async def youtube_unmute() -> dict:
    """Unmute video."""
    return await connector.unmute()

@mcp.tool()
async def youtube_toggle_mute() -> dict:
    """Toggle player mute."""
    return await connector.toggle_mute()

@mcp.tool()
async def youtube_set_speed(rate: 'float') -> dict:
    """Set playback speed."""
    return await connector.set_speed(rate=rate)

@mcp.tool()
async def youtube_speed_up(delta: 'float' = 0.25) -> dict:
    """Increase speed."""
    return await connector.speed_up(delta=delta)

@mcp.tool()
async def youtube_speed_down(delta: 'float' = 0.25) -> dict:
    """Decrease speed."""
    return await connector.speed_down(delta=delta)

@mcp.tool()
async def youtube_set_video_loop(enabled: 'bool') -> dict:
    """Toggle HTML5 current video repeat."""
    return await connector.set_video_loop(enabled=enabled)

@mcp.tool()
async def youtube_media_status() -> dict:
    """Inspect full HTML media player state."""
    return await connector.media_status()

@mcp.tool()
async def youtube_toggle_fullscreen() -> dict:
    """Toggle YouTube fullscreen."""
    return await connector.toggle_fullscreen()

@mcp.tool()
async def youtube_toggle_theater() -> dict:
    """Toggle YouTube theater layout."""
    return await connector.toggle_theater()

@mcp.tool()
async def youtube_toggle_captions() -> dict:
    """Toggle captions via player control."""
    return await connector.toggle_captions()

@mcp.tool()
async def youtube_open_settings() -> dict:
    """Open YouTube player settings."""
    return await connector.open_settings()

@mcp.tool()
async def youtube_toggle_miniplayer() -> dict:
    """Toggle player miniplayer."""
    return await connector.toggle_miniplayer()

@mcp.tool()
async def youtube_toggle_autoplay() -> dict:
    """Toggle autoplay through UI."""
    return await connector.toggle_autoplay()

@mcp.tool()
async def youtube_next_frame() -> dict:
    """Advance approximate frame when paused."""
    return await connector.next_frame()

@mcp.tool()
async def youtube_previous_frame() -> dict:
    """Reverse approximate frame when paused."""
    return await connector.previous_frame()

@mcp.tool()
async def youtube_get_video_title() -> dict:
    """Get tab/video title."""
    return await connector.get_video_title()

@mcp.tool()
async def youtube_get_current_video_id() -> dict:
    """Read active video ID."""
    return await connector.get_current_video_id()

@mcp.tool()
async def youtube_get_current_playlist_id() -> dict:
    """Read active playlist ID."""
    return await connector.get_current_playlist_id()

@mcp.tool()
async def youtube_get_current_url() -> dict:
    """Read current URL."""
    return await connector.get_current_url()

@mcp.tool()
async def youtube_get_playback_time() -> dict:
    """Get player time/duration."""
    return await connector.get_playback_time()

@mcp.tool()
async def youtube_get_volume() -> dict:
    """Read volume/mute."""
    return await connector.get_volume()

@mcp.tool()
async def youtube_get_speed() -> dict:
    """Read playback speed."""
    return await connector.get_speed()

@mcp.tool()
async def youtube_reconnect_browser() -> dict:
    """Recreate dedicated browser session if disconnected."""
    return await connector.reconnect_browser()

@mcp.tool()
async def youtube_browser_reload() -> dict:
    """Reload current YouTube page."""
    return await connector.browser_reload()

@mcp.tool()
async def youtube_open_youtube_home() -> dict:
    """Navigate YouTube home."""
    return await connector.open_youtube_home()

@mcp.tool()
async def youtube_open_subscriptions() -> dict:
    """Open subscriptions page."""
    return await connector.open_subscriptions()

@mcp.tool()
async def youtube_open_history() -> dict:
    """Open YouTube history."""
    return await connector.open_history()

@mcp.tool()
async def youtube_open_watch_later() -> dict:
    """Open Watch Later playlist."""
    return await connector.open_watch_later()

@mcp.tool()
async def youtube_open_library() -> dict:
    """Open user library."""
    return await connector.open_library()

@mcp.tool()
async def youtube_open_channel(channel: 'str') -> dict:
    """Open channel by ID."""
    return await connector.open_channel(channel=channel)

@mcp.tool()
async def youtube_open_playlist(playlist: 'str') -> dict:
    """Open playlist by ID."""
    return await connector.open_playlist(playlist=playlist)

@mcp.tool()
async def youtube_open_search(query: 'str') -> dict:
    """Open visible search results."""
    return await connector.open_search(query=query)

@mcp.tool()
async def youtube_open_video(video: 'str') -> dict:
    """Open video without asserting playback started."""
    return await connector.open_video(video=video)

@mcp.tool()
async def youtube_browser_back() -> dict:
    """Navigate back in YouTube tab."""
    return await connector.browser_back()

@mcp.tool()
async def youtube_browser_forward() -> dict:
    """Navigate forward in YouTube tab."""
    return await connector.browser_forward()

@mcp.tool()
async def youtube_get_page_diagnostics() -> dict:
    """Inspect DOM player presence/controls."""
    return await connector.get_page_diagnostics()

@mcp.tool()
async def youtube_queue_add(video: 'str') -> dict:
    """Add single video to Jarvis-managed queue."""
    return await connector.queue_add(video=video)

@mcp.tool()
async def youtube_queue_add_many(videos: 'list[str]') -> dict:
    """Add many videos to Jarvis queue."""
    return await connector.queue_add_many(videos=videos)

@mcp.tool()
async def youtube_queue_list() -> dict:
    """List Jarvis-managed queue."""
    return await connector.queue_list()

@mcp.tool()
async def youtube_queue_clear() -> dict:
    """Clear Jarvis queue."""
    return await connector.queue_clear()

@mcp.tool()
async def youtube_queue_remove(index: 'int') -> dict:
    """Remove video by queue index."""
    return await connector.queue_remove(index=index)

@mcp.tool()
async def youtube_queue_move(old_index: 'int', new_index: 'int') -> dict:
    """Reorder queue item."""
    return await connector.queue_move(old_index=old_index, new_index=new_index)

@mcp.tool()
async def youtube_queue_play_next() -> dict:
    """Play next Jarvis queued video."""
    return await connector.queue_play_next()

@mcp.tool()
async def youtube_queue_set_repeat(enabled: 'bool') -> dict:
    """Enable repetition of Jarvis local queue."""
    return await connector.queue_set_repeat(enabled=enabled)

@mcp.tool()
async def youtube_queue_set_shuffle(enabled: 'bool') -> dict:
    """Set Jarvis queue shuffle preference."""
    return await connector.queue_set_shuffle(enabled=enabled)

@mcp.tool()
async def youtube_queue_shuffle_now() -> dict:
    """Randomize Jarvis queue order."""
    return await connector.queue_shuffle_now()

@mcp.tool()
async def youtube_queue_status() -> dict:
    """Inspect local queue settings."""
    return await connector.queue_status()

@mcp.tool()
async def youtube_queue_play_previous() -> dict:
    """Revisit last Jarvis-queued video."""
    return await connector.queue_play_previous()

@mcp.tool()
async def youtube_search_channels(query: 'str', limit: 'int' = 5) -> dict:
    """Search channels with Data API."""
    return await connector.search_channels(query=query, limit=limit)

@mcp.tool()
async def youtube_search_videos_filtered(query: 'str', limit: 'int' = 5, order: 'str' = 'relevance', video_duration: 'str' = 'any') -> dict:
    """Search videos with duration/sort filters using Data API."""
    return await connector.search_videos_filtered(query=query, limit=limit, order=order, video_duration=video_duration)

@mcp.tool()
async def youtube_get_video_details(video: 'str') -> dict:
    """Get video metadata via Data API."""
    return await connector.get_video_details(video=video)

@mcp.tool()
async def youtube_get_video_statistics(video: 'str') -> dict:
    """Get video stats via Data API."""
    return await connector.get_video_statistics(video=video)

@mcp.tool()
async def youtube_get_video_captions_metadata(video: 'str') -> dict:
    """Get captions metadata via OAuth."""
    return await connector.get_video_captions_metadata(video=video)

@mcp.tool()
async def youtube_get_channel_details(channel_id: 'str') -> dict:
    """Get channel metadata via Data API."""
    return await connector.get_channel_details(channel_id=channel_id)

@mcp.tool()
async def youtube_get_channel_videos(channel_id: 'str', limit: 'int' = 10) -> dict:
    """Get recent channel videos."""
    return await connector.get_channel_videos(channel_id=channel_id, limit=limit)

@mcp.tool()
async def youtube_get_playlist_details(playlist: 'str') -> dict:
    """Get playlist metadata."""
    return await connector.get_playlist_details(playlist=playlist)

@mcp.tool()
async def youtube_get_playlist_items(playlist: 'str', limit: 'int' = 50, page_token: 'str' = '') -> dict:
    """Get list of playlist entries."""
    return await connector.get_playlist_items(playlist=playlist, limit=limit, page_token=page_token)

@mcp.tool()
async def youtube_get_channel_playlists(channel_id: 'str', limit: 'int' = 25) -> dict:
    """Get playlists of specified channel."""
    return await connector.get_channel_playlists(channel_id=channel_id, limit=limit)

@mcp.tool()
async def youtube_get_video_comments(video: 'str', limit: 'int' = 20) -> dict:
    """Read public comments."""
    return await connector.get_video_comments(video=video, limit=limit)

@mcp.tool()
async def youtube_get_comment_replies(parent_id: 'str', limit: 'int' = 20) -> dict:
    """Read comment replies."""
    return await connector.get_comment_replies(parent_id=parent_id, limit=limit)

@mcp.tool()
async def youtube_get_video_categories(region_code: 'str' = 'US') -> dict:
    """Retrieve video categories by region."""
    return await connector.get_video_categories(region_code=region_code)

@mcp.tool()
async def youtube_get_trending_videos(region_code: 'str' = 'US', limit: 'int' = 20) -> dict:
    """Retrieve popular videos."""
    return await connector.get_trending_videos(region_code=region_code, limit=limit)

@mcp.tool()
async def youtube_get_my_channel() -> dict:
    """Read signed-in channel (OAuth)."""
    return await connector.get_my_channel()

@mcp.tool()
async def youtube_get_my_playlists(limit: 'int' = 25) -> dict:
    """Read owned playlists (OAuth)."""
    return await connector.get_my_playlists(limit=limit)

@mcp.tool()
async def youtube_get_my_subscriptions(limit: 'int' = 25) -> dict:
    """Read subscriptions (OAuth)."""
    return await connector.get_my_subscriptions(limit=limit)

@mcp.tool()
async def youtube_get_my_liked_videos(limit: 'int' = 25) -> dict:
    """Read liked videos (OAuth)."""
    return await connector.get_my_liked_videos(limit=limit)

@mcp.tool()
async def youtube_get_my_video_rating(video: 'str') -> dict:
    """Read my rating for specified video (OAuth)."""
    return await connector.get_my_video_rating(video=video)

@mcp.tool()
async def youtube_rate_video(video: 'str', rating: 'str') -> dict:
    """Like/dislike/unrate video (OAuth, approval)."""
    return await connector.rate_video(video=video, rating=rating)

@mcp.tool()
async def youtube_create_playlist(title: 'str', privacy: 'str' = 'private', description: 'str' = '') -> dict:
    """Create playlist (OAuth, approval)."""
    return await connector.create_playlist(title=title, privacy=privacy, description=description)

@mcp.tool()
async def youtube_update_playlist(playlist: 'str', title: 'str', description: 'str' = '', privacy: 'str' = 'private') -> dict:
    """Edit playlist (OAuth, approval)."""
    return await connector.update_playlist(playlist=playlist, title=title, description=description, privacy=privacy)

@mcp.tool()
async def youtube_delete_playlist(playlist: 'str') -> dict:
    """Delete playlist (OAuth, approval)."""
    return await connector.delete_playlist(playlist=playlist)

@mcp.tool()
async def youtube_add_video_to_playlist(playlist: 'str', video: 'str') -> dict:
    """Add video to playlist (OAuth, approval)."""
    return await connector.add_video_to_playlist(playlist=playlist, video=video)

@mcp.tool()
async def youtube_remove_playlist_item(item_id: 'str') -> dict:
    """Remove playlist entry (OAuth, approval)."""
    return await connector.remove_playlist_item(item_id=item_id)

@mcp.tool()
async def youtube_subscribe_channel(channel_id: 'str') -> dict:
    """Subscribe to channel (OAuth, approval)."""
    return await connector.subscribe_channel(channel_id=channel_id)

@mcp.tool()
async def youtube_unsubscribe_channel(subscription_id: 'str') -> dict:
    """Unsubscribe from channel (OAuth, approval)."""
    return await connector.unsubscribe_channel(subscription_id=subscription_id)

@mcp.tool()
async def youtube_add_comment(video: 'str', channel_id: 'str', text: 'str') -> dict:
    """Post comment (OAuth, approval)."""
    return await connector.add_comment(video=video, channel_id=channel_id, text=text)

@mcp.tool()
async def youtube_reply_comment(parent_id: 'str', text: 'str') -> dict:
    """Reply to comment (OAuth, approval)."""
    return await connector.reply_comment(parent_id=parent_id, text=text)

@mcp.tool()
async def youtube_delete_my_comment(comment_id: 'str') -> dict:
    """Delete own comment (OAuth, approval)."""
    return await connector.delete_my_comment(comment_id=comment_id)

@mcp.tool()
async def youtube_get_quota_hint() -> dict:
    """Get quota guidance and restrictions."""
    return await connector.get_quota_hint()

@mcp.tool()
async def youtube_next() -> dict:
    """Legacy compatibility alias of youtube_next_video."""
    return await connector.next_video()

@mcp.tool()
async def youtube_previous() -> dict:
    """Legacy compatibility alias of youtube_previous_video."""
    return await connector.previous_video()

@mcp.tool()
async def youtube_status() -> dict:
    """Legacy compatibility alias of youtube_get_status."""
    return await connector.get_status()

if __name__ == '__main__':
    mcp.run()
