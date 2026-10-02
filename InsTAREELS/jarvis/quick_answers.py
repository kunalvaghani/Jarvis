"""Bounded direct replies for greetings, local time, and current weather."""
from datetime import datetime, timedelta, timezone
import re
import threading
import time

import requests

from .everyday_runtime import EverydayRuntime


HELLO = re.compile(r"(?i)^(?:hi|hello|hey|good morning|good afternoon|good evening|namaste|नमस्ते)[!. ]*$")
WELLBEING = re.compile(r"(?i)^(?:how are you|how are you doing|how's it going|कैसे हो)[?.! ]*$")
THANKS = re.compile(r"(?i)^(?:thanks|thank you|धन्यवाद)[!. ]*$")
TIME = re.compile(r"(?i)^(?:(?:what(?:'s| is) )?(?:the )?(?:local |current )?time(?: now)?|time|what time is it|समय क्या है|कितने बजे हैं)[?.! ]*$")
DATE = re.compile(r"(?i)^(?:(?:what(?:'s| is) )?(?:today'?s |the |current )?date|what day is it|today'?s date|तारीख क्या है)[?.! ]*$")
WEATHER = re.compile(r"(?i)^(?:(?:what(?:'s| is) )?(?:the )?(?:current |today'?s )?(?:weather|temperature)(?: like)?(?: today)?(?: (?:in|for) [a-z][a-z ,]{1,60})?|(?:weather|temperature)(?: today)?(?: (?:in|for) [a-z][a-z ,]{1,60})?|mausam|मौसम(?: कैसा है)?)$", re.I)
WEATHER_CITY = re.compile(r"(?i)\b(?:weather|temperature)(?: like)?(?: today)? (?:in|for) ([a-z][a-z ,]{1,60})[?.! ]*$")
CONDITIONS = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy",
              45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzly", 55: "drizzly",
              61: "light rain", 63: "rainy", 65: "heavy rain", 71: "light snow",
              73: "snowy", 75: "heavy snow", 80: "rain showers", 81: "rain showers",
              82: "heavy rain showers", 95: "thunderstorms"}


class WeatherService:
    def __init__(self, memory=None, options=None, http_get=None):
        self.memory = memory
        self.options = options or {}
        session = requests.Session()
        self.http_get = http_get or session.get
        self.lock = threading.Lock()
        self.cached = None
        self.cached_at = 0.0
        self.failed_at = 0.0
        self.named_cache = {}

    def saved_city(self):
        profile = self.memory.profile_text() if self.memory else ""
        match = re.search(r"(?im)^- Current city:\s*([^,\n]+)", profile)
        return match[1].strip() if match else self.options.get("fallback_city", "")

    def _get(self, url, params=None, timeout=(.6, 1.0)):
        response = self.http_get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _location(self, named_city=None):
        if not named_city and self.options.get("ip_location", True):
            try:
                data = self._get("https://ipapi.co/json/", timeout=(.6, .8))
                city, lat, lon = data.get("city"), data.get("latitude"), data.get("longitude")
                if isinstance(city, str) and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    return city[:60], lat, lon, "approximate IP location"
            except (requests.RequestException, ValueError, TypeError, KeyError):
                pass
        city = named_city or self.saved_city()
        if not city:
            raise ValueError("No current city could be determined.")
        data = self._get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "en"}, timeout=(.6, .8))
        rows = data.get("results") or []
        if not rows:
            raise ValueError("The weather location could not be found.")
        row = rows[0]
        return row["name"], row["latitude"], row["longitude"], "named city" if named_city else "saved city"

    def current(self, named_city=None):
        with self.lock:
            if not named_city and self.cached and time.monotonic() - self.cached_at < 600:
                return self.cached
            if named_city:
                cached = self.named_cache.get(named_city.casefold())
                if cached and time.monotonic() - cached[0] < 600:
                    return cached[1]
            if not named_city and self.failed_at and time.monotonic() - self.failed_at < 60:
                return None
            try:
                city, lat, lon, source = self._location(named_city)
                data = self._get("https://api.open-meteo.com/v1/forecast",
                    params={"latitude": lat, "longitude": lon,
                            "current": "temperature_2m,weather_code,relative_humidity_2m,apparent_temperature",
                            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset,uv_index_max",
                            "timezone": "auto"},
                    timeout=(.6, 1.0))
                current = data["current"]
                temperature = current["temperature_2m"]
                if not isinstance(temperature, (int, float)):
                    raise ValueError("Weather service returned no temperature.")
                result = {"city": city, "temperature": round(temperature),
                          "condition": CONDITIONS.get(current.get("weather_code"), "conditions unavailable"),
                          "source": source, "observed_at": current.get("time", ""),
                          "humidity": current.get("relative_humidity_2m"),
                          "feels_like": current.get("apparent_temperature"),
                          "daily": data.get("daily") or {},
                          "utc_offset_seconds": data.get("utc_offset_seconds")}
                if not named_city:
                    self.cached, self.cached_at = result, time.monotonic()
                    self.failed_at = 0.0
                else:
                    self.named_cache[named_city.casefold()] = (time.monotonic(), result)
                return result
            except (requests.RequestException, ValueError, TypeError, KeyError):
                if not named_city:
                    self.failed_at = time.monotonic()
                return None

    def air_quality(self, named_city=None):
        try:
            city, lat, lon, source = self._location(named_city)
            data = self._get("https://air-quality-api.open-meteo.com/v1/air-quality",
                params={"latitude": lat, "longitude": lon, "current": "us_aqi", "timezone": "auto"},
                timeout=(.6, 1.0))
            value = (data.get("current") or {}).get("us_aqi")
            return {"city": city, "value": round(value), "source": source} if isinstance(value, (int, float)) else None
        except (requests.RequestException, ValueError, TypeError, KeyError):
            return None


class QuickAnswers:
    def __init__(self, memory=None, weather_options=None, weather=None, clock=None, settings=None):
        self.memory = memory
        self.weather = weather or WeatherService(memory, weather_options)
        self.clock = clock or datetime.now
        self.everyday = EverydayRuntime(memory, self.weather, self.clock, settings=settings)

    def name(self):
        profile = self.memory.profile_text() if self.memory else ""
        match = re.search(r"(?im)^- Full name:\s*([^\n]+)", profile)
        return match[1].split()[0] if match else ""

    def salutation(self, hour=None):
        hour = self.clock().hour if hour is None else hour
        return "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

    def time_text(self):
        return self.clock().strftime("%I:%M %p").lstrip("0")

    def weather_text(self, named_city=None):
        current = self.weather.current(named_city)
        return self._weather_text(current, named_city)

    def _weather_text(self, current, named_city=None):
        if current is None:
            city = named_city or self.weather.saved_city()
            return f"I couldn't check live weather for {city}." if city else "I couldn't check live weather or your location."
        location = (f"near {current['city']} (approximate IP location)" if current["source"] == "approximate IP location"
                    else f"in {current['city']} ({current['source']})")
        return f"Current weather {location}: {current['temperature']}°C and {current['condition']}."

    def startup_greeting(self):
        name = self.name()
        address = f", {name} sir" if name else ""
        current = self.weather.current()
        weather = self._weather_text(current)
        offset = current.get("utc_offset_seconds") if current else None
        if isinstance(offset, (int, float)):
            local = datetime.now(timezone.utc) + timedelta(seconds=offset)
            time_label = f"The time near {current['city']} is {local.strftime('%I:%M %p').lstrip('0')}"
            greeting = self.salutation(local.hour)
        else:
            time_label = f"The local PC time is {self.time_text()}"
            greeting = self.salutation()
        return f"{greeting}{address}. {weather} {time_label}."

    def answer(self, question):
        question = question.strip().replace("’", "'")
        if self.memory is not None and hasattr(self.memory, "catalogue_answer"):
            catalogue = self.memory.catalogue_answer(question)
            if isinstance(catalogue, str) and catalogue:
                return catalogue
        if HELLO.fullmatch(question):
            name = self.name()
            return f"{self.salutation()}, {name} sir. I'm ready." if name else f"{self.salutation()}. I'm ready."
        if WELLBEING.fullmatch(question):
            name = self.name()
            return f"I'm doing well, {name} sir. How can I help?" if name else "I'm doing well. How can I help?"
        if THANKS.fullmatch(question):
            return "You're welcome."
        if TIME.fullmatch(question):
            return f"The local time is {self.time_text()}."
        if DATE.fullmatch(question):
            return f"Today is {self.clock().strftime('%A, %d %B %Y')}."
        if WEATHER.fullmatch(question.rstrip("?.! ")):
            match = WEATHER_CITY.search(question)
            return self.weather_text(match[1].strip() if match else None)
        weather = self._weather_detail(question)
        return weather if weather is not None else self.everyday.answer(question)

    def _weather_detail(self, question):
        text = question.strip().casefold().rstrip("?.! ")
        if re.fullmatch(r"(?:what is |what's )?(?:the )?(?:air quality index|aqi)(?: (?:near me|outside))?", text):
            result = self.weather.air_quality()
            return (f"The current US AQI estimate near {result['city']} is {result['value']} (Open-Meteo/CAMS, {result['source']})."
                    if result else "I couldn't verify the current air quality index.")
        if text in {"are there weather alerts nearby", "any weather alerts nearby"}:
            return "I don't have a verified local weather alert feed connected."
        detail = None
        if re.fullmatch(r"(?:(?:what|when) is |what's )?(?:the )?(?:temperature outside|humidity|uv index|sunrise today|sunset|time of sunset|time of sunrise)", text):
            detail = "metric"
        elif re.fullmatch(r"(?:how is the weather|weather tomorrow|will it rain today|should i carry an umbrella|is it going to rain this evening|what is the forecast for the weekend|does it feel hot outside|should i wear a jacket|what should i wear for today's weather|is it cold enough for a hoodie)", text):
            detail = "advice"
        if detail is None:
            return None
        result = self.weather.current()
        if not result:
            return "I couldn't check live weather for " + (self.weather.saved_city() or "your location") + "."
        city = result["city"]
        daily = result.get("daily") or {}
        dates = daily.get("time") or []
        index = 1 if text == "weather tomorrow" else 0
        if text == "what is the forecast for the weekend":
            for i, day in enumerate(dates):
                try:
                    if datetime.fromisoformat(day).weekday() == 5:
                        index = i
                        break
                except ValueError:
                    pass
        def day_value(key):
            values = daily.get(key) or []
            return values[index] if index < len(values) else None
        if "humidity" in text:
            value = result.get("humidity")
            return f"Current humidity near {city} is {value}%." if value is not None else "Current humidity is unavailable."
        if "uv index" in text:
            value = day_value("uv_index_max")
            return f"Today's maximum UV index near {city} is {value}." if value is not None else "The UV index is unavailable."
        if "sunrise" in text or "sunset" in text:
            key = "sunrise" if "sunrise" in text else "sunset"
            value = day_value(key)
            return f"{key.capitalize()} near {city} is at {value.split('T')[-1]} local time." if isinstance(value, str) else f"{key.capitalize()} time is unavailable."
        if text == "does it feel hot outside":
            value = result.get("feels_like")
            return f"It feels like {round(value)}°C near {city}." if isinstance(value, (int, float)) else self.weather_text()
        if text in {"should i wear a jacket", "what should i wear for today's weather", "is it cold enough for a hoodie"}:
            value = result.get("feels_like")
            if not isinstance(value, (int, float)):
                return self.weather_text()
            return (f"It feels like {round(value)}°C near {city}; a jacket may be comfortable."
                    if value < 18 else f"It feels like {round(value)}°C near {city}; a jacket may be too warm.")
        if "rain" in text or "umbrella" in text:
            chance = day_value("precipitation_probability_max")
            if chance is None:
                return "I couldn't verify the current rain forecast."
            if "evening" in text:
                return f"The highest forecast rain chance near {city} today is {chance}%; I don't have an evening-specific figure."
            label = "tomorrow" if index == 1 else "today"
            return f"The highest forecast rain chance near {city} {label} is {chance}%."
        if text in {"weather tomorrow", "what is the forecast for the weekend"}:
            high, low = day_value("temperature_2m_max"), day_value("temperature_2m_min")
            chance = day_value("precipitation_probability_max")
            if high is None or low is None:
                return "That weather forecast is unavailable."
            label = "tomorrow" if index == 1 else "on Saturday"
            return f"Near {city} {label}: {round(low)}–{round(high)}°C, with up to {chance}% rain chance."
        return self.weather_text()
