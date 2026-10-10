import asyncio
import unittest
from unittest.mock import AsyncMock, patch

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


class FakeManager:
    def __init__(self, sessions):
        self.sessions = sessions

    def get_sessions(self):
        return self.sessions


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
            with patch("winrt.windows.media.control.GlobalSystemMediaTransportControlsSessionManager.request_async",
                       new=AsyncMock(return_value=FakeManager([chrome, spotify_session]))):
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
        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=[chrome_audio, spotify_audio]):
            self.assertEqual(spotify.volume("50"), "Spotify volume 50 percent.")
        self.assertEqual(spotify_audio.SimpleAudioVolume.value, .5)
        self.assertEqual(chrome_audio.SimpleAudioVolume.value, .25)


if __name__ == "__main__":
    unittest.main()
