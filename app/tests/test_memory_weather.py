import json
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis.commands import Command, parse
from jarvis import memory_curator as mc
from jarvis import weather_watch as ww


class CuratorTests(unittest.TestCase):
    def curator(self, chat=None):
        return mc.MemoryCurator(tempfile.mkdtemp(), {"enabled": True}, model_chat=chat)

    def test_add_update_forget_and_files(self):
        c = self.curator()
        fact, state = c.add("Kunal's sister Riya lives in Jamnagar", "person")
        self.assertEqual(state, "added")
        _, state = c.add("Kunal's sister Riya lives in Jamnagar now", "person")
        self.assertEqual((state, len(c.facts)), ("updated", 1))
        self.assertIsNone(c.add("my password is hunter2")[0])  # Secrets are never stored.
        md = (c.vault / "Jarvis Memory.md").read_text(encoding="utf-8")
        self.assertIn("## People", md)
        self.assertIn("[[Jarvis Memory]]", (c.vault / "Jarvis Brain.md").read_text(encoding="utf-8"))
        self.assertEqual(c.forget("Kunal's sister Riya Jamnagar"), ["Kunal's sister Riya lives in Jamnagar now."])
        self.assertEqual(c.facts, [])
        reloaded = mc.MemoryCurator(c.vault, {"enabled": True})
        self.assertEqual(reloaded.facts, [])

    def test_relevant_context_and_expiry(self):
        c = self.curator()
        c.add("Kunal prefers Arijit Singh songs while studying", "preference")
        c.add("Kunal had an exam on 2020-01-01", "plan", expires="2020-01-02")
        context = c.context("play something to study")
        self.assertEqual(context["facts"], ["Kunal prefers Arijit Singh songs while studying."])

    def test_learning_is_gated_and_grounded(self):
        chat = Mock(return_value={"facts": [{"text": "Kunal prefers Arijit Singh songs while studying.", "category": "preference"},
                                            {"text": "Jarvis plays music well.", "category": "fact"},
                                            {"text": "Kunal loves cricket.", "category": "preference"}]})
        c = self.curator(chat)
        c.observe("what is the capital of France", "Paris.")
        self.assertTrue(c.queue.empty())  # No personal cue: no model call at all.
        c.observe("I prefer Arijit Singh songs when I study", "Okay.")
        job = c.queue.get_nowait()
        saved = c.extract(job[1], job[2])
        # Facts about Jarvis, or with no words from the user's message, are rejected.
        self.assertEqual(saved, ["Kunal prefers Arijit Singh songs while studying."])

    def test_summary_note_and_conversation_answers(self):
        chat = Mock(return_value={"title": "Weekend plans", "summary": "Kunal planned a trip to Jamnagar.", "topics": ["trip"]})
        c = self.curator(chat)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        row = c.summarise([{"q": "plan my trip", "a": "Sure", "at": now}, {"q": "to Jamnagar", "a": "Done", "at": now}])
        self.assertEqual(row["title"], "Weekend plans")
        note = c.vault / "Jarvis Conversations" / (row["date"] + ".md")
        self.assertIn("Kunal planned a trip", note.read_text(encoding="utf-8"))
        self.assertEqual(c.conversations("what did we talk about today")[0]["title"], "Weekend plans")
        self.assertEqual(c.conversations("what did we discuss about the trip")[0]["title"], "Weekend plans")
        self.assertIn("past_conversations", c.context("what did we talk about last time"))
        self.assertIsNone(c.summarise([{"q": "one turn", "a": "", "at": now}]))  # Too short to summarise.

    def test_idle_gap_queues_a_summary(self):
        clock = [1000.]
        c = mc.MemoryCurator(tempfile.mkdtemp(), {"summary_idle_minutes": 15}, clock=lambda: clock[0])
        c.observe("open notepad", "Opened Notepad.", "task")
        clock[0] += 16 * 60
        c.observe("play music", "Playing.", "task")
        self.assertEqual(c.queue.get_nowait()[0], "summary")

    def test_commands_and_dates(self):
        self.assertEqual(parse("remember that my sister is Riya and she lives in Jamnagar"),
                         Command("memory_save", "my sister is Riya and she lives in Jamnagar"))
        self.assertEqual(parse("forget that I have an exam"), Command("memory_forget", "I have an exam"))
        self.assertEqual(parse("what do you remember about me"), Command("memory_list", ""))
        self.assertEqual(parse("what do you know about Riya"), Command("memory_list", "Riya"))
        self.assertEqual(parse("what did we talk about yesterday").kind, "memory_conversations")
        self.assertEqual(parse("do you remember what I said").kind, "ask")  # A question, not a save.
        self.assertEqual(mc.absolute_dates(mc.first_person("my exam is on Monday"), date(2026, 10, 10)),
                         "Kunal's exam is on Monday 12 October 2026")
        self.assertEqual(mc.describe(Command("play_media", "nadan parinde", "")), "Play nadan parinde")

    def test_execute_refuses_secrets(self):
        actions = SimpleNamespace(curator=self.curator())
        self.assertIn("won't store", mc.execute(actions, Command("memory_save", "my upi pin is 1234")))
        self.assertIn("I'll remember", mc.execute(actions, Command("memory_save", "I love masala chai")))
        self.assertIn("masala chai", mc.execute(actions, Command("memory_list", "chai")))


def forecast(now, **overrides):
    hours = [(now + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(48)]
    hourly = {"time": hours, "temperature_2m": [30] * 48, "precipitation": [0] * 48, "weather_code": [1] * 48,
              "wind_gusts_10m": [20] * 48, "visibility": [10000] * 48}
    for key, (index, value) in overrides.items():
        hourly[key][index] = value
    days = [(now + timedelta(days=i)).date().isoformat() for i in range(3)]
    return {"hourly": hourly, "daily": {"time": days, "precipitation_sum": [0, 0, 0], "uv_index_max": [5, 5, 5]}}


class WeatherRuleTests(unittest.TestCase):
    now = datetime(2026, 10, 10, 9, 0)

    def test_quiet_day_has_no_alerts(self):
        self.assertEqual(ww.hazards(forecast(self.now), now=self.now), [])

    def test_storm_wind_heat_fog_rain(self):
        data = forecast(self.now, weather_code=(7, 96), precipitation=(7, 12), wind_gusts_10m=(8, 75),
                        temperature_2m=(5, 43), visibility=(20, 150))
        data["daily"]["precipitation_sum"][1] = 120
        found = {h["kind"]: h for h in ww.hazards(data, now=self.now)}
        self.assertEqual(found["thunderstorm"]["level"], "severe")
        self.assertIn("around 4 PM today", found["thunderstorm"]["message"])
        self.assertEqual(found["wind"]["level"], "warning")
        self.assertEqual(found["heat"]["level"], "warning")
        self.assertIn("fog", found)
        self.assertEqual(found["heavy_rain"]["level"], "severe")
        self.assertIn("tomorrow", found["heavy_rain"]["message"])

    def test_air_quakes_disasters(self):
        air = {"hourly": {"time": [(self.now + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(5)],
                          "us_aqi": [100, 120, 175, 160, 90]}}
        quake = {"features": [{"id": "q1", "properties": {"mag": 5.1, "time": time.time() * 1000, "place": "near Bhuj"},
                               "geometry": {"coordinates": [72.6, 23.0]}},
                              {"id": "far", "properties": {"mag": 5.5, "time": time.time() * 1000, "place": "Japan"},
                               "geometry": {"coordinates": [139, 35]}}]}
        gdacs = {"items": [{"lat": "21.0", "long": "70.0", "alertlevel": "Orange", "title": "Cyclone VAYU", "guid": "TC1"}]}
        found = ww.hazards(forecast(self.now), air, quake, gdacs, location={"latitude": 22.3, "longitude": 73.2}, now=self.now)
        kinds = [h["kind"].split(":")[0] for h in found]
        self.assertEqual(sorted(kinds), ["air", "earthquake", "gdacs"])
        self.assertIn("175", next(h for h in found if h["kind"] == "air")["message"])

    def test_announce_once_and_on_escalation(self):
        reports = []
        actions = SimpleNamespace(base=tempfile.mkdtemp(), config={}, report=lambda *a: reports.append(a), memory=None)
        watch = ww.WeatherWatch(actions, {"enabled": True})
        place = {"name": "Vadodara"}
        warning = [{"id": "wind:2026-10-10", "kind": "wind", "level": "warning", "message": "Strong winds.", "starts": "x"}]
        self.assertEqual(len(watch.announce(place, warning)), 1)
        self.assertEqual(watch.announce(place, warning), [])  # Already told.
        severe = [dict(warning[0], level="severe", message="Dangerous winds.")]
        self.assertEqual(len(watch.announce(place, severe)), 1)  # Got worse: tell again.
        spoken = [a[1] for a in reports if a[0] == "spoken_reply"]
        self.assertTrue(spoken[0].startswith("Weather alert for Vadodara: Strong winds."))
        self.assertIn("not an official warning", spoken[0])
        self.assertTrue(any(a[0] == "media_card" and a[1]["service"] == "weather" for a in reports))

    def test_parse(self):
        for spoken in ("weather alerts", "is bad weather coming?", "any weather warnings today", "is a cyclone coming"):
            self.assertEqual(parse(spoken), Command("weather_alerts", "check"), spoken)


class CapabilityAndApiTests(unittest.TestCase):
    def test_capability_answers(self):
        from jarvis.capability_guide import answer
        base = tempfile.mkdtemp()
        self.assertIn("WhatsApp", answer("what can you do?", base))
        self.assertIn("82 free public data APIs", answer("which APIs are you connected to", base))
        self.assertIn("reply to my WhatsApp messages", answer("how do I use whatsapp", base))
        self.assertIsNone(answer("what is the capital of France", base))
        self.assertEqual(parse("check your APIs"), Command("api_health", ""))

    def test_fallback_not_found_and_single_retry(self):
        from jarvis.realtime_sources import Sources

        class Response:
            def __init__(self, status, payload=None):
                self.status_code, self.payload, self.headers = status, payload or {}, {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def close(self):
                pass

            def raise_for_status(self):
                if self.status_code >= 400:
                    import requests
                    raise requests.HTTPError(response=self)

            def iter_content(self, size):
                yield json.dumps(self.payload).encode()
        http = Mock()
        http.get.side_effect = [Response(503), Response(200, {"results": [{"title": "ok"}]})]
        with patch("jarvis.realtime_sources.time.sleep"):
            row = Sources(transport=http).fetch("openalex", {"query": "x"})
        self.assertEqual((row["status"], http.get.call_count), ("ok", 2))  # One retry after a 503.
        http = Mock()
        http.get.return_value = Response(404)
        self.assertEqual(Sources(transport=http).fetch("dictionary", {"id": "weather"})["status"], "not_found")
        http = Mock()
        http.get.side_effect = lambda url, **kw: Response(429) if "semanticscholar" in url else Response(200, {"results": []})
        with patch("jarvis.realtime_sources.time.sleep"):
            row = Sources(transport=http).fetch("semantic_scholar", {"query": "climate"})
        self.assertEqual((row["status"], row["fallback_for"], row["provider"]), ("ok", "semantic_scholar", "openalex"))


class IslandWeatherTests(unittest.TestCase):
    def test_weather_card_renders(self):
        from jarvis.island import MEDIA_HEIGHT, render_island
        from jarvis.media_player import card
        for phase in ("alert", "notice"):
            image = render_island(560, MEDIA_HEIGHT, "WORKING", 1.0, "", 10, False, "", 1.,
                                  card("weather", phase, "Thunderstorm expected around 4 PM", "Vadodara", "", 0, 0, "Warning"))
            self.assertEqual(image.size[1], MEDIA_HEIGHT)


if __name__ == "__main__":
    unittest.main()
