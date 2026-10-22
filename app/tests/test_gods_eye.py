import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis import gods_eye as ge
from jarvis.commands import Command, parse

HERE = {"latitude": 22.3, "longitude": 73.2, "name": "Vadodara"}


def flight(icao, callsign, lat, lon, alt, squawk="1000", ground=False):
    return [icao, callsign, "India", time.time(), time.time(), lon, lat, alt, ground, 80, 90, 0, None, alt, squawk, False, 0]


class ParseTests(unittest.TestCase):
    def spec(self, spoken):
        command = parse(spoken)
        self.assertEqual(command.kind, "gods_eye_show", spoken)
        return json.loads(command.value)

    def test_places_layers_styles_routes(self):
        self.assertEqual(self.spec("show me the Eiffel Tower")["place"], "eiffel tower")
        self.assertEqual(self.spec("take me to Tokyo")["place"], "tokyo")
        flights = self.spec("show flights near me")
        self.assertEqual((flights["place"], flights["layers"]), ("me", ["flights", "local-adsb"]))
        military = self.spec("show military over the Persian Gulf")
        self.assertEqual((military["place"], military["layers"]), ("the persian gulf", ["military", "military-installations"]))
        weather = self.spec("what's the weather doing")
        self.assertEqual((weather["place"], weather["layers"], weather["lock"]), ("me", ["weather-radar", "weather-lightning"], True))
        self.assertEqual(self.spec("what's the traffic like in London")["layers"], ["traffic"])
        self.assertTrue(self.spec("show cameras in London")["cctv"])
        self.assertEqual(self.spec("switch to thermal view")["style"], ["style", "thermal"])
        self.assertEqual(self.spec("switch to cyber radar")["style"], ["hud", "cyber"])
        self.assertEqual(self.spec("show me the route from Vadodara to Ahmedabad")["route"], ["vadodara", "ahmedabad"])

    def test_explain_and_admin(self):
        for spoken in ("why is it so loud outside", "why am I hearing sirens", "what planes are above me",
                       "any helicopters overhead", "what's happening around me"):
            self.assertEqual(parse(spoken).kind, "gods_eye_explain", spoken)
        self.assertEqual(parse("update gods eye").kind, "gods_eye_update")
        self.assertEqual(parse("god's eye status").kind, "gods_eye_status")

    def test_other_commands_are_untouched(self):
        self.assertEqual(parse("open notepad").kind, "open")
        self.assertEqual(parse("show me the queue").kind, "queue_status")
        self.assertEqual(parse("play nadan parinde").kind, "play_media")
        self.assertNotEqual(parse("show me my emails").kind, "gods_eye_show")
        self.assertEqual(parse("open god's eye").kind, "gods_eye_view")


class Feed(ge.GodsEye):
    def __init__(self, responses, clock=time.time):
        actions = SimpleNamespace(base=tempfile.mkdtemp(), config={}, report=Mock(), memory=None, realtime=None)
        super().__init__(actions, {"radius_km": 40}, clock=clock)
        self.responses = responses
        self.http = Mock()
        self.http.get.side_effect = lambda *a, **k: Mock(json=lambda: {"features": []})

    def here(self):
        return HERE

    def api(self, path, params=None, timeout=20):
        return self.responses.get(path)


class FeedTests(unittest.TestCase):
    def feed(self):
        # Real-time milliseconds can round-trip one float ULP into the future.
        # Use one explicit fixture clock; keep production's strict future guard.
        stamp = 1700000000.0
        states = [flight("a1", "IGO527 ", 22.45, 73.25, 11000), flight("b2", "LOW1 ", 22.32, 73.21, 600),
                  flight("c3", "EMG77 ", 22.5, 73.3, 2000, "7700"), flight("d4", "FAR ", 28.6, 77.2, 9000)]
        for state in states:
            state[3] = state[4] = stamp
        return Feed({
            "/api/flights": {"time": stamp, "states": states},
            "/api/military": {"now":int(stamp*1000),"total": 100, "ac": [{"seen_pos":0,"hex": "m1", "flight": "IAF01 ", "t": "C130", "lat": 22.35, "lon": 73.22,
                                                    "alt_baro": 2500, "squawk": "4000", "emergency": "none"}]},
            "/api/cyclones": {"storms": [{"name": "Vayu", "position": {"latitude": 21.0, "longitude": 70.5}, "forecastPoints": []}]},
            "/api/fire-perimeters": {"rows": []},
            "/api/weather-effects": {"weather": {"weatherCode": 95, "precipitationMm": 4, "windKph": 30}},
            "/api/local-receivers/aircraft": {"configured": False},
            "/api/tomtom/status": {"hasKey": False},
        }, clock=lambda: stamp)

    def test_future_aircraft_timestamps_still_rejected(self):
        feed = self.feed()
        future = feed.clock() + 1
        feed.responses['/api/flights']['time'] = future
        for state in feed.responses['/api/flights']['states']:
            state[3] = state[4] = future
        feed.responses['/api/military']['now'] = int(future*1000)
        snapshot = feed.poll()
        self.assertEqual(snapshot['flights']['count'], 0)
        self.assertEqual(snapshot['military']['count_near'], 0)
        stamp = 1792639900.00029
        self.assertGreater(stamp*1000/1000, stamp)
        self.assertFalse(ge.recent(stamp*1000/1000, stamp))

    def test_poll_alerts_and_answers(self):
        feed = self.feed()
        snapshot = feed.poll()
        self.assertEqual(snapshot["flights"]["count"], 3)  # Delhi is outside 40 km.
        self.assertEqual([f["callsign"] for f in snapshot["flights"]["low"]], ["LOW1"])
        self.assertEqual(snapshot["flights"]["emergencies"][0]["squawk"], "7700")
        self.assertEqual(snapshot["military"]["count_near"], 1)
        self.assertEqual(snapshot["cyclones"]["near"][0]["name"], "Vayu")
        kinds = [a[0].split(":")[0] for a in feed.alerts()]
        self.assertEqual(kinds, ["squawk", "mil-low", "cyclone"])
        fresh = feed.alert()
        self.assertEqual(len(fresh), 3)
        self.assertEqual(feed.alert(), [])  # Each alert is spoken once.
        spoken = [c.args[1] for c in feed.actions.report.call_args_list if c.args[0] == "spoken_reply"]
        self.assertIn("squawking 7700 (general emergency)", spoken[0])
        answer = feed.explain("why is it so loud outside")
        self.assertIn("LOW1", answer)
        self.assertIn("military aircraft IAF01", answer)
        self.assertIn("thunderstorm", answer)
        self.assertEqual(feed.summary()["aircraft_within_40km"], 3)

    def test_quiet_area_and_sirens(self):
        feed = Feed({"/api/flights": {"states": []}, "/api/military": {"ac": []}, "/api/tomtom/status": {"hasKey": False}})
        feed.poll()
        self.assertIn("unavailable", feed.explain("why is it so loud outside"))
        self.assertIn("live traffic isn't connected", feed.explain("why am I hearing sirens"))


class ShowTests(unittest.TestCase):
    def eye(self):
        browser = Mock()
        browser.request.return_value = {"results": [
            {"name": "fly_to_location", "ok": True, "result": {"ok": True}},
            {"name": "set_layer_visibility", "ok": True, "result": {"ok": True, "label": "Military Flights", "enabled": True}},
            {"name": "camera_check", "ok": True, "result": {}}]}
        actions = SimpleNamespace(base=tempfile.mkdtemp(), config={}, report=Mock(), _browser=lambda: browser, realtime=None)
        eye = ge.GodsEye(actions, {})
        eye.ensure_server = Mock(return_value=ge.BASE)
        eye.geocode = Mock(return_value={"latitude": 27.2, "longitude": 51.2, "name": "Persian Gulf", "span_km": 1000})
        return eye, browser

    def test_military_region_builds_actions_and_replaces_old_layers(self):
        eye, browser = self.eye()
        eye.enabled_layers = {"cctv"}
        text = eye.show({"place": "the persian gulf", "layers": ["military", "military-installations"], "kind": "military"})
        sent = browser.request.call_args.kwargs
        names = [(a["name"], a["args"].get("layerId"), a["args"].get("enabled")) for a in sent["actions"]]
        self.assertEqual(names[0][0], "fly_to_location")
        self.assertIn(("set_layer_visibility", "cctv", False), names)  # The previous request's layer is turned off.
        self.assertIn(("set_layer_visibility", "military", True), names)
        self.assertEqual(sent["view"]["altitude"], 450000)
        self.assertIn("Persian Gulf", text)
        self.assertIn("Military Flights", text)

    def test_style_only_and_route(self):
        eye, browser = self.eye()
        eye.show({"place": "", "style": ["hud", "cyber"]})
        self.assertEqual(browser.request.call_args.kwargs["actions"], [{"name": "set_hud", "args": {"visible": "on", "layout": "cyber"}}])
        eye.geocode = Mock(side_effect=[{"latitude": 22.3, "longitude": 73.2, "name": "A"}, {"latitude": 23.0, "longitude": 72.6, "name": "B"}])
        text = eye.show({"place": "", "route": ["vadodara", "ahmedabad"]})
        names = [a["name"] for a in browser.request.call_args.kwargs["actions"]]
        self.assertEqual(names, ["fly_to_location", "annotate_map", "fly_route"])
        self.assertIn("driving route", text)


class UpdateTests(unittest.TestCase):
    def test_swap_keeps_local_state_and_reinstalls_on_lock_change(self):
        import io
        import zipfile
        from jarvis import gods_eye_update as gu
        root = Path(tempfile.mkdtemp()) / "gods-eye-view-main"
        root.mkdir()
        (root / "package-lock.json").write_text("old")
        (root / "old.js").write_text("old")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "keep.txt").write_text("deps")
        (root / ".env").write_text("SECRET=1")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("gods-eye-view-abc/package-lock.json", "new")
            archive.writestr("gods-eye-view-abc/src/main.js", "new")
        run = Mock(return_value=Mock(returncode=0))
        with patch.object(gu, "latest", return_value=("abc123", "2026-10-10T00:00:00Z", "msg")), \
                patch.object(gu.requests, "get", return_value=Mock(content=buffer.getvalue())):
            result = gu.update(root, run=run)
        self.assertTrue(result["updated"] and result["dependencies_reinstalled"])
        self.assertEqual((root / "src" / "main.js").read_text(), "new")
        self.assertFalse((root / "old.js").exists())
        self.assertEqual((root / ".env").read_text(), "SECRET=1")
        self.assertTrue((root / "node_modules" / "keep.txt").exists())
        self.assertTrue((Path(result["backup"]) / "old.js").exists())
        with patch.object(gu, "latest", return_value=("abc123", "2026-10-10T00:00:00Z", "msg")):
            self.assertFalse(gu.update(root)["updated"])  # Same commit: nothing changes.


class IslandTests(unittest.TestCase):
    def test_card(self):
        from jarvis.island import MEDIA_HEIGHT, render_island
        from jarvis.media_player import card
        for phase in ("opening", "showing", "alert"):
            image = render_island(560, MEDIA_HEIGHT, "WORKING", 1., "", 10, False, "", 1.,
                                  card("godseye", phase, "Persian Gulf", "Military Flights", "", 0, 0, "On screen"))
            self.assertEqual(image.size[1], MEDIA_HEIGHT)


if __name__ == "__main__":
    unittest.main()
