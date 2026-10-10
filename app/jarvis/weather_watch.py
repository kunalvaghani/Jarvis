"""Bad-weather and emergency alerts while Jarvis is running.

Every `interval_minutes` (default 30), even while Jarvis is busy, this checks the next 36 hours for the
user's location and speaks an alert once per hazard (again only if it gets worse):

* Open-Meteo forecast: thunderstorms and hail, heavy rain (IMD-style: 64.5 mm/day heavy, 115.6 very heavy,
  or 10 mm/h bursts), strong gusts, heat (42 °C+), cold, dense fog;
* Open-Meteo air quality: unhealthy US AQI (151+);
* USGS earthquakes (M4.5+ within 300 km in the last day), GDACS orange/red disasters (cyclones, floods,
  droughts) within 500 km, NASA EONET severe storms and wildfires within 300 km;
* Open-Meteo flood: river discharge forecast well above its median.

These are forecasts and public feeds, not official government warnings; alerts say so and name the source.
"""
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import threading
import time

import requests

LEVELS = {"notice": 0, "warning": 1, "severe": 2}
WMO = {95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
       65: "heavy rain", 82: "violent rain showers", 75: "heavy snow", 67: "freezing rain"}


def distance(lat, lon, lat2, lon2):
    a, b, c, d = map(math.radians, (lat, lon, lat2, lon2))
    h = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def when(stamp, now):
    """'now', 'around 4 PM today', 'tomorrow around 9 AM'."""
    moment = datetime.fromisoformat(stamp)
    if moment <= now + timedelta(minutes=59):
        return "now"
    hour = moment.strftime("%I %p").lstrip("0")
    day = "today" if moment.date() == now.date() else "tomorrow" if moment.date() == (now + timedelta(days=1)).date() \
        else moment.strftime("on %A")
    return "around " + hour + " " + day if day == "today" else day + " around " + hour


def hazards(forecast, air=None, quakes=None, gdacs=None, eonet=None, flood=None, location=None, now=None, hours=36):
    """Pure rules over provider JSON -> [{id, kind, level, message, starts}] (most severe first)."""
    location = location or {}
    lat, lon = location.get("latitude"), location.get("longitude")
    found = []

    def add(kind, level, message, starts, day=None):
        found.append({"id": kind + ":" + (day or starts[:10]), "kind": kind, "level": level, "message": message,
                      "starts": starts})
    hourly = (forecast or {}).get("hourly") or {}
    times = hourly.get("time") or []
    now = now or datetime.now()
    window = [i for i, t in enumerate(times)
              if now - timedelta(hours=1) <= datetime.fromisoformat(t) <= now + timedelta(hours=hours)]

    def series(name):
        values = hourly.get(name) or []
        return [(times[i], values[i]) for i in window if i < len(values) and isinstance(values[i], (int, float))]
    storms = [(t, v) for t, v in series("weather_code") if int(v) in {95, 96, 99}]
    if storms:
        worst = max(int(v) for _, v in storms)
        rain = max((v for t, v in series("precipitation") if t >= storms[0][0]), default=0)
        gust = max((v for t, v in series("wind_gusts_10m") if t >= storms[0][0]), default=0)
        add("thunderstorm", "severe" if worst in {96, 99} else "warning",
            WMO[worst].capitalize() + " expected " + when(storms[0][0], now) +
            (", with up to " + str(round(rain)) + " mm of rain an hour" if rain >= 2 else "") +
            (" and gusts near " + str(round(gust)) + " km/h" if gust >= 40 else "") + ".", storms[0][0])
    bursts = [(t, v) for t, v in series("precipitation") if v >= 10]
    if bursts and not storms:
        peak = max(bursts, key=lambda x: x[1])
        add("heavy_rain_burst", "severe" if peak[1] >= 30 else "warning",
            "Very heavy rain expected " + when(bursts[0][0], now) + ", up to " + str(round(peak[1])) + " mm in an hour.",
            bursts[0][0])
    gusts = [(t, v) for t, v in series("wind_gusts_10m") if v >= 60]
    if gusts:
        peak = max(gusts, key=lambda x: x[1])
        add("wind", "severe" if peak[1] >= 90 else "warning",
            "Strong winds expected " + when(gusts[0][0], now) + ", gusts up to " + str(round(peak[1])) + " km/h. "
            "Secure loose things outside.", gusts[0][0])
    heat = [(t, v) for t, v in series("temperature_2m") if v >= 42]
    if heat:
        peak = max(heat, key=lambda x: x[1])
        add("heat", "severe" if peak[1] >= 45 else "warning",
            "Heatwave conditions " + when(heat[0][0], now) + ", up to " + str(round(peak[1])) + " °C. "
            "Drink water and avoid the afternoon sun.", heat[0][0])
    cold = [(t, v) for t, v in series("temperature_2m") if v <= 4]
    if cold:
        low = min(cold, key=lambda x: x[1])
        add("cold", "severe" if low[1] <= 0 else "warning",
            "Very cold " + when(cold[0][0], now) + ", down to " + str(round(low[1])) + " °C.", cold[0][0])
    fog = [(t, v) for t, v in series("visibility") if v < 200]
    if fog:
        add("fog", "warning", "Dense fog " + when(fog[0][0], now) + ", visibility under 200 metres. Drive carefully.",
            fog[0][0])
    daily = (forecast or {}).get("daily") or {}
    for i, day in enumerate((daily.get("time") or [])[:2]):
        total = (daily.get("precipitation_sum") or [0] * 3)[i] or 0
        if total >= 64.5:
            level = "severe" if total >= 115.6 else "warning"
            word = "extremely heavy" if total >= 204.5 else "very heavy" if total >= 115.6 else "heavy"
            label = "today" if day == now.date().isoformat() else "tomorrow"
            add("heavy_rain", level, word.capitalize() + " rain forecast " + label + ": about " + str(round(total)) +
                " mm. Watch for waterlogging and avoid flooded roads.", day + "T06:00", day)
        uv = (daily.get("uv_index_max") or [0] * 3)[i] or 0
        if uv >= 11 and day == now.date().isoformat():
            add("uv", "notice", "Extreme UV today (index " + str(round(uv)) + "). Use sunscreen and shade.", day + "T11:00", day)
    if air:
        a_hourly = air.get("hourly") or {}
        a_times = a_hourly.get("time") or []
        values = [(a_times[i], v) for i, v in enumerate(a_hourly.get("us_aqi") or [])
                  if isinstance(v, (int, float)) and i < len(a_times)
                  and now - timedelta(hours=1) <= datetime.fromisoformat(a_times[i]) <= now + timedelta(hours=24)]
        bad = [(t, v) for t, v in values if v >= 151]
        if bad:
            peak = max(bad, key=lambda x: x[1])
            level = "severe" if peak[1] >= 201 else "warning"
            label = "hazardous" if peak[1] >= 301 else "very unhealthy" if peak[1] >= 201 else "unhealthy"
            add("air", level, "Air quality turns " + label + " " + when(bad[0][0], now) + " (US AQI up to " +
                str(round(peak[1])) + "). Limit time outdoors; a mask helps.", bad[0][0])
    if lat is not None:
        for feature in (quakes or {}).get("features", []):
            props, coords = feature.get("properties", {}), feature.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2 or not props.get("mag"):
                continue
            km = distance(lat, lon, coords[1], coords[0])
            age = time.time() - (props.get("time") or 0) / 1000
            if age <= 86400 and ((props["mag"] >= 4.5 and km <= 300) or (props["mag"] >= 6 and km <= 500)):
                at = datetime.fromtimestamp(props["time"] / 1000).isoformat(timespec="minutes")
                add("earthquake:" + str(feature.get("id")), "severe" if props["mag"] >= 6 else "warning",
                    "Magnitude " + str(props["mag"]) + " earthquake " + str(round(km)) + " km away (" +
                    str(props.get("place", "")) + ").", at, at[:10])
        for item in (gdacs or {}).get("items", []):
            try:
                km = distance(lat, lon, float(item["lat"]), float(item["long"]))
            except (KeyError, TypeError, ValueError):
                continue
            level = str(item.get("alertlevel", "")).casefold()
            if km <= 500 and level in {"orange", "red"}:
                add("gdacs:" + str(item.get("guid", item.get("title", "")))[-40:], "severe" if level == "red" else "warning",
                    "Disaster alert " + str(round(km)) + " km away: " + str(item.get("title", ""))[:160] + " (GDACS " + level + ").",
                    now.isoformat(timespec="minutes"))
        for event in (eonet or {}).get("events", []):
            category = ",".join(c.get("title", "") for c in event.get("categories", []))
            if not any(word in category for word in ("Severe Storms", "Wildfires", "Floods", "Volcanoes")):
                continue
            for geometry in (event.get("geometry") or [])[-1:]:
                coords = geometry.get("coordinates") or []
                if geometry.get("type") == "Point" and len(coords) >= 2 and distance(lat, lon, coords[1], coords[0]) <= 300:
                    add("eonet:" + str(event.get("id")), "notice",
                        category + " nearby: " + str(event.get("title", ""))[:140] + " (NASA EONET).", now.isoformat(timespec="minutes"))
    if flood:
        f_daily = flood.get("daily") or {}
        for day, value, median in zip(f_daily.get("time") or [], f_daily.get("river_discharge") or [],
                                      f_daily.get("river_discharge_median") or []):
            if isinstance(value, (int, float)) and isinstance(median, (int, float)) and median > 1 and value >= 3 * median:
                add("flood", "warning", "Nearby rivers are forecast to run about " + str(round(value / median)) +
                    " times their usual level " + ("today" if day == now.date().isoformat() else "on " + day) +
                    ". Watch for flooding.", day + "T06:00", day)
                break
    return sorted(found, key=lambda h: (-LEVELS[h["level"]], h["starts"]))


class WeatherWatch:
    def __init__(self, actions, options=None, http=None, clock=time.time):
        options = options or {}
        self.actions = actions
        self.enabled = bool(options.get("enabled", True))
        self.interval = float(options.get("interval_minutes", 30)) * 60
        self.min_level = options.get("min_level", "warning")
        self.http = http or requests.Session()
        self.clock = clock
        self.path = Path(actions.base) / ".jarvis-runtime" / "weather-alerts.json"
        self.seen = self._load()
        self.last = None
        self.stop = threading.Event()
        self.thread = None
        self.lock = threading.Lock()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {k: v for k, v in data.items() if self.clock() - v.get("at", 0) < 3 * 86400}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.seen), encoding="utf-8")
        except OSError:
            pass

    def realtime(self):
        from .capability_guide import live_realtime
        if getattr(self, "_realtime", None) is None:
            self._realtime = live_realtime(self.actions)
        return self._realtime

    def location(self):
        realtime = self.realtime()
        found = realtime.detect_location(lambda: self.stop.is_set()) if realtime is not None else None
        if found and not found.get("stale"):
            return found
        city = self.actions.config.get("weather", {}).get("fallback_city", "")
        if city:
            data = self.get("https://geocoding-api.open-meteo.com/v1/search", {"name": city, "count": 1})
            row = (data.get("results") or [None])[0] if data else None
            if row:
                return {"latitude": row["latitude"], "longitude": row["longitude"], "name": row.get("name", city),
                        "accuracy": "saved city"}
        return None

    def get(self, url, params=None, timeout=15):
        try:
            response = self.http.get(url, params=params, timeout=(5, timeout),
                                     headers={"User-Agent": "JarvisPersonalAssistant/1.0 (weather alerts)"})
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            return None

    def check(self, force=False):
        """Fetch everything and return (location, hazards, sources_ok)."""
        place = self.location()
        if not place:
            return None, [], {}
        lat, lon = round(place["latitude"], 4), round(place["longitude"], 4)
        forecast = self.get("https://api.open-meteo.com/v1/forecast", {
            "latitude": lat, "longitude": lon, "forecast_days": 3, "timezone": "auto",
            "hourly": "temperature_2m,precipitation,weather_code,wind_gusts_10m,visibility",
            "daily": "precipitation_sum,uv_index_max,temperature_2m_max,temperature_2m_min"})
        air = self.get("https://air-quality-api.open-meteo.com/v1/air-quality",
                       {"latitude": lat, "longitude": lon, "hourly": "us_aqi", "forecast_days": 2, "timezone": "auto"})
        quakes = self.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson")
        flood = self.get("https://flood-api.open-meteo.com/v1/flood",
                         {"latitude": lat, "longitude": lon, "daily": "river_discharge,river_discharge_median", "forecast_days": 5})
        gdacs = eonet = None
        realtime = self.realtime()
        if realtime is not None:
            for key in ("gdacs", "eonet"):
                try:
                    row = realtime.query(key, {}, lambda: self.stop.is_set())
                    if row.get("status") == "ok":
                        gdacs, eonet = (row.get("data"), eonet) if key == "gdacs" else (gdacs, row.get("data"))
                except Exception:
                    pass
        offset = (forecast or {}).get("utc_offset_seconds")
        now = (datetime.utcnow() + timedelta(seconds=offset)) if isinstance(offset, (int, float)) else datetime.now()
        found = hazards(forecast, air, quakes, gdacs, eonet, flood, place, now)
        sources = {"forecast": forecast is not None, "air quality": air is not None, "earthquakes": quakes is not None,
                   "disasters": gdacs is not None, "floods": flood is not None}
        self.last = {"at": self.clock(), "place": place, "hazards": found, "sources": sources,
                     "today": self._today(forecast)}
        return place, found, sources

    @staticmethod
    def _today(forecast):
        daily = (forecast or {}).get("daily") or {}
        try:
            return {"max": daily["temperature_2m_max"][0], "min": daily["temperature_2m_min"][0],
                    "rain": daily["precipitation_sum"][0]}
        except (KeyError, IndexError, TypeError):
            return {}

    def announce(self, place, found):
        """Speak hazards not yet announced (or that got worse). Returns what was announced."""
        fresh = []
        for hazard in found:
            if LEVELS[hazard["level"]] < LEVELS.get(self.min_level, 1):
                continue
            before = self.seen.get(hazard["id"])
            if before and LEVELS[before["level"]] >= LEVELS[hazard["level"]]:
                continue
            fresh.append(hazard)
            self.seen[hazard["id"]] = {"level": hazard["level"], "at": self.clock()}
        if not fresh:
            return []
        self._save()
        name = place.get("name") or "your area"
        worst = fresh[0]["level"]
        text = ("Weather alert for " + name + ": " if worst != "notice" else "Heads up for " + name + ": ") + \
            " ".join(h["message"] for h in fresh[:3]) + " This is from forecast data, not an official warning."
        self.actions.report("spoken_reply", text)
        from .media_player import card
        self.actions.report("media_card", card("weather", "alert" if worst != "notice" else "notice",
                                               fresh[0]["message"][:90], name, "", 0, 0,
                                               ("Severe" if worst == "severe" else "Warning" if worst == "warning" else "Notice")
                                               + (" · +" + str(len(fresh) - 1) + " more" if len(fresh) > 1 else "")))
        memory = getattr(self.actions, "memory", None)
        if memory is not None:
            memory.record("Weather alert", text)
        return fresh

    def summary(self):
        """Spoken answer for 'is bad weather coming' (always checks fresh)."""
        place, found, sources = self.check(force=True)
        if place is None:
            return "I couldn't work out your location for weather alerts. Set weather.fallback_city in config."
        name = place.get("name") or "your area"
        failed = [k for k, ok in sources.items() if not ok]
        if found:
            text = "For " + name + " in the next 36 hours: " + " ".join(h["message"] for h in found[:4])
        else:
            today = (self.last or {}).get("today") or {}
            text = ("No bad weather expected for " + name + " in the next 36 hours" +
                    (", today " + str(round(today["min"])) + " to " + str(round(today["max"])) + " °C" if today.get("max") is not None else "") +
                    (" with no rain" if today.get("rain") == 0 else ", about " + str(round(today["rain"])) + " mm of rain" if today.get("rain") else "") + ".")
        if failed:
            text += " I couldn't reach: " + ", ".join(failed) + "."
        return text

    def start(self):
        if self.enabled and not self.thread:
            self.thread = threading.Thread(target=self.run, name="Jarvis weather watch", daemon=True)
            self.thread.start()
        return self

    def close(self):
        self.stop.set()

    def run(self):
        if self.stop.wait(45):  # Let startup finish first.
            return
        while not self.stop.is_set():
            try:
                with self.lock:
                    place, found, _ = self.check()
                if place:
                    self.announce(place, found)
            except Exception:
                pass
            self.stop.wait(self.interval)


def parse_command(text):
    import re
    from .commands import Command
    clean = re.sub(r"[.!?]+$", "", text.strip())
    if re.fullmatch(r"(?:any |are there (?:any )?|check (?:for )?|show (?:me )?)?(?:weather|storm|climate|emergency|disaster) "
                    r"(?:alerts?|warnings?)(?: (?:today|now|for (?:today|tomorrow)|near me|here))?|"
                    r"(?:is|will) (?:there )?(?:any )?(?:bad|severe|extreme) weather(?: coming| expected)?(?: today| tomorrow| soon)?|"
                    r"is (?:a |any )?(?:storm|cyclone|heatwave|heat wave|flood) coming|any (?:upcoming )?bad weather", clean, re.I):
        return Command("weather_alerts", "check")
    return None
