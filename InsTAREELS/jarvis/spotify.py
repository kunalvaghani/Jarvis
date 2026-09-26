"""Spotify app navigation and source-scoped Windows media transport controls."""
import asyncio
import os
from urllib.parse import quote


def search(query, cancelled=lambda: False):
    query = query.strip()
    if not query or len(query) > 300:
        raise ValueError("Name a song, artist, album, or playlist to find on Spotify.")
    if cancelled():
        raise ValueError("Spotify search cancelled.")
    os.startfile("spotify:search:" + quote(query, safe=""))
    return f"Opened Spotify search for {query}; choose a result to start playback."


def _spotify_session(manager):
    sessions = [session for session in manager.get_sessions()
                if "spotify" in session.source_app_user_model_id.casefold()]
    if not sessions:
        raise ValueError("Spotify has no active playback session. Play a song in Spotify first.")
    if len(sessions) > 1:
        raise ValueError("Multiple Spotify playback sessions are active; choose one in Spotify first.")
    return sessions[0]


async def _control(action, cancelled):
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    from winrt.windows.media import MediaPlaybackAutoRepeatMode

    if cancelled():
        raise ValueError("Spotify action cancelled.")
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    session = _spotify_session(manager)
    before = session.get_playback_info()
    status = before.playback_status.name.lower()

    if action == "status":
        media = await session.try_get_media_properties_async()
        title = media.title or "Unknown track"
        artist = media.artist or "Unknown artist"
        return f"Spotify is {status}: {title} by {artist}."

    methods = {
        "play": session.try_play_async,
        "pause": session.try_pause_async,
        "next": session.try_skip_next_async,
        "previous": session.try_skip_previous_async,
    }
    if action in methods:
        accepted = await methods[action]()
    elif action in {"shuffle_on", "shuffle_off"}:
        accepted = await session.try_change_shuffle_active_async(action == "shuffle_on")
    elif action in {"repeat_off", "repeat_one", "repeat_all"}:
        mode = {"repeat_off": MediaPlaybackAutoRepeatMode.NONE,
                "repeat_one": MediaPlaybackAutoRepeatMode.TRACK,
                "repeat_all": MediaPlaybackAutoRepeatMode.LIST}[action]
        accepted = await session.try_change_auto_repeat_mode_async(mode)
    elif action.startswith("seek_"):
        from datetime import timedelta
        seconds = int(action.split("_", 1)[1])
        timeline = session.get_timeline_properties()
        position = timeline.position + timedelta(seconds=seconds)
        position = max(timedelta(), min(position, timeline.end_time))
        accepted = await session.try_change_playback_position_async(int(position.total_seconds() * 10_000_000))
    else:
        raise ValueError("Unknown Spotify action.")
    if not accepted:
        raise ValueError(f"Spotify did not accept {action.replace('_', ' ')}.")
    if cancelled():
        raise ValueError("Spotify action cancelled after sending; check the app before repeating it.")

    # Windows acknowledges a transport request before the app updates its state.
    if action in {"play", "pause", "shuffle_on", "shuffle_off", "repeat_off", "repeat_one", "repeat_all"}:
        for _ in range(5):
            await asyncio.sleep(.15)
            if cancelled():
                raise ValueError("Spotify action cancelled after sending; check the app before repeating it.")
            info = session.get_playback_info()
            if action in {"play", "pause"} and info.playback_status.name.lower() == ("playing" if action == "play" else "paused"):
                return f"Spotify {('playing' if action == 'play' else 'paused')}."
            if action.startswith("shuffle_") and bool(info.is_shuffle_active) == (action == "shuffle_on"):
                return f"Spotify shuffle {'on' if action == 'shuffle_on' else 'off'}."
            if action.startswith("repeat_") and info.auto_repeat_mode == mode:
                return f"Spotify repeat {action.removeprefix('repeat_')}."
        return f"Spotify accepted {action.replace('_', ' ')}, but its updated state could not be verified."
    return f"Spotify accepted {action.replace('_', ' ')}."


def control(action, cancelled=lambda: False):
    return asyncio.run(_control(action, cancelled))


async def _is_playing():
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    try:
        session = _spotify_session(manager)
    except ValueError:
        return False
    return session.get_playback_info().playback_status.name.lower() == "playing"


def is_playing():
    return asyncio.run(_is_playing())


def volume(action, cancelled=lambda: False):
    """Change only Spotify's Core Audio sessions, never the system or browser level."""
    import comtypes
    from pycaw.pycaw import AudioUtilities
    comtypes.CoInitialize()
    try:
        sessions = []
        for session in AudioUtilities.GetAllSessions():
            process = session.Process
            try:
                name = process.name().casefold() if process else ""
            except Exception:  # A process can exit while audio sessions are enumerated.
                continue
            if name == "spotify.exe" and session.SimpleAudioVolume is not None:
                sessions.append(session.SimpleAudioVolume)
        if not sessions:
            raise ValueError("Spotify has no active Windows audio session. Start playback in Spotify first.")
        if cancelled():
            raise ValueError("Spotify volume action cancelled.")
        if action in {"mute", "unmute"}:
            muted = action == "mute"
            for level in sessions:
                level.SetMute(int(muted), None)
            if not all(bool(level.GetMute()) == muted for level in sessions):
                raise ValueError("Spotify mute change could not be verified.")
            return "Spotify muted." if muted else "Spotify unmuted."
        if action in {"up", "down"}:
            change = .1 if action == "up" else -.1
            target = max(0.0, min(1.0, sessions[0].GetMasterVolume() + change))
        else:
            target = int(action) / 100
            if not 0 <= target <= 1:
                raise ValueError("Choose a Spotify volume between 0 and 100 percent.")
        for level in sessions:
            level.SetMasterVolume(target, None)
        if not all(abs(level.GetMasterVolume() - target) <= .01 for level in sessions):
            raise ValueError("Spotify volume change could not be verified.")
        return f"Spotify volume {round(target * 100)} percent."
    finally:
        comtypes.CoUninitialize()
