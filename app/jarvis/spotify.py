"""Spotify app navigation and source-scoped Windows media transport controls."""
import asyncio
import os
import threading
import time
from urllib.parse import quote


def open_app(cancelled=lambda: False):
    if cancelled():
        raise ValueError('Spotify launch cancelled.')
    try:
        os.startfile('spotify:')
    except OSError as exc:
        raise ValueError('The native Spotify app or its URI handler is unavailable. Install Spotify or explicitly request its web player.') from exc
    return 'Opened the native Spotify app.'


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

    if action in {"play", "pause"} and status == ("playing" if action == "play" else "paused"):
        return f"Spotify {status}."

    methods = {
        "play": session.try_play_async,
        "pause": session.try_pause_async,
        "next": session.try_skip_next_async,
        "previous": session.try_skip_previous_async,
    }
    track = await _track(session) if action in {"next", "previous"} else None
    previous_position = (session.get_timeline_properties().position.total_seconds()
                         if action == "previous" and track else None)
    if cancelled():
        raise ValueError("Spotify action cancelled before sending.")
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
        if cancelled():
            raise ValueError("Spotify action cancelled before sending.")
        accepted = await session.try_change_playback_position_async(int(position.total_seconds() * 10_000_000))
    else:
        raise ValueError("Unknown Spotify action.")
    if not accepted:
        raise ValueError(f"Spotify did not accept {action.replace('_', ' ')}.")
    if cancelled():
        raise ValueError("Spotify action cancelled after sending; check the app before repeating it.")

    if track:
        # Confirm the track really changed. Spotify's "previous" first restarts the current song, so when the
        # title stays the same and the song is back at the start, one more "previous" reaches the earlier track.
        again = action == "previous" and previous_position is not None and previous_position > 2.5
        for _ in range(12):
            await asyncio.sleep(.15)
            if cancelled():
                raise ValueError("Spotify action cancelled after sending; check the app before repeating it.")
            now = await _track(session)
            if now and now != track:
                return f"Now playing {now[0]} by {now[1]}."
            if again and now == track and session.get_timeline_properties().position.total_seconds() < 2.5:
                again = False
                if cancelled():
                    raise ValueError("Spotify action cancelled after sending; check the app before repeating it.")
                if not await session.try_skip_previous_async():
                    return "Spotify restarted the current song but did not accept previous track."
        return f"Spotify accepted {action}, but the track change could not be verified."

    # Windows acknowledges a transport request before the app updates its state.
    if action in {"play", "pause", "shuffle_on", "shuffle_off", "repeat_off", "repeat_one", "repeat_all"}:
        for _ in range(10):
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


async def _track(session):
    """(title, artist) of the current Spotify track, or None when it cannot be read."""
    try:
        media = await session.try_get_media_properties_async()
        return (media.title, media.artist) if media and media.title else None
    except Exception:
        return None


def _on_media_thread(operation, cancelled, timeout=6.):
    """WinRT needs MTA; desktop libraries initialize the caller as STA.

    Fence late dispatch after timeout/cancellation, and never retry mutations.
    The async timeout also bounds read-back after an accepted command.
    """
    if cancelled():
        raise ValueError("Spotify action cancelled before sending.")
    stopped = threading.Event()
    deadline = time.monotonic() + timeout
    result = {}

    def abort():
        return stopped.is_set() or time.monotonic() >= deadline or cancelled()

    def run():
        initialized = False
        try:
            from winrt.runtime import ApartmentType, init_apartment, uninit_apartment
            init_apartment(ApartmentType.MULTI_THREADED)
            initialized = True
            if abort():
                raise ValueError("Spotify action cancelled before sending.")
            result["value"] = asyncio.run(asyncio.wait_for(operation(abort), timeout))
        except Exception as exc:
            result["error"] = exc
        finally:
            if initialized:
                uninit_apartment()

    worker = threading.Thread(target=run, daemon=True, name="jarvis-spotify-control")
    worker.start()
    while worker.is_alive() and not abort():
        worker.join(.05)
    if worker.is_alive() or isinstance(result.get("error"), (TimeoutError, asyncio.TimeoutError)):
        stopped.set()
        raise ValueError("Spotify request could not be verified. Check playback before repeating; no retry was sent.")
    if "error" in result:
        raise result["error"]
    return result["value"]


def control(action, cancelled=lambda: False):
    return _on_media_thread(lambda abort: _control(action, abort), cancelled)


async def _is_playing():
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    try:
        session = _spotify_session(manager)
    except ValueError:
        return False
    return session.get_playback_info().playback_status.name.lower() == "playing"


def is_playing():
    return _on_media_thread(lambda abort: _is_playing(), lambda: False)


def _audio_sessions():
    """Include Spotify routed to a non-default speaker/headset in Windows."""
    from pycaw.pycaw import AudioUtilities, AudioSession, IAudioSessionControl2, EDataFlow, DEVICE_STATE
    from comtypes import COMError
    sessions = []
    for device in AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value):
        try:
            manager = device.AudioSessionManager
            if manager is None:
                continue
            enumerator = manager.GetSessionEnumerator()
            for index in range(enumerator.GetCount()):
                control = enumerator.GetSession(index)
                if control is not None:
                    sessions.append(AudioSession(control.QueryInterface(IAudioSessionControl2)))
        except (OSError, COMError):
            # An endpoint can disconnect during enumeration; other outputs remain usable.
            continue
    return sessions


def volume(action, cancelled=lambda: False):
    """Change only Spotify's Core Audio sessions, never the system or browser level."""
    import comtypes
    initialized = False
    try:
        comtypes.CoInitialize()
        initialized = True
    except OSError as exc:
        # An existing MTA apartment is usable for Core Audio too. Do not
        # uninitialize COM owned by another library on this thread.
        if getattr(exc, 'winerror', None) != -2147417850:
            raise
    try:
        sessions = []
        for session in _audio_sessions():
            try:
                process = session.Process
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
                if cancelled():
                    raise ValueError("Spotify volume action cancelled; check the app before repeating it.")
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
            if cancelled():
                raise ValueError("Spotify volume action cancelled; check the app before repeating it.")
            level.SetMasterVolume(target, None)
        if not all(abs(level.GetMasterVolume() - target) <= .01 for level in sessions):
            raise ValueError("Spotify volume change could not be verified.")
        return f"Spotify volume {round(target * 100)} percent."
    finally:
        if initialized:
            comtypes.CoUninitialize()
