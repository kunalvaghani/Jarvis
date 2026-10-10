import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis import media_player
from jarvis.commands import Command, parse
from jarvis.media_player import (card, choose_spotify, choose_youtube, clean_query, control_card, control_text,
                                 similarity, spotify_results, youtube_search)


def row(video_id, title, channel="", duration=240):
    return {"id": video_id, "title": title, "channel": channel, "duration": duration, "thumbnail": "", "source": "test"}


class Response:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self.payload, self.text = status, payload, text

    def json(self):
        return self.payload


class MatchingTests(unittest.TestCase):
    def test_transliterated_titles_match_and_unrelated_ones_do_not(self):
        self.assertGreater(similarity("nadan parinde", "ROCKSTAR: Nadaan Parinde (Lyrical Video)"), .9)
        self.assertGreater(similarity("blinding lights", "The Weeknd - Blinding Lights (Official Video)"), .9)
        self.assertLess(similarity("nadan parinde", "Kun Faya Kun Full Song"), .4)

    def test_clean_query_drops_filler(self):
        self.assertEqual(clean_query("the song nadan parinde video"), "nadan parinde")

    def test_choose_youtube_skips_variants_and_shorts(self):
        rows = [row("aaaaaaaaaaa", "Nadaan Parinde short", duration=30),
                row("bbbbbbbbbbb", "Nadaan Parinde (Slowed + Reverb)"),
                row("ccccccccccc", "ROCKSTAR: Nadaan Parinde (Lyrical Video)", "T-Series")]
        self.assertEqual(choose_youtube("nadan parinde", rows)["id"], "ccccccccccc")
        self.assertEqual(choose_youtube("nadan parinde slowed", rows)["id"], "bbbbbbbbbbb")
        self.assertIsNone(choose_youtube("x", []))

    def test_choose_youtube_falls_back_to_top_relevance(self):
        rows = [row("aaaaaaaaaaa", "Something else"), row("bbbbbbbbbbb", "Another")]
        self.assertEqual(choose_youtube("obscure words", rows)["id"], "aaaaaaaaaaa")


class SearchTests(unittest.TestCase):
    def test_data_api_v3_path_reads_search_and_durations(self):
        session = Mock()
        session.get.side_effect = [
            Response(payload={"items": [{"id": {"videoId": "6MgsHSAcI9k"},
                                         "snippet": {"title": "Nadaan Parinde", "channelTitle": "T-Series"}}]}),
            Response(payload={"items": [{"id": "6MgsHSAcI9k", "contentDetails": {"duration": "PT6M42S"}}]})]
        rows = youtube_search("nadan parinde", session=session, key="KEY")
        self.assertEqual(rows, [{"id": "6MgsHSAcI9k", "title": "Nadaan Parinde", "channel": "T-Series", "duration": 402,
                                 "thumbnail": "https://i.ytimg.com/vi/6MgsHSAcI9k/mqdefault.jpg",
                                 "source": "youtube-data-api-v3"}])
        self.assertEqual(session.get.call_args_list[0].kwargs["params"]["type"], "video")

    def test_keyless_page_parse_and_bad_key_fallback(self):
        data = {"contents": [{"videoRenderer": {"videoId": "6MgsHSAcI9k", "title": {"runs": [{"text": "Nadaan Parinde"}]},
                                                "ownerText": {"runs": [{"text": "T-Series"}]},
                                                "lengthText": {"simpleText": "6:42"}}}]}
        page = "<script>var ytInitialData = " + json.dumps(data) + ";</script>"
        session = Mock()
        session.get.side_effect = [Response(status=403), Response(text=page)]
        rows = youtube_search("nadan parinde", session=session, key="EXPIRED")
        self.assertEqual(rows[0]["id"], "6MgsHSAcI9k")
        self.assertEqual(rows[0]["duration"], 402)
        self.assertEqual(rows[0]["source"], "youtube-search-page")

    def test_keyless_page_without_data_is_an_error(self):
        session = Mock()
        session.get.return_value = Response(text="<html></html>")
        with self.assertRaises(ValueError):
            youtube_search("x", session=session, key="")


class SpotifyParseTests(unittest.TestCase):
    controls = [
        {"name": "Top result", "role": "Text", "context": ""},
        {"name": "Nadaan Parinde", "role": "DataItem", "context": "Search results"},
        {"name": "Song • A.R. Rahman, Mohit Chauhan", "role": "DataItem", "context": "Nadaan Parinde"},
        {"name": "Play Nadaan Parinde", "role": "Button", "context": "Nadaan Parinde"},
        {"name": "Rockstar", "role": "DataItem", "context": "Search results"},
        {"name": "Album • A.R. Rahman", "role": "DataItem", "context": "Rockstar"},
        {"name": "Play", "role": "Button", "context": "Rockstar"},
        {"name": "No play button", "role": "DataItem", "context": "Search results"}]

    def test_results_and_song_choice(self):
        results = spotify_results(self.controls)
        self.assertEqual([(r["title"], r["kind"]) for r in results], [("Nadaan Parinde", "Song"), ("Rockstar", "Album")])
        self.assertEqual(results[0]["artists"], "A.R. Rahman, Mohit Chauhan")
        self.assertEqual(choose_spotify("nadan parinde", results)["title"], "Nadaan Parinde")
        self.assertIsNone(choose_spotify("completely different", results))


class PlayFallbackTests(unittest.TestCase):
    def setUp(self):
        stub = patch.object(media_player, "pause_other")  # Never touch the real Spotify session in unit tests.
        self.pause_other = stub.start()
        self.addCleanup(stub.stop)

    def actions(self, last=None):
        return SimpleNamespace(config={}, last_media=last, report=Mock())

    def test_unnamed_service_falls_back_to_the_other(self):
        actions = self.actions()
        with patch.object(media_player, "play_youtube", side_effect=ValueError("no video")), \
                patch.object(media_player, "play_spotify", return_value="Playing on Spotify.") as spotify:
            self.assertEqual(media_player.play(actions, "song", None, lambda: False), "Playing on Spotify.")
        spotify.assert_called_once()

    def test_named_service_never_switches_and_cancel_is_not_retried(self):
        actions = self.actions("spotify")
        with patch.object(media_player, "play_youtube", side_effect=ValueError("no video")), \
                patch.object(media_player, "play_spotify") as spotify:
            with self.assertRaises(ValueError):
                media_player.play(actions, "song", "youtube", lambda: False)
        spotify.assert_not_called()
        with patch.object(media_player, "play_spotify", side_effect=ValueError("cancelled")), \
                patch.object(media_player, "play_youtube") as youtube:
            with self.assertRaises(ValueError):
                media_player.play(actions, "song", None, lambda: False)
        youtube.assert_not_called()

    def test_play_youtube_reports_cards_and_remembers_service(self):
        actions = self.actions()
        browser = Mock()
        browser.request.return_value = {"verified": True, "state": {"position": 2, "duration": 402}, "ad_skipped": True}
        actions._browser = lambda: browser
        with patch.object(media_player, "youtube_search", return_value=[row("6MgsHSAcI9k", "Nadaan Parinde", "T-Series")]), \
                patch.object(media_player, "fetch_image", return_value=""):
            result = media_player.play_youtube(actions, "nadan parinde", lambda: False)
        self.assertEqual(result, "Playing Nadaan Parinde on YouTube.")
        self.assertEqual([c.args[1]["phase"] for c in actions.report.call_args_list], ["searching", "loading", "playing"])
        self.assertEqual(actions.report.call_args_list[-1].args[1]["detail"], "Ad skipped")
        self.assertEqual(actions.last_media, "youtube")
        self.pause_other.assert_called_once_with(actions, "youtube")
        browser.request.assert_called_once_with("play_video", unittest.mock.ANY, video_id="6MgsHSAcI9k", new_task=True)

    def test_unverified_youtube_playback_is_not_reported_as_playing(self):
        actions = self.actions()
        actions._browser = lambda: Mock(request=Mock(return_value={"verified": False}))
        with patch.object(media_player, "youtube_search", return_value=[row("6MgsHSAcI9k", "Nadaan Parinde")]), \
                patch.object(media_player, "fetch_image", return_value=""):
            with self.assertRaises(ValueError):
                media_player.play_youtube(actions, "nadan parinde", lambda: False)
        self.assertNotIn("playing", [c.args[1]["phase"] for c in actions.report.call_args_list])


class ControlCardTests(unittest.TestCase):
    def test_control_text(self):
        self.assertEqual([control_text(v) for v in ("pause", "seek_-10", "volume_40", "position_50", "shuffle_on")],
                         ["Paused", "Back 10s", "Volume 40%", "Jumped to 50%", "Shuffle on"])

    def test_spotify_card_uses_media_session(self):
        actions = SimpleNamespace(report=Mock(), last_media="spotify")
        now = {"title": "Nadaan Parinde", "artist": "A.R. Rahman", "status": "paused", "position": 10, "duration": 380}
        with patch.object(media_player, "spotify_now", return_value=now), patch.object(media_player.time, "sleep"):
            control_card(actions, Command("spotify_control", "pause"))
        shown = actions.report.call_args.args[1]
        self.assertEqual((shown["service"], shown["phase"], shown["title"], shown["detail"]),
                         ("spotify", "paused", "Nadaan Parinde", "Paused"))

    def test_youtube_card_reads_owned_player_and_keeps_artwork(self):
        browser = Mock(last_url="https://www.youtube.com/watch?v=6MgsHSAcI9k")
        browser.request.return_value = {"state": {"title": "Nadaan Parinde", "paused": False, "position": 5, "duration": 402}}
        actions = SimpleNamespace(report=Mock(), last_media="youtube", browser_automation=browser,
                                  last_youtube={"title": "Nadaan Parinde", "channel": "T-Series", "image": "abc"})
        control_card(actions, Command("media_control", "volume_up", "youtube"))
        shown = actions.report.call_args.args[1]
        self.assertEqual((shown["phase"], shown["subtitle"], shown["image"], shown["detail"]),
                         ("playing", "T-Series", "abc", "Volume up"))

    def test_card_failure_is_silent(self):
        actions = SimpleNamespace(report=Mock(side_effect=RuntimeError("closed")), last_media="youtube")
        control_card(actions, Command("media_control", "pause", "youtube"))  # Must not raise.


class ResolveTests(unittest.TestCase):
    def resolve(self, command, spotify=None, youtube=None, last=None):
        actions = SimpleNamespace(last_media=last)
        with patch.object(media_player, "spotify_window", return_value=1 if spotify else None),                 patch.object(media_player, "spotify_now", return_value=spotify),                 patch.object(media_player, "youtube_state", return_value=youtube or {}):
            return media_player.resolve(actions, command)

    def test_follows_the_playing_service(self):
        playing_youtube = {"paused": False}
        self.assertEqual(self.resolve(Command("spotify_volume", "40", "auto"), youtube=playing_youtube),
                         Command("media_control", "volume_40", "youtube"))
        self.assertEqual(self.resolve(Command("spotify_control", "seek_-10", "auto"), youtube=playing_youtube),
                         Command("media_control", "seek_-10", "youtube"))
        self.assertEqual(self.resolve(Command("click_control", "pause", "click"), spotify={"status": "playing"}),
                         Command("spotify_control", "pause", ""))
        self.assertEqual(self.resolve(Command("spotify_control", "next", "auto"), spotify={"status": "paused"}),
                         Command("spotify_control", "next", ""))

    def test_both_playing_prefers_the_last_started(self):
        both = dict(spotify={"status": "playing"}, youtube={"paused": False})
        self.assertEqual(self.resolve(Command("click_control", "pause", "click"), last="youtube", **both).extra, "youtube")
        self.assertEqual(self.resolve(Command("click_control", "pause", "click"), last="spotify", **both).kind,
                         "spotify_control")

    def test_spotify_only_actions_stay_on_spotify(self):
        self.assertEqual(self.resolve(Command("spotify_control", "shuffle_on", "auto"), youtube={"paused": False}),
                         Command("spotify_control", "shuffle_on", ""))

    def test_unscoped_phrases_are_marked_auto(self):
        self.assertEqual(parse("volume up"), Command("spotify_volume", "up", "auto"))
        self.assertEqual(parse("spotify volume up"), Command("spotify_volume", "up", ""))
        self.assertEqual(parse("go back 10 seconds"), Command("spotify_control", "seek_-10", "auto"))
        self.assertEqual(parse("skip this song"), Command("spotify_control", "next", "auto"))
        self.assertEqual(parse("turn on captions"), Command("media_control", "captions_on", "youtube"))

    def test_player_message_is_speakable(self):
        from jarvis.browser_worker import player_message
        state = {"title": "Song", "paused": False, "position": 65, "duration": 402, "volume": .4, "speed": 1}
        self.assertEqual(player_message("status", state), "Playing: Song, at 1:05 of 6:42 on YouTube.")
        self.assertEqual(player_message("pause", state), "Paused on YouTube.")
        self.assertEqual(player_message("volume_40", state), "YouTube volume 40%, speed 1x.")


class SpotifyTrackTests(unittest.TestCase):
    def test_previous_skips_past_the_restart(self):
        import asyncio
        from jarvis import spotify

        class Media:
            def __init__(self, title):
                self.title, self.artist = title, "Artist"

        class Session:
            source_app_user_model_id = "Spotify.exe"
            def __init__(self):
                self.track, self.calls = "Current", []
            def get_playback_info(self):
                return SimpleNamespace(playback_status=SimpleNamespace(name="PLAYING"))
            def get_timeline_properties(self):
                return SimpleNamespace(position=SimpleNamespace(total_seconds=lambda: 0.4))
            async def try_get_media_properties_async(self):
                return Media(self.track)
            try_play_async = try_pause_async = try_skip_next_async = None
            async def try_skip_previous_async(self):
                self.calls.append("previous")
                if len(self.calls) == 2:
                    self.track = "Earlier"  # First press restarted the song; the second reached the earlier track.
                return True

        session = Session()
        manager = SimpleNamespace(get_sessions=lambda: [session])

        import sys
        from types import ModuleType
        control_module, media_module = ModuleType("winrt.windows.media.control"), ModuleType("winrt.windows.media")
        control_module.GlobalSystemMediaTransportControlsSessionManager = SimpleNamespace(
            request_async=unittest.mock.AsyncMock(return_value=manager))
        media_module.MediaPlaybackAutoRepeatMode = SimpleNamespace(NONE=0, TRACK=1, LIST=2)

        async def run():
            # Fake WinRT modules: loading the real WinRT DLLs here breaks onnxruntime's later DLL init in this process.
            with patch.dict(sys.modules, {"winrt.windows.media.control": control_module, "winrt.windows.media": media_module}),                     patch.object(spotify, "_spotify_session", return_value=session):
                return await spotify._control("previous", lambda: False)
        self.assertEqual(asyncio.run(run()), "Now playing Earlier by Artist.")
        self.assertEqual(session.calls, ["previous", "previous"])


class RoutingTests(unittest.TestCase):
    def test_play_phrases(self):
        self.assertEqual(parse("open youtube and play nadan parinde"), Command("play_media", "nadan parinde", "youtube"))
        self.assertEqual(parse("go to Spotify then play blinding lights"),
                         Command("play_media", "blinding lights", "spotify"))
        self.assertEqual(parse("play nadan parinde on spotify").kind, "play_media")
        self.assertEqual(parse("play nadan parinde"), Command("play_media", "nadan parinde", ""))
        self.assertEqual(parse("and play nadan parinde"), Command("play_media", "nadan parinde", ""))
        self.assertEqual(parse("play it again"), Command("media_control", "restart", ""))

    def test_bare_player_words_are_not_searches(self):
        for spoken in ("play it", "play that", "play music"):
            self.assertNotEqual(parse(spoken).kind, "play_media", spoken)


class IslandCardTests(unittest.TestCase):
    def test_every_phase_renders(self):
        from jarvis.island import MEDIA_HEIGHT, media_progress, render_island
        for service in ("youtube", "spotify"):
            for phase in ("searching", "loading", "playing", "paused", "error", "control"):
                image = render_island(560, MEDIA_HEIGHT, "WORKING", 1.2, "", 20, False, "", 1.,
                                      card(service, phase, "Title", "Artist", "", 30, 200, "Detail"))
                self.assertEqual(image.size[1], MEDIA_HEIGHT)
        playing = card("youtube", "playing", position=10, duration=100)
        self.assertAlmostEqual(media_progress(playing, playing["at"] + 5)[0], 15, delta=.01)
        paused = card("youtube", "paused", position=10, duration=100)
        self.assertEqual(media_progress(paused, time.time() + 50)[0], 10)


if __name__ == "__main__":
    unittest.main()
