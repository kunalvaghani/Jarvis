import asyncio
import sys
import threading
import time
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from jarvis.commands import Command, parse
from jarvis import spotify
from jarvis.brain import spotify_media_plan, validate_plan


class FakeInfo:
    def __init__(self, status="PAUSED", shuffle=False, repeat=None):
        self.playback_status = type("Status", (), {"name": status})()
        self.is_shuffle_active = shuffle
        self.auto_repeat_mode = repeat


class FakeSession:
    source_app_user_model_id = "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"

    def __init__(self):
        self.info = FakeInfo()
        self.calls = []

    def get_playback_info(self):
        return self.info

    async def try_play_async(self):
        self.calls.append("play")
        self.info.playback_status.name = "PLAYING"
        return True

    async def try_pause_async(self):
        self.calls.append("pause")
        self.info.playback_status.name = "PAUSED"
        return True

    async def try_skip_next_async(self):
        self.calls.append("next")
        return True

    async def try_skip_previous_async(self):
        self.calls.append("previous")
        return True

    def get_timeline_properties(self):
        return SimpleNamespace(position=SimpleNamespace(total_seconds=lambda: .4 if self.calls else 25))


class FakeManager:
    def __init__(self, sessions):
        self.sessions = sessions

    def get_sessions(self):
        return self.sessions


def media_modules(manager):
    control, media = ModuleType("winrt.windows.media.control"), ModuleType("winrt.windows.media")
    control.GlobalSystemMediaTransportControlsSessionManager = SimpleNamespace(
        request_async=AsyncMock(return_value=manager))
    media.MediaPlaybackAutoRepeatMode = SimpleNamespace(NONE=0, TRACK=1, LIST=2)
    return {"winrt.windows.media.control": control, "winrt.windows.media": media}


class SpotifyTests(unittest.TestCase):
    def test_voice_phrases(self):
        expected = {
            "pause Spotify": "pause",
            "resume Spotify": "play",
            "pause music": "pause",
            "next song on Spotify": "next",
            "forward music": "next",
            "previous song on Spotify": "previous",
            "back music": "previous",
            "shuffle on": "shuffle_on",
            "repeat one": "repeat_one",
            "skip 30 seconds on Spotify": "seek_30",
            "rewind 15 seconds on Spotify": "seek_-15",
            "what's playing on Spotify": "status",
        }
        for spoken, action in expected.items():
            with self.subTest(spoken=spoken):
                self.assertEqual(parse(spoken), Command("spotify_control", action, "" if "spotify" in spoken.lower() else "auto"))
        self.assertEqual(parse("open playlist Focus on Spotify"), Command("spotify_open_playlist", "Focus"))
        self.assertEqual(parse("play what makes you beautiful on Spotify"),
                         Command("play_media", "what makes you beautiful", "spotify"))
        self.assertEqual(parse("set Spotify volume to 50 percent"), Command("spotify_volume", "50"))
        self.assertEqual(parse("mute Spotify"), Command("spotify_volume", "mute"))
        self.assertEqual(parse("Spotify पर अगला गाना चलाओ"), Command("spotify_control", "next"))
        self.assertEqual(parse("Spotify par pichla gaana chalao"), Command("spotify_control", "previous"))

    def test_search_opens_native_app_without_claiming_playback(self):
        with patch.object(spotify.os, "startfile") as open_uri:
            result = spotify.search("what makes you beautiful")
        open_uri.assert_called_once_with("spotify:search:what%20makes%20you%20beautiful")
        self.assertIn("choose a result", result)

    def test_direct_plan_preserves_exact_song_and_selects_result(self):
        plan = spotify_media_plan("Play what makes you beautiful on Spotify")
        self.assertEqual([step["action"] for step in validate_plan(plan)], ["media_search", "select"])
        self.assertEqual(plan["steps"][0]["value"], "what makes you beautiful")
        playlist = spotify_media_plan("Open playlist Focus on Spotify")
        self.assertEqual(playlist["steps"][1]["value"], "playlist Focus")
        self.assertIsNone(spotify_media_plan("Play jazz on YouTube"))

    def test_chrome_only_session_is_never_controlled(self):
        chrome = FakeSession()
        chrome.source_app_user_model_id = "Chrome"
        with self.assertRaisesRegex(ValueError, "no active playback session"):
            spotify._spotify_session(FakeManager([chrome]))
        self.assertEqual(chrome.calls, [])

    def test_transport_calls_spotify_only(self):
        spotify_session = FakeSession()
        chrome = FakeSession()
        chrome.source_app_user_model_id = "Chrome"
        self.assertIs(spotify._spotify_session(FakeManager([chrome, spotify_session])), spotify_session)
        async def run():
            with patch.dict(sys.modules, media_modules(FakeManager([chrome, spotify_session]))):
                return await spotify._control("next", lambda: False)
        self.assertIn("accepted next", asyncio.run(run()))
        self.assertEqual(spotify_session.calls, ["next"])
        self.assertEqual(chrome.calls, [])

    def test_volume_changes_spotify_session_only(self):
        class Level:
            def __init__(self):
                self.value = .25
            def SetMasterVolume(self, value, _):
                self.value = value
            def GetMasterVolume(self):
                return self.value
        class AudioSession:
            def __init__(self, name):
                self.Process = type("Process", (), {"name": lambda _: name})()
                self.SimpleAudioVolume = Level()
        spotify_audio, chrome_audio = AudioSession("Spotify.exe"), AudioSession("chrome.exe")
        with patch.object(spotify, "_audio_sessions", return_value=[chrome_audio, spotify_audio]):
            self.assertEqual(spotify.volume("50"), "Spotify volume 50 percent.")
        self.assertEqual(spotify_audio.SimpleAudioVolume.value, .5)
        self.assertEqual(chrome_audio.SimpleAudioVolume.value, .25)

    def test_volume_phrases(self):
        for phrase, action in [("increase Spotify volume", "up"), ("lower volume on Spotify", "down"),
                               ("turn down the volume", "down"), ("raise volume", "up")]:
            self.assertEqual(parse(phrase), Command("spotify_volume", action, "" if "spotify" in phrase.lower() else "auto"))

    def test_transport_uses_fresh_mta_thread_even_from_sta_caller(self):
        session = FakeSession()
        caller = threading.get_ident()
        runtime = ModuleType("winrt.runtime")
        runtime.ApartmentType = SimpleNamespace(MULTI_THREADED=0)
        apartment_threads = []
        runtime.init_apartment = lambda kind: apartment_threads.append((threading.get_ident(), kind))
        runtime.uninit_apartment = Mock()
        modules = media_modules(FakeManager([session])) | {"winrt.runtime": runtime}
        with patch.dict(sys.modules, modules):
            self.assertEqual(spotify.control("play"), "Spotify playing.")
            self.assertEqual(spotify.control("pause"), "Spotify paused.")
        self.assertEqual(session.calls, ["play", "pause"])
        self.assertTrue(all(ident != caller and kind == 0 for ident, kind in apartment_threads))
        self.assertEqual(runtime.uninit_apartment.call_count, 2)

    def test_play_and_pause_are_idempotent(self):
        session = FakeSession()
        with patch.dict(sys.modules, media_modules(FakeManager([session]))):
            self.assertEqual(asyncio.run(spotify._control("pause", lambda: False)), "Spotify paused.")
            session.info.playback_status.name = "PLAYING"
            self.assertEqual(asyncio.run(spotify._control("play", lambda: False)), "Spotify playing.")
        self.assertEqual(session.calls, [])

    def test_cancel_after_metadata_read_never_sends_next(self):
        session = FakeSession()
        stopped = threading.Event()
        async def track(_):
            stopped.set()
            return ("Current", "Artist")
        with patch.dict(sys.modules, media_modules(FakeManager([session]))), patch.object(spotify, "_track", track):
            with self.assertRaisesRegex(ValueError, "cancelled before sending"):
                asyncio.run(spotify._control("next", stopped.is_set))
        self.assertEqual(session.calls, [])

    def test_cancel_during_previous_verification_does_not_send_second_press(self):
        session = FakeSession()
        stopped = threading.Event()
        async def sleep(_):
            stopped.set()
        with patch.dict(sys.modules, media_modules(FakeManager([session]))), \
                patch.object(spotify, "_track", AsyncMock(return_value=("Current", "Artist"))), \
                patch.object(spotify.asyncio, "sleep", sleep):
            with self.assertRaisesRegex(ValueError, "cancelled after sending"):
                asyncio.run(spotify._control("previous", stopped.is_set))
        self.assertEqual(session.calls, ["previous"])

    def test_previous_near_start_never_skips_twice_on_stale_metadata(self):
        session = FakeSession()
        session.get_timeline_properties = lambda: SimpleNamespace(position=SimpleNamespace(total_seconds=lambda: .4))
        with patch.dict(sys.modules, media_modules(FakeManager([session]))), \
                patch.object(spotify, "_track", AsyncMock(return_value=("Current", "Artist"))), \
                patch.object(spotify.asyncio, "sleep", AsyncMock()):
            self.assertIn("could not be verified", asyncio.run(spotify._control("previous", lambda: False)))
        self.assertEqual(session.calls, ["previous"])

    def test_timeout_fences_late_dispatch_and_never_retries(self):
        runtime = ModuleType("winrt.runtime")
        runtime.ApartmentType = SimpleNamespace(MULTI_THREADED=0)
        runtime.init_apartment = Mock()
        runtime.uninit_apartment = Mock()
        finished = threading.Event()
        sent = []
        async def slow(abort):
            # Model a blocked native observation: it returns after the caller times out.
            time.sleep(.15)
            if not abort():
                sent.append("next")
            finished.set()
        with patch.dict(sys.modules, {"winrt.runtime": runtime}):
            with self.assertRaisesRegex(ValueError, "no retry"):
                spotify._on_media_thread(slow, lambda: False, timeout=.03)
            self.assertTrue(finished.wait(1))
        self.assertEqual(sent, [])

    def test_audio_enumeration_includes_non_default_outputs(self):
        def endpoint(controls):
            enumerator = SimpleNamespace(GetCount=lambda: len(controls), GetSession=lambda index: controls[index])
            return SimpleNamespace(AudioSessionManager=SimpleNamespace(GetSessionEnumerator=lambda: enumerator))
        default = Mock(QueryInterface=Mock(return_value="browser"))
        headset = Mock(QueryInterface=Mock(return_value="spotify"))
        with patch("pycaw.pycaw.AudioUtilities.GetAllDevices", return_value=[endpoint([default]), endpoint([headset])]) as devices, \
                patch("pycaw.pycaw.AudioSession", side_effect=lambda ctl: ctl):
            self.assertEqual(spotify._audio_sessions(), ["browser", "spotify"])
        devices.assert_called_once_with(0, 1)

    def test_async_timeout_reports_uncertainty_without_retry(self):
        runtime = ModuleType("winrt.runtime")
        runtime.ApartmentType = SimpleNamespace(MULTI_THREADED=0)
        runtime.init_apartment = Mock()
        runtime.uninit_apartment = Mock()
        async def failed(abort):
            raise asyncio.TimeoutError()
        with patch.dict(sys.modules, {"winrt.runtime": runtime}):
            with self.assertRaisesRegex(ValueError, "no retry"):
                spotify._on_media_thread(failed, lambda: False)


if __name__ == "__main__":
    unittest.main()
