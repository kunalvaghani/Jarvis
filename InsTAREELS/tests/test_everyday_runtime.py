from datetime import datetime
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from jarvis.commands import Command, parse
from jarvis.everyday_runtime import EverydayRuntime
from jarvis.knowledge import Knowledge
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.quick_answers import QuickAnswers, WeatherService


class FakeWeather:
    def __init__(self):
        self.calls = []
    def current(self, city=None):
        self.calls.append(city)
        return {"city": city or "Vadodara", "source": "named city" if city else "saved city",
                "temperature": 29, "condition": "partly cloudy", "humidity": 61,
                "feels_like": 32, "utc_offset_seconds": 19800,
                "daily": {"time": ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"],
                          "temperature_2m_min": [20, 21, 22, 23, 24],
                          "temperature_2m_max": [30, 31, 32, 33, 34],
                          "precipitation_probability_max": [40, 50, 60, 70, 80],
                          "sunrise": ["2026-09-29T06:30"] * 5,
                          "sunset": ["2026-09-29T18:30"] * 5,
                          "uv_index_max": [5] * 5}}
    def saved_city(self):
        return "Vadodara"
    def air_quality(self):
        return {"city": "Vadodara", "value": 55, "source": "saved city"}


class EverydayRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.memory = ObsidianMemory(self.temp.name, {"enabled": True, "vault": "vault"})
        self.memory.start()
        (Path(self.temp.name) / "vault" / "Kunal Vaghani.md").write_text(
            "- Full name: Kunal Vaghani\n- Birth date: 20 December 2002\n"
            "- Current city: Vadodara, Gujarat, India\n- Hometown: Jamnagar, Gujarat, India\n"
            "- Career goal: Get a job at Google\n", encoding="utf-8")
        self.weather = FakeWeather()
        self.quick = QuickAnswers(self.memory, weather=self.weather,
            clock=lambda: datetime(2026, 9, 29, 9, 4))

    def test_bank_calculations_are_computed_from_inputs(self):
        cases = {"What is 25 plus 17?": "42", "What is 25 plus 18?": "43",
                 "Multiply 46 by 12": "552", "Divide 144 by 12": "12",
                 "What is 19 squared?": "361", "What is the square root of 81?": "9",
                 "What is 18 percent of 750?": "135",
                 "What is 20 percent off 899?": "719.2",
                 "Find the percentage increase from 80 to 100": "25%",
                 "How much is 500 plus 12 percent tax?": "560",
                 "Split a bill of 1600 four ways": "400",
                 "Convert 5 kilometers to miles": "3.11",
                 "Convert 100 Fahrenheit to Celsius": "37.78"}
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(parse(question).kind, "ask")
                self.assertIn(expected, self.quick.answer(question))

    def test_date_and_profile_answers_use_clock_and_obsidian(self):
        self.assertIn("Wednesday, 30 September 2026", self.quick.answer("What is tomorrow's date?"))
        self.assertIn("Thursday, 29 October 2026", self.quick.answer("What date is 30 days from now?"))
        self.assertIn("82 days", self.quick.answer("How long until my birthday?"))
        self.assertIn("23 years old", self.quick.answer("How old am I?"))
        self.assertIn("Kunal Vaghani", self.quick.answer("What is my name?"))
        self.assertIn("Jamnagar", self.quick.answer("Where am I from?"))
        self.assertIn("Monday, 12 October 2026", self.quick.answer("What day falls on October 12?"))

    def test_weather_answers_use_live_fields(self):
        self.assertIn("61%", self.quick.answer("What is the humidity?"))
        self.assertIn("50%", self.quick.answer("Weather tomorrow"))
        self.assertIn("40%", self.quick.answer("Will it rain today?"))
        self.assertIn("55", self.quick.answer("What is the air quality index?"))
        self.assertIn("18:30", self.quick.answer("What is the time of sunset?"))
        self.assertIn("32°C", self.quick.answer("Should I wear a jacket?"))

    def test_currency_uses_live_rate_and_date_and_cache(self):
        runtime = self.quick.everyday
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"rate": 84.5, "date": "2026-09-29"}
        runtime.http_get = Mock(return_value=response)
        self.assertIn("8450 INR", runtime.answer("Convert 100 USD to INR"))
        self.assertIn("1690 INR", runtime.answer("Convert 20 USD to INR"))
        self.assertEqual(runtime.http_get.call_count, 1)
        runtime.http_get = Mock(side_effect=OSError("offline"))
        self.assertIn("couldn't verify", runtime.answer("Convert 100 CAD to INR"))

    def test_named_time_uses_live_timezone_offset(self):
        self.assertEqual(parse("Time in London"), Command("ask", "Time in London"))
        self.assertIn("in london", self.quick.answer("Time in London"))
        self.assertEqual(self.weather.calls[-1], "london")
        self.assertIn("10:00 AM", self.quick.answer("Convert 10 AM IST to Toronto time"))

    def test_forecast_network_failure_does_not_fabricate_conditions(self):
        offline = Mock()
        offline.current.return_value = None
        offline.saved_city.return_value = "Vadodara"
        quick = QuickAnswers(self.memory, weather=offline)
        self.assertIn("couldn't check live weather", quick.answer("Weather tomorrow"))

    def test_computed_answer_skips_ollama_under_one_second(self):
        answers = []
        ready = threading.Event()
        def report(kind, message):
            if kind == "answer":
                answers.append(message)
                ready.set()
        knowledge = Knowledge({}, report)
        knowledge.quick = self.quick
        knowledge.client.request = Mock(side_effect=AssertionError("Ollama should not run"))
        knowledge.start()
        try:
            started = time.monotonic()
            knowledge.submit("What is 25 plus 17?")
            self.assertTrue(ready.wait(1))
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(answers, ["The result is 42."])
            knowledge.client.request.assert_not_called()
        finally:
            knowledge.close()
            knowledge.thread.join(2)


if __name__ == "__main__":
    unittest.main()
