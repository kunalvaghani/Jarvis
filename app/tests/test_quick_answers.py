from datetime import datetime
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from jarvis.commands import Command, parse
from jarvis.knowledge import Knowledge
from jarvis.knowledge_worker import answer
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.quick_answers import QuickAnswers, WeatherService


class QuickAnswerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.memory = ObsidianMemory(self.temp.name, {"enabled": True, "vault": "vault"})
        self.memory.start()
        (Path(self.temp.name) / "vault" / "Kunal Vaghani.md").write_text(
            "# Kunal Vaghani\n\n- Full name: Kunal Vaghani\n- Current city: Vadodara, Gujarat, India\n",
            encoding="utf-8")

    def test_common_spoken_phrases_route_to_questions(self):
        for phrase in ("hello", "how are you", "thanks", "time", "date", "weather",
                       "current weather", "temperature", "weather today", "weather in Surat"):
            with self.subTest(phrase=phrase):
                self.assertEqual(parse(phrase), Command("ask", phrase))

    def test_profile_greeting_time_and_date_are_direct(self):
        weather = Mock()
        weather.current.return_value = {"city": "Vadodara", "temperature": 29,
            "condition": "clear", "source": "saved city"}
        quick = QuickAnswers(self.memory, weather=weather,
            clock=lambda: datetime(2026, 9, 29, 9, 4))
        self.assertEqual(quick.answer("hello"), "Good morning, Kunal sir. I'm ready.")
        self.assertEqual(quick.answer("what time is it?"), "The local time is 9:04 AM.")
        self.assertEqual(quick.answer("what is the date?"), "Today is Tuesday, 29 September 2026.")
        self.assertIn("Kunal sir. Current weather in Vadodara", quick.startup_greeting())
        self.assertIn("The local PC time is 9:04 AM", quick.startup_greeting())
        self.assertIsNone(quick.answer("Why does weather change?"))

    def test_weather_uses_ip_location_and_reuses_result(self):
        calls = []
        def get(url, params=None, timeout=None):
            calls.append(url)
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = (
                {"city": "Surat", "latitude": 21.17, "longitude": 72.83}
                if "ipapi" in url else
                {"current": {"temperature_2m": 31.4, "weather_code": 2, "time": "2026-09-29T09:00"}})
            return response
        weather = WeatherService(self.memory, http_get=get)
        quick = QuickAnswers(self.memory, weather=weather)
        self.assertIn("near Surat (approximate IP location): 31°C", quick.answer("weather"))
        self.assertIn("near Surat", quick.answer("weather"))
        self.assertEqual(len(calls), 2)

    def test_weather_falls_back_to_saved_city_and_reports_failure(self):
        def get(url, params=None, timeout=None):
            if "ipapi" in url:
                raise ValueError("offline")
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = (
                {"results": [{"name": "Vadodara", "latitude": 22.3, "longitude": 73.2}]}
                if "geocoding" in url else
                {"current": {"temperature_2m": 27, "weather_code": 63}})
            return response
        quick = QuickAnswers(self.memory, weather=WeatherService(self.memory, http_get=get))
        self.assertIn("in Vadodara (saved city): 27°C and rainy", quick.answer("weather"))

        failed = Mock(side_effect=ValueError("offline"))
        quick = QuickAnswers(self.memory, weather=WeatherService(self.memory, http_get=failed))
        self.assertIn("couldn't check live weather for Vadodara", quick.answer("weather"))
        first_calls = failed.call_count
        quick.answer("weather")
        self.assertEqual(failed.call_count, first_calls)

    def test_forecast_and_air_quality_parameters_are_live_queries(self):
        calls = []
        def get(url, params=None, timeout=None):
            calls.append((url, params))
            response = Mock()
            response.raise_for_status.return_value = None
            if "geocoding" in url:
                response.json.return_value = {"results": [{"name": "Vadodara", "latitude": 22.3, "longitude": 73.2}]}
            elif "air-quality" in url:
                response.json.return_value = {"current": {"us_aqi": 55}}
            else:
                response.json.return_value = {"current": {"temperature_2m": 29, "weather_code": 2},
                    "daily": {"time": ["2026-09-29"], "precipitation_probability_max": [40]},
                    "utc_offset_seconds": 19800}
            return response
        weather = WeatherService(self.memory, {"ip_location": False}, get)
        self.assertEqual(weather.current()["daily"]["precipitation_probability_max"], [40])
        self.assertEqual(weather.air_quality()["value"], 55)
        self.assertTrue(any("daily" in (params or {}) for _, params in calls))
        self.assertTrue(any((params or {}).get("current") == "us_aqi" for _, params in calls))

    def test_knowledge_fast_path_skips_model(self):
        answers = []
        ready = threading.Event()
        def report(kind, message):
            if kind == "answer":
                answers.append(message)
                ready.set()
        knowledge = Knowledge({}, report)
        knowledge.quick = QuickAnswers(self.memory, weather=Mock(),
            clock=lambda: datetime(2026, 9, 29, 9, 4))
        knowledge.client.request = Mock(side_effect=AssertionError("Model path used"))
        knowledge.start()
        try:
            started = time.monotonic()
            knowledge.submit("hello")
            self.assertTrue(ready.wait(1))
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(answers, ["Good morning, Kunal sir. I'm ready."])
            knowledge.client.request.assert_not_called()
        finally:
            knowledge.close()
            knowledge.thread.join(2)

    def test_local_model_receives_profile_as_reference(self):
        chat = Mock(return_value='{"answer":"Hello Kunal.","needs_web":false}')
        answer({"question": "Tell me about my career goal",
                "user_profile": self.memory.profile_text()}, chat_fn=chat)
        system = chat.call_args.args[2][0]["content"]
        self.assertIn("Kunal Vaghani", system)
        self.assertIn("Use it only when relevant", system)


if __name__ == "__main__":
    unittest.main()
