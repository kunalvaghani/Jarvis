"""God's Eye View, fully wired into Jarvis.

* Server: the local God's Eye View app (integrations/gods-eye-view-src) starts with Jarvis and is kept running.
* Visualization: "show me Paris", "show flights near me", "show military over the Gulf", "what's the weather
  doing", "show traffic cameras in London", "switch to thermal" open God's Eye in Jarvis's browser and drive it
  with God's Eye's own voice actions (fly_to_location, set_layer_visibility, set_visual_style, set_hud, control_cctv,
  annotate_map + fly_route, frame_overhead, control_cockpit).
* Runtime absorption: a side thread polls the God's Eye server every minute for a 25-mile (40 km) radius around
  you: aircraft (emergency squawks 7700/7600/7500, low and military traffic), your local SDR receiver, fire
  perimeters, cyclone tracks, weather effects and the regional brief, plus USGS earthquakes. The cache feeds
  questions ("why is it so loud outside?", "why am I hearing sirens?") before any web search, the multi-context
  situation, and proactive alerts on the island.
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import threading
import time

import requests

BASE = "http://127.0.0.1:4173"
SQUAWKS = {"7700": "general emergency", "7600": "radio failure", "7500": "hijack"}
LAYERS = {  # Spoken word -> God's Eye layer id (from its voice layer manifest).
    "flights": "flights", "flight": "flights", "planes": "flights", "plane": "flights", "aircraft": "flights",
    "air traffic": "flights", "airplanes": "flights", "jets": "flights",
    "military": "military", "military flights": "military", "military aircraft": "military", "military planes": "military",
    "military bases": "military-installations", "bases": "military-installations", "installations": "military-installations",
    "my receiver": "local-adsb", "sdr": "local-adsb", "local adsb": "local-adsb",
    "ships": "ais-live-vessels", "vessels": "ais-live-vessels", "boats": "ais-live-vessels",
    "satellites": "satellites", "satellite": "satellites", "rocket launches": "rocket-launches", "launches": "rocket-launches",
    "space missions": "rocket-launches", "earthquakes": "earthquakes", "quakes": "earthquakes",
    "fires": "local-firms", "wildfires": "local-firms", "active fires": "local-firms", "fire perimeters": "fire-perimeters",
    "cyclones": "weather-cyclones", "hurricanes": "weather-cyclones", "typhoons": "weather-cyclones", "storms": "weather-cyclones",
    "rain": "weather-radar", "radar": "weather-radar", "rain radar": "weather-radar", "weather": "weather-radar",
    "clouds": "weather-satellite", "lightning": "weather-lightning", "wind": "wind", "winds": "wind",
    "traffic": "traffic", "road traffic": "traffic", "congestion": "traffic", "transit": "transit", "buses": "transit",
    "trains": "transit", "metro": "transit", "trams": "transit", "bikes": "bikeshare",
    "cameras": "cctv", "cctv": "cctv", "traffic cameras": "cctv", "webcams": "cctv",
    "license plate readers": "alpr-cameras", "alpr": "alpr-cameras", "flock cameras": "alpr-cameras",
    "data centers": "local-datacenters", "datacenters": "local-datacenters", "dams": "local-dams",
    "submarine cables": "telegeography-submarine-cables", "undersea cables": "telegeography-submarine-cables",
    "street level": "street-level", "recent imagery": "recent-imagery", "satellite imagery": "recent-imagery",
}
# Each request type turns on related layers too ("show military" = flights and mapped installations).
BUNDLES = {"military": ["military", "military-installations"], "weather-radar": ["weather-radar", "weather-lightning"],
           "weather-cyclones": ["weather-cyclones", "weather-satellite"], "flights": ["flights"],
           "local-firms": ["local-firms", "fire-perimeters"]}
STYLES = {"thermal": ("style", "thermal"), "flir": ("style", "thermal"), "iron bow": ("style", "thermal"),
          "night vision": ("style", "surveillance"), "nvg": ("style", "surveillance"), "surveillance": ("style", "surveillance"),
          "normal": ("style", "normal"), "standard": ("style", "normal"), "tactical": ("hud", "tactical"),
          "cyber": ("hud", "cyber"), "radar": ("hud", "cyber"), "noir": ("style", "noir"), "retro": ("style", "retro"),
          "anime": ("style", "anime"), "snow": ("style", "snow"), "operator": ("hud", "operator"), "minimal": ("hud", "minimal")}
ME = re.compile(r"(?i)^(?:me|my area|my location|here|overhead|above me|over me|near me|around me|my city|nearby|"
                r"where i am|my place|my home|home)$")
LAYER_WORDS = "|".join(sorted((re.escape(k) for k in LAYERS), key=len, reverse=True))


def distance(lat, lon, lat2, lon2):
    a, b, c, d = map(math.radians, (lat, lon, lat2, lon2))
    h = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def bearing(lat, lon, lat2, lon2):
    a, b, c, d = map(math.radians, (lat, lon, lat2, lon2))
    y = math.sin(d - b) * math.cos(c)
    x = math.cos(a) * math.sin(c) - math.sin(a) * math.cos(c) * math.cos(d - b)
    deg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][int((deg + 22.5) // 45) % 8]


# --- spoken commands ------------------------------------------------------------------------------------------
def parse_command(text):
    """Visualization requests -> Command('gods_eye_show', json) / ('gods_eye_explain', question) / None."""
    from .commands import Command
    clean = re.sub(r"[.!?]+$", "", text.strip())
    lower = clean.casefold()
    explain = re.fullmatch(r"(?:why is it (?:so )?(?:loud|noisy)(?: outside| here| right now)?|why (?:am i hearing|do i hear|"
                           r"are there|is there) (?:sirens?|(?:a )?helicopters?|(?:so many )?planes|jets?|(?:a )?loud noise)(?: outside)?|"
                           r"what(?:'s| is| was) (?:that|this) (?:noise|sound|plane|helicopter|aircraft|jet)(?: overhead| above me| outside)?|"
                           r"(?:what|which) (?:planes|aircraft|flights|helicopters) are (?:above|over|near) (?:me|us|my house)|"
                           r"(?:are there |any )(?:planes|aircraft|helicopters|military (?:aircraft|planes|flights)) (?:overhead|above me|near me|nearby)|"
                           r"what(?:'s| is) (?:happening|going on) (?:around me|near me|in my area|outside)|"
                           r"(?:any|are there any) (?:emergencies|emergency flights|fires) (?:near me|nearby|around me))", lower)
    if explain:
        return Command("gods_eye_explain", clean)
    if re.fullmatch(r"(?:update|upgrade) (?:the )?god'?s ?eye(?: view)?(?: repo(?:sitory)?)?", lower):
        return Command("gods_eye_update", "")
    if re.fullmatch(r"god'?s ?eye(?: view)? status|what(?:'s| is) god'?s ?eye (?:seeing|showing)|god'?s ?eye report", lower):
        return Command("gods_eye_status", "")
    spec = {}
    style = re.fullmatch(r"(?:switch|change|go|set)(?: (?:god'?s ?eye|the globe|the view))? to (?:the )?(.+?)(?: view| mode| vision| ui| hud| style)?|"
                         r"(?:turn on |use |enable )?(?:the )?(thermal|flir|iron bow|night vision|nvg|cyber|noir|retro|anime|snow|surveillance|tactical)"
                         r"(?: view| mode| vision| radar| ui| hud| style)?", lower)
    if style:
        word = (style[1] or style[2] or "").strip()
        word = re.sub(r" (?:radar|camera)$", "", word)
        if word in STYLES:
            return Command("gods_eye_show", json.dumps({"place": "", "style": STYLES[word]}))
    route = re.fullmatch(r"(?:show me |show |fly |drive |take me )?(?:me )?(?:the )?(?:route|way|directions|path)(?: to drive)? from (.+?) to (.+?)"
                         r"(?: in god'?s ?eye| on the globe)?", lower) or \
        re.fullmatch(r"fly (?:me )?(?:along |down )?(?:the )?route (?:from )?(.+?) to (.+)", lower)
    if route:
        return Command("gods_eye_show", json.dumps({"place": "", "route": [route[1].strip(), route[2].strip()]}))
    m = re.fullmatch(r"(?:show me|show|display|open|let me see|i (?:want|need) to see|can i see|pull up|bring up)(?: the| all| live| any)?"
                     r" (?P<layer>" + LAYER_WORDS + r")(?: (?:flights|aircraft|planes|activity|layer|data|radar|map))?"
                     r"(?: (?:over|in|near|around|above|at|on|for) (?P<place>.+?))?(?: (?P<where>overhead|near me|around me|above me|here))?"
                     r"(?: (?:in|on) (?:god'?s ?eye(?: view)?|the globe|the map|satellite view))?", lower)
    weather_q = re.fullmatch(r"what(?:'s| is) the (?P<layer>weather|traffic|rain|wind) (?:doing|like)(?: (?:in|at|near|over) (?P<place>.+?))?(?: right now| now)?(?: on the (?:globe|map))?", lower)
    m = m or weather_q
    if m:
        word = m.group("layer")
        layer = LAYERS[word]
        place = (m.groupdict().get("place") or "").strip()
        where = (m.groupdict().get("where") or "").strip()
        if not place or ME.fullmatch(place) or where:
            place = "me" if (not place or ME.fullmatch(place)) else place
        layers = BUNDLES.get(layer, [layer])
        if layer == "flights" and place == "me":
            layers = ["flights", "local-adsb"]  # Overhead traffic also uses your own SDR receiver, if one is set up.
        spec = {"place": place, "layers": layers, "kind": layer}
        if weather_q or layer in {"traffic", "weather-radar"}:
            spec["lock"] = True
        if layer == "cctv":
            spec["cctv"] = True
        return Command("gods_eye_show", json.dumps(spec))
    show = re.fullmatch(r"(?P<verb>show me|let me see|i (?:want|need) to see|take me to|fly (?:me )?to|zoom (?:in )?(?:on|to|into)|"
                        r"go to|open|look at|show)(?: the)? (?P<place>.+?)(?P<view> (?:in|on|from|with) (?:god'?s ?eye(?: view)?|the globe|"
                        r"satellite(?: view)?|3d|space|above|the map)| satellite view| from above| on the globe)?(?P<cams> (?:and|with) (?:the )?"
                        r"(?:cameras|cctv)(?: around it)?)?", lower)
    if show:
        place = show["place"].strip()
        explicit = bool(show["view"]) or lower.startswith(("take me to", "fly to", "fly me to", "zoom"))
        if show["verb"] in {"go to", "open", "look at", "show"} and not show["view"]:
            return None  # "open notepad" / "go to settings" are not places on the globe.
        if not explicit and (re.search(r"\b(?:my |the |your )?(?:emails?|mail|files?|folders?|desktop|downloads|documents|queue|tasks?|"
                                       r"settings|notes?|calendar|screen|history|memory|repos?|code|projects?|messages?|chats?|"
                                       r"news|weather|time|playlist|songs?|videos?|music|photos|apps?|windows?|tabs?|"
                                       r"how|what|why|who|when|which|it|that|this|them|more|less|options|results|menu)\b", place)
                             or len(place.split()) > 6):
            return None
        if ME.fullmatch(place):
            place = "me"
        return Command("gods_eye_show", json.dumps({"place": place, "layers": ["cctv"] if show["cams"] else [],
                                                    "cctv": bool(show["cams"]), "kind": "place"}))
    return None


# --- server, geocoding and the page ----------------------------------------------------------------------------
class GodsEye:
    def __init__(self, actions, options=None, http=None, clock=time.time):
        options = options or {}
        self.actions = actions
        self.options = options
        self.enabled = bool(options.get("enabled", True))
        self.radius_km = float(options.get("radius_km", 40))
        self.interval = float(options.get("poll_seconds", 60))
        self.http = http or requests.Session()
        self.clock = clock
        self.server = None
        self.cache = {}
        self.seen = {}
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.path = Path(actions.base) / ".jarvis-runtime" / "gods-eye-cache.json"
        self.enabled_layers = set()  # Layers Jarvis turned on for the last request.
        self.last_view = None  # {"latitude", "longitude", "altitude", "label"} of the last place shown.
        self.view_history = []  # Earlier views, for "go back to the previous camera position".
        self.last_route = ""  # Label of the last drawn route, for "fly along the route".

    def ensure_server(self, cancelled=lambda: False):
        from .gods_eye_view import GodsEyeView, ready
        if ready():
            return BASE
        self.prepare_cameras()  # Toronto (and Ontario 511 with a key) before the server reads its .env.
        if self.server is None:
            self.server = getattr(self.actions, "gods_eye_view", None) or GodsEyeView()
            self.actions.gods_eye_view = self.server
        return self.server.start(cancelled).rstrip("/")

    def prepare_cameras(self, force=False):
        from .gods_eye_cameras import build
        from .gods_eye_view import SOURCE
        try:
            return build(self.actions.base, SOURCE, force=force)
        except Exception as exc:
            return {"toronto": 0, "ontario": 0, "changed": False, "errors": [str(exc)[:160]]}

    def refresh_cameras(self, cancelled=lambda: False):
        """Rebuild the extra camera pack and restart God's Eye's server so it loads it."""
        from .gods_eye_cameras import ontario_key, summary
        from .gods_eye_view import SOURCE, ready
        result = self.prepare_cameras(force=True)
        if ready():
            if self.server is not None and self.server.process is not None:
                self.server.close()
            else:
                stop_vite(SOURCE)
            deadline = time.time() + 10
            while ready() and time.time() < deadline:
                time.sleep(.3)
        self.ensure_server(cancelled)
        return summary(result, bool(ontario_key(self.actions.base)))

    def api(self, path, params=None, timeout=20):
        response = self.http.get(BASE + path, params=params, timeout=(3, timeout))
        if response.status_code >= 400:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def here(self):
        realtime = getattr(self.actions, "realtime", None)
        location = realtime.detect_location(lambda: self.stop.is_set()) if realtime is not None else None
        if location and not location.get("stale"):
            return {"latitude": location["latitude"], "longitude": location["longitude"], "name": location.get("name", "your location")}
        city = self.actions.config.get("weather", {}).get("fallback_city", "")
        return self.geocode(city) if city else None

    def geocode(self, place):
        """Place -> {latitude, longitude, name, span_km}. OpenStreetMap Nominatim ranked by importance handles seas,
        regions and landmarks ("the Persian Gulf", "Eiffel Tower"); God's Eye's geocoder and Open-Meteo are fallbacks."""
        query = re.sub(r"(?i)^(?:the|a|an)\s+", "", place.strip())
        # "central London" found a tube line called Central; the city itself is what was meant.
        query = re.sub(r"(?i)^(?:central|downtown|greater|old town of|(?:the )?(?:city )?cent(?:er|re) of|(?:the )?heart of)\s+", "", query) or query
        try:
            contact = self.actions.config.get("realtime", {}).get("contact", "")
            rows = self.http.get("https://nominatim.openstreetmap.org/search", timeout=(3, 12),
                                 params={"q": query, "format": "jsonv2", "limit": 5, "namedetails": 1, "accept-language": "en"},
                                 headers={"User-Agent": "JarvisPersonalAssistant/1.0 " + contact}).json()
            if rows:
                row = max(rows, key=lambda r: float(r.get("importance") or 0))
                south, north, west, east = (float(v) for v in row.get("boundingbox", [0, 0, 0, 0]))
                name = (row.get("namedetails") or {}).get("name:en") or (row.get("namedetails") or {}).get("name") or row.get("name") \
                    or row.get("display_name", query).split(",")[0]
                span = distance(south, west, north, east) if north != south else 5
                if span < 50 and any(w in name.casefold() for w in ("gulf", "sea", "ocean", "bay", "strait", "channel")):
                    span = 900  # Water bodies are often a single point in OpenStreetMap.
                return {"latitude": float(row["lat"]), "longitude": float(row["lon"]), "name": name[:80], "span_km": span}
        except (requests.RequestException, ValueError, KeyError):
            pass
        data = None
        try:
            data = self.api("/api/geocode", {"q": place}, 15)
        except requests.RequestException:
            data = None
        rows = (data or {}).get("results") or []
        if rows:
            row = rows[0]
            loc = row["geometry"]["location"]
            box = row["geometry"].get("viewport") or row["geometry"].get("bounds") or {}
            span = 0
            if box:
                span = distance(box["southwest"]["lat"], box["southwest"]["lng"], box["northeast"]["lat"], box["northeast"]["lng"])
            return {"latitude": loc["lat"], "longitude": loc["lng"], "name": row.get("formatted_address", place).split(",")[0][:80],
                    "span_km": span}
        try:
            data = self.http.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": place, "count": 1},
                                 timeout=(3, 10)).json()
            row = (data.get("results") or [None])[0]
            if row:
                return {"latitude": row["latitude"], "longitude": row["longitude"],
                        "name": ", ".join(x for x in (row.get("name"), row.get("admin1"), row.get("country")) if x), "span_km": 20}
        except (requests.RequestException, ValueError):
            pass
        return None

    def card(self, phase, title, subtitle="", detail=""):
        from .media_player import card
        self.actions.report("media_card", card("godseye", phase, title, subtitle, "", 0, 0, detail))

    def show(self, spec, cancelled=lambda: False):
        """Open God's Eye at the requested place with the requested layers and style."""
        self.card("opening", "God's Eye", spec.get("place") or "Opening the globe", "Starting the console")
        self.ensure_server(cancelled)
        actions, view, label = [], None, ""
        place = spec.get("place", "")
        kind = spec.get("kind", "place")
        if spec.get("route"):
            start, end = spec["route"]
            a = self.here() if ME.fullmatch(start) else self.geocode(start)
            b = self.here() if ME.fullmatch(end) else self.geocode(end)
            if not a or not b:
                raise ValueError("I couldn't find " + (start if not a else end) + " on the map.")
            label = "Route to " + end.title()
            mid_lat, mid_lon = (a["latitude"] + b["latitude"]) / 2, (a["longitude"] + b["longitude"]) / 2
            km = distance(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
            view = {"latitude": mid_lat, "longitude": mid_lon, "altitude": max(4000, km * 1800)}
            actions += [{"name": "fly_to_location", "args": {"latitude": mid_lat, "longitude": mid_lon, "viewMode": "overview",
                                                             "rangeM": view["altitude"]}},
                        {"name": "annotate_map", "args": {"annotations": [{"type": "route", "label": label, "mode": "driving", "color": "amber",
                                                                           "points": [{"latitude": a["latitude"], "longitude": a["longitude"]},
                                                                                      {"latitude": b["latitude"], "longitude": b["longitude"]}]}],
                                                          "flyTo": False, "persist": True}},
                        {"name": "fly_route", "args": {"label": label, "speed": "normal"}}]
            place = start + " to " + end
            self.last_route = label
        elif place:
            spot = self.here() if place == "me" else self.geocode(place)
            if not spot:
                raise ValueError("I couldn't find " + place + " on the map.")
            label = "your location" if place == "me" else spot["name"]
            altitude = {"flights": 60000, "local-adsb": 60000, "military": 450000, "military-installations": 450000,
                        "weather-radar": 900000, "weather-cyclones": 2500000, "weather-satellite": 2500000,
                        "traffic": 15000, "transit": 12000, "cctv": 3000, "local-firms": 300000, "fire-perimeters": 300000,
                        "earthquakes": 1500000, "ais-live-vessels": 120000}.get(kind)
            if altitude is None:
                span = spot.get("span_km") or 10
                altitude = min(3_000_000, max(1500, span * 1400))
            view = {"latitude": spot["latitude"], "longitude": spot["longitude"], "altitude": altitude}
            actions.append({"name": "fly_to_location", "args": {"latitude": spot["latitude"], "longitude": spot["longitude"],
                                                                "viewMode": "overview", "rangeM": altitude}})
            if spec.get("zoom") in {"in", "out"}:
                actions.append({"name": "adjust_camera_zoom", "args": {"direction": spec["zoom"], "amount": "lot"}})
            if spec.get("nearest"):
                actions.append({"name": "select_nearest_aircraft", "args": {"layerId": spec["nearest"], "latitude": spot["latitude"],
                                                                             "longitude": spot["longitude"]}})
        wanted = list(spec.get("layers", []))
        if wanted or (place and not spec.get("style")):
            # A new request replaces the layers Jarvis turned on for the previous one (your own toggles are kept).
            for layer in sorted(self.enabled_layers - set(wanted)):
                actions.append({"name": "set_layer_visibility", "args": {"layerId": layer, "enabled": False}})
            self.enabled_layers = set(wanted)
        for layer in wanted:
            actions.append({"name": "set_layer_visibility", "args": {"layerId": layer, "enabled": True}})
        if spec.get("cctv"):
            actions.append({"name": "control_cctv", "args": {"action": "nearest"}})
        if spec.get("style"):
            what, value = spec["style"]
            actions.append({"name": "set_visual_style", "args": {"style": value}} if what == "style"
                           else {"name": "set_hud", "args": {"visible": "on", "layout": value}})
        if not actions:
            actions.append({"name": "get_current_view_state", "args": {}})
        result = self.actions._browser().request("gods_eye", cancelled, new_task=True, actions=actions, view=view)
        if view:
            if self.last_view:
                self.view_history = (self.view_history + [self.last_view])[-10:]
            self.last_view = {**view, "label": label}
        done = [r for r in result.get("results", []) if r.get("ok")]
        failed = [r for r in result.get("results", []) if not r.get("ok") and r["name"] != "camera_check"]
        layer_names = [r["result"].get("label", r["result"].get("layerId")) for r in done
                       if r["name"] == "set_layer_visibility" and isinstance(r.get("result"), dict) and r["result"].get("enabled")]
        text = "Showing " + (label or "God's Eye")
        if layer_names:
            text += " with " + ", ".join(layer_names)
        if spec.get("style"):
            text += " in " + spec["style"][1] + " " + ("view" if spec["style"][0] == "style" else "HUD")
        if spec.get("route"):
            text = "Flying the driving route from " + spec["route"][0] + " to " + spec["route"][1] + " in God's Eye"
        if spec.get("lock"):
            text += ". The view stays on this area"
        if spec.get("coverage_note"):
            text += (". Cyclone tracks come from NOAA and cover the Atlantic and eastern and central Pacific only, not the Indian Ocean, "
                     "so no track there doesn't mean no storm")
        if spec.get("sources"):
            text += (". Positions come from God's Eye's live flight feed (OpenSky-format states)" +
                     (" and your SDR receiver" if (self.cache.get("local_receiver") if isinstance(self.cache, dict) else None) else
                      "; no local SDR receiver is configured"))
        if failed:
            text += ". Not available: " + ", ".join(r["name"].replace("_", " ") + (" (" + str((r.get("result") or {}).get("say") or r.get("error", ""))[:80] + ")") for r in failed[:3])
        self.card("showing", label or "God's Eye", ", ".join(layer_names) or (spec.get("style") or ("", ""))[1] or "Globe view",
                  "On screen in God's Eye")
        return text + "."

    def camera(self, spec, cancelled=lambda: False):
        """Move or inspect the current God's Eye view: zoom, orbit, pan, overhead, back, label, clear, where, hide."""
        self.ensure_server(cancelled)
        browser = self.actions._browser()

        def run(steps, view=None):
            return browser.request("gods_eye", cancelled, new_task=True, actions=steps, view=view).get("results", [])

        def current():
            for row in run([{"name": "get_current_view_state", "args": {}}]):
                camera = (row.get("result") or {}).get("camera") or {}
                center = (row.get("result") or {}).get("center") or camera  # The point in view, not the camera itself.
                if isinstance(center.get("latitude"), (int, float)):
                    return {"latitude": center["latitude"], "longitude": center["longitude"],
                            "altitude": max(300, float(camera.get("heightM") or 6000))}
            return self.last_view
        if spec.get("zoom"):
            run([{"name": "adjust_camera_zoom", "args": {"direction": spec["zoom"], "amount": spec.get("amount", "medium")}}])
            return "Zoomed " + spec["zoom"] + "."
        if spec.get("move") == "orbit":
            run([{"name": "move_camera", "args": {"motion": "orbit", "mode": "continuous", "speed": "slow"}}])
            return "Orbiting around this area. Say 'zoom in' or 'go to' somewhere to stop."
        if spec.get("move") == "pan":
            run([{"name": "move_camera", "args": {"motion": "pan", "direction": spec.get("direction", "up"), "mode": "once"}}])
            return "Moved the view " + {"up": "north", "down": "south", "left": "west", "right": "east"}[spec.get("direction", "up")] + "."
        if spec.get("overhead") or spec.get("back"):
            if spec.get("back"):
                if not self.view_history:
                    return "There's no earlier view to go back to."
                view = self.view_history.pop()
            else:
                view = current()
                if not view:
                    return "Open a place in God's Eye first."
            run([{"name": "fly_to_location", "args": {"latitude": view["latitude"], "longitude": view["longitude"],
                                                      "viewMode": "overview", "rangeM": view["altitude"]}}], view)
            if spec.get("back"):
                self.last_view = view
            return ("Back to " + (view.get("label") or "the previous view") + ".") if spec.get("back") else "Looking straight down on this area."
        if spec.get("label"):
            view = current()
            if not view:
                return "Open a place in God's Eye first."
            name = (self.last_view or {}).get("label") or "Here"
            run([{"name": "annotate_map", "args": {"annotations": [{"type": "pin", "label": name[:60], "latitude": view["latitude"],
                                                                     "longitude": view["longitude"], "color": "amber"}],
                                                   "flyTo": False, "persist": True}}])
            return "Labelled " + name + " on the map."
        if spec.get("clear"):
            run([{"name": "clear_annotations", "args": {}}])
            return "Removed the annotations."
        if spec.get("fly_route"):
            if not self.last_route:
                return "I haven't drawn a route yet. Say 'draw a route from' one place 'to' another."
            run([{"name": "fly_route", "args": {"label": self.last_route, "speed": "normal"}}])
            return "Flying along " + self.last_route + "."
        if spec.get("where"):
            view = current()
            if not view:
                return "God's Eye isn't showing anything yet."
            near = (self.last_view or {}).get("label")
            return ("God's Eye is looking at {:.3f}, {:.3f} from about {} km up".format(view["latitude"], view["longitude"],
                                                                                   round(view["altitude"] / 1000, 1)) +
                    (", last place shown: " + near if near else "") + ".")
        if spec.get("hide"):
            layers = sorted(self.enabled_layers) if spec["hide"] == ["*"] else spec["hide"]
            if not layers:
                return "I haven't turned on any layers to hide."
            run([{"name": "set_layer_visibility", "args": {"layerId": layer, "enabled": False}} for layer in layers[:10]])
            self.enabled_layers -= set(layers)
            return "Hid " + ", ".join(layers) + "; the camera stays where it is."
        raise ValueError("Unknown God's Eye camera request.")

    # --- runtime absorption ----------------------------------------------------------------------------------------
    def start(self):
        if self.enabled and not self.thread:
            self.thread = threading.Thread(target=self.run, name="Jarvis God's Eye feed", daemon=True)
            self.thread.start()
        return self

    def close(self):
        self.stop.set()

    def run(self):
        if self.stop.wait(20):
            return
        failures = 0
        while not self.stop.is_set():
            try:
                if self.options.get("autostart", True):
                    self.ensure_server(lambda: self.stop.is_set())
                self.poll()
                self.alert()
                failures = 0
            except Exception as exc:
                failures += 1
                with self.lock:
                    self.cache["error"] = type(exc).__name__ + ": " + str(exc)[:200]
            self.stop.wait(self.interval * (1 if failures < 3 else 5))

    def poll(self):
        here = self.here()
        if not here:
            return {}
        lat, lon, radius = here["latitude"], here["longitude"], self.radius_km
        snapshot = {"at": self.clock(), "at_local": datetime.now().strftime("%H:%M"), "location": here, "radius_km": radius}
        flights = self.api("/api/flights", {"lat": round(lat, 4), "lon": round(lon, 4)}) or {}
        nearby = []
        for s in flights.get("states") or []:
            try:
                if s[6] is None or s[5] is None:
                    continue
                km = distance(lat, lon, s[6], s[5])
                if km > radius:
                    continue
                nearby.append({"callsign": (s[1] or "").strip() or s[0], "icao24": s[0], "country": s[2], "km": round(km, 1),
                               "altitude_m": round(s[7] or s[13] or 0), "on_ground": bool(s[8]), "speed_kmh": round((s[9] or 0) * 3.6),
                               "heading": round(s[10] or 0), "squawk": s[14] or "", "direction": bearing(lat, lon, s[6], s[5])})
            except (TypeError, IndexError):
                continue
        nearby.sort(key=lambda f: f["km"])
        snapshot["flights"] = {"count": len(nearby), "source": "God's Eye /api/flights", "nearest": nearby[:8],
                               "low": [f for f in nearby if not f["on_ground"] and 0 < f["altitude_m"] < 1500][:6],
                               "emergencies": [f for f in nearby if f["squawk"] in SQUAWKS]}
        military = self.api("/api/military") or {}
        mil = []
        for a in military.get("ac") or []:
            if not isinstance(a.get("lat"), (int, float)) or not isinstance(a.get("lon"), (int, float)):
                continue
            km = distance(lat, lon, a["lat"], a["lon"])
            alt = a.get("alt_baro")
            alt_m = round(alt * 0.3048) if isinstance(alt, (int, float)) else 0
            emergency = (a.get("emergency") not in (None, "none")) or a.get("squawk") in SQUAWKS
            if km <= radius * 4 or emergency and km <= 500:
                mil.append({"callsign": (a.get("flight") or "").strip() or a.get("hex"), "type": a.get("t", ""), "km": round(km, 1),
                            "altitude_m": alt_m, "squawk": a.get("squawk", ""), "emergency": a.get("emergency", "none"),
                            "direction": bearing(lat, lon, a["lat"], a["lon"])})
        mil.sort(key=lambda a: a["km"])
        snapshot["military"] = {"count_near": sum(1 for a in mil if a["km"] <= radius), "worldwide": military.get("total"),
                                "nearest": mil[:6], "emergencies": [a for a in mil if a["squawk"] in SQUAWKS or a["emergency"] != "none"]}
        receiver = self.api("/api/local-receivers/aircraft") or {}
        if receiver.get("configured"):
            snapshot["local_receiver"] = {"aircraft": len(receiver.get("records") or []), "feeds": len(receiver.get("feeds") or [])}
        cyclones = self.api("/api/cyclones", timeout=25) or {}
        storms = []
        for storm in (cyclones.get("storms") or [])[:30]:
            points = [storm.get("position") or {}] + [p for p in (storm.get("forecastPoints") or []) if isinstance(p, dict)]
            near = None
            for point in points[:80]:
                plat = point.get("latitude", point.get("lat"))
                plon = point.get("longitude", point.get("lon"))
                if isinstance(plat, (int, float)) and isinstance(plon, (int, float)):
                    km = distance(lat, lon, plat, plon)
                    near = km if near is None else min(near, km)
            if near is not None:
                storms.append({"name": storm.get("name") or storm.get("id"), "closest_km": round(near),
                               "classification": storm.get("classification"), "wind_kt": storm.get("windKt")})
        snapshot["cyclones"] = {"tracked": len(storms), "near": [s for s in storms if s["closest_km"] <= 800],
                                "coverage": cyclones.get("coverage"), "unavailable": cyclones.get("unavailable")}
        fires = self.api("/api/fire-perimeters", timeout=25) or {}
        near_fires = []
        for row in fires.get("rows") or []:
            try:
                ring = row["polygons"][0][0]  # [[lon, lat], ...] of the first perimeter ring.
                flon = sum(pt[0] for pt in ring) / len(ring)
                flat = sum(pt[1] for pt in ring) / len(ring)
            except (KeyError, IndexError, TypeError, ZeroDivisionError):
                continue
            km = distance(lat, lon, flat, flon)
            if km <= radius * 2:
                near_fires.append({"name": row.get("name"), "km": round(km, 1), "containment": row.get("containedPct"),
                                   "acres": row.get("acres")})
        snapshot["fires"] = {"near": near_fires[:5], "source": "NIFC WFIGS perimeters (US coverage)"}
        effects = self.api("/api/weather-effects", {"latitude": round(lat, 3), "longitude": round(lon, 3)}) or {}
        snapshot["weather"] = effects.get("weather")
        brief = self.api("/api/regional-brief", {"latitude": round(lat, 3), "longitude": round(lon, 3)}, 25) or {}
        if brief:
            snapshot["regional_brief"] = {"place": (brief.get("place") or {}).get("label"),
                                          "headlines": [a.get("title", "")[:140] for a in (brief.get("articles") or [])[:5]],
                                          "news_source": brief.get("newsSource")}
        try:
            quakes = self.http.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson", timeout=(3, 15)).json()
            q = []
            for f in quakes.get("features", []):
                c = f["geometry"]["coordinates"]
                km = distance(lat, lon, c[1], c[0])
                if km <= 400:
                    q.append({"magnitude": f["properties"]["mag"], "km": round(km), "place": f["properties"].get("place")})
            snapshot["earthquakes"] = sorted(q, key=lambda x: x["km"])[:5]
        except (requests.RequestException, ValueError, KeyError):
            pass
        tomtom = self.api("/api/tomtom/status") or {}
        snapshot["traffic"] = {"available": bool(tomtom.get("hasKey")),
                               "note": "" if tomtom.get("hasKey") else "Live traffic needs a TomTom key in God's Eye settings."}
        with self.lock:
            self.cache = snapshot
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(snapshot, ensure_ascii=False, default=str), encoding="utf-8")
        except OSError:
            pass
        return snapshot

    def alerts(self, snapshot=None):
        snapshot = snapshot or self.cache
        found = []
        for f in (snapshot.get("flights") or {}).get("emergencies", []):
            found.append(("squawk:" + f["icao24"] + ":" + f["squawk"], "severe",
                          "Aircraft " + f["callsign"] + " is squawking " + f["squawk"] + " (" + SQUAWKS[f["squawk"]] + ") " +
                          str(f["km"]) + " km " + f["direction"] + " of you at " + str(f["altitude_m"]) + " m."))
        for a in (snapshot.get("military") or {}).get("emergencies", []):
            if a["km"] <= self.radius_km * 3:
                found.append(("mil-emergency:" + str(a["callsign"]), "severe",
                              "Military aircraft " + str(a["callsign"]) + " (" + str(a["type"]) + ") is declaring an emergency " +
                              str(a["km"]) + " km " + a["direction"] + " of you."))
        for a in (snapshot.get("military") or {}).get("nearest", []):
            if a["km"] <= 15 and 0 < a["altitude_m"] < 3000:
                found.append(("mil-low:" + str(a["callsign"]), "warning",
                              "Military aircraft " + str(a["callsign"]) + " (" + str(a["type"]) + ") is low overhead: " +
                              str(a["altitude_m"]) + " m, " + str(a["km"]) + " km " + a["direction"] + "."))
        for s in (snapshot.get("cyclones") or {}).get("near", []):
            if s["closest_km"] <= 400:
                found.append(("cyclone:" + str(s["name"]), "severe",
                              "Cyclone " + str(s["name"]) + "'s track passes within " + str(s["closest_km"]) + " km of you."))
        for f in (snapshot.get("fires") or {}).get("near", []):
            found.append(("fire:" + str(f["name"]), "warning", "Wildfire " + str(f["name"]) + " is " + str(f["km"]) + " km away" +
                          (" (" + str(f["containment"]) + "% contained)" if f.get("containment") is not None else "") + "."))
        return found

    def alert(self):
        now = self.clock()
        self.seen = {k: v for k, v in self.seen.items() if now - v < 6 * 3600}
        fresh = [a for a in self.alerts() if a[0] not in self.seen]
        for key, level, message in fresh[:3]:
            self.seen[key] = now
            self.actions.report("spoken_reply", "God's Eye alert: " + message)
            self.card("alert", message[:90], (self.cache.get("location") or {}).get("name", ""), "Severe" if level == "severe" else "Warning")
            memory = getattr(self.actions, "memory", None)
            if memory is not None:
                memory.record("God's Eye alert", message)
        return fresh

    def explain(self, question):
        """Answer 'why is it loud / sirens / what's overhead' from the side-thread cache (no web search)."""
        with self.lock:
            snapshot = dict(self.cache)
        if not snapshot or self.clock() - snapshot.get("at", 0) > 600:
            try:
                self.ensure_server()
                snapshot = self.poll()
            except Exception as exc:
                return "God's Eye data isn't available right now (" + str(exc)[:120] + "), so I can't check the sky or fires around you."
        if not snapshot:
            return "I don't know your location yet, so God's Eye can't check your area."
        lower = question.casefold()
        parts = []
        low = (snapshot.get("flights") or {}).get("low", [])
        nearest = (snapshot.get("flights") or {}).get("nearest", [])
        mil = [a for a in (snapshot.get("military") or {}).get("nearest", []) if a["km"] <= 30]
        if low:
            f = low[0]
            parts.append("there's low air traffic: " + f["callsign"] + " is " + str(f["km"]) + " km " + f["direction"] +
                         " of you at about " + str(f["altitude_m"]) + " m" + (" (" + str(len(low)) + " low aircraft in total)" if len(low) > 1 else ""))
        elif nearest and any(w in lower for w in ("plane", "aircraft", "jet", "loud", "noise", "sound", "overhead", "helicopter")):
            f = nearest[0]
            parts.append("the nearest aircraft is " + f["callsign"] + ", " + str(f["km"]) + " km " + f["direction"] + " at " +
                         str(f["altitude_m"]) + " m (" + str((snapshot.get("flights") or {}).get("count", 0)) + " within 40 km)")
        if mil:
            a = mil[0]
            parts.append("military aircraft " + str(a["callsign"]) + " (" + str(a["type"]) + ") is " + str(a["km"]) + " km " + a["direction"] +
                         (" at " + str(a["altitude_m"]) + " m" if a["altitude_m"] else ""))
        for a in (snapshot.get("flights") or {}).get("emergencies", []) + (snapshot.get("military") or {}).get("emergencies", [])[:1]:
            parts.append("an aircraft is squawking an emergency (" + str(a.get("squawk")) + ") " + str(a["km"]) + " km away")
        fires = (snapshot.get("fires") or {}).get("near", [])
        if fires:
            parts.append("a fire (" + str(fires[0]["name"]) + ") is " + str(fires[0]["km"]) + " km away")
        weather = snapshot.get("weather") or {}
        if isinstance(weather, dict):
            code = weather.get("weatherCode")
            if isinstance(code, (int, float)) and int(code) in {95, 96, 99}:
                parts.append("there's a thunderstorm overhead (" + str(weather.get("precipitationMm", 0)) + " mm rain)")
            elif isinstance(weather.get("windKph"), (int, float)) and weather["windKph"] >= 45 and any(w in lower for w in ("loud", "noise", "sound")):
                parts.append("it's very windy (" + str(round(weather["windKph"])) + " km/h)")
        quakes = [q for q in snapshot.get("earthquakes", []) if q["km"] <= 150]
        if quakes:
            parts.append("a magnitude " + str(quakes[0]["magnitude"]) + " earthquake hit " + str(quakes[0]["km"]) + " km away")
        if "siren" in lower and not fires:
            parts.append("God's Eye shows no fires or emergencies nearby" + ("" if (snapshot.get("traffic") or {}).get("available")
                                                                              else ", and live traffic isn't connected (no TomTom key), so a road incident can't be checked"))
        when = snapshot.get("at_local", "")
        place = (snapshot.get("location") or {}).get("name", "your area")
        if not parts:
            return ("God's Eye shows nothing unusual around " + place + " (as of " + when + "): " +
                    str((snapshot.get("flights") or {}).get("count", 0)) + " aircraft within 40 km, none low, no military nearby, "
                    "no fires or severe weather. The sound is probably local.")
        return "From God's Eye around " + place + " (as of " + when + "): " + "; ".join(parts) + "."

    def summary(self):
        """Compact cache summary for the multi-context situation."""
        with self.lock:
            s = dict(self.cache)
        if not s:
            return None
        return {"as_of": s.get("at_local"), "aircraft_within_40km": (s.get("flights") or {}).get("count"),
                "low_aircraft": [(f["callsign"], f["altitude_m"], f["km"]) for f in (s.get("flights") or {}).get("low", [])[:3]],
                "military_near": (s.get("military") or {}).get("count_near"),
                "alerts": [a[2][:120] for a in self.alerts(s)][:3]}


def stop_vite(source):
    """Stop the God's Eye dev server on port 4173, only if it is God's Eye's own vite process."""
    import psutil
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if "vite" in cmdline and "4173" in cmdline and Path(proc.info["cwd"] or "").resolve() == Path(source).resolve():
                proc.terminate()
                proc.wait(5)
        except (psutil.Error, OSError):
            continue


def execute(actions, command, cancelled):
    eye = getattr(actions, "gods_eye", None)
    if eye is None:
        return "God's Eye integration is off (gods_eye.enabled)."
    if command.kind == "gods_eye_show":
        return eye.show(json.loads(command.value or "{}"), cancelled)
    if command.kind == "gods_eye_explain":
        return eye.explain(command.value)
    if command.kind == "gods_eye_cameras":
        if command.value == "coverage":
            from .gods_eye_cameras import COVERAGE, pack_path
            try:
                data = json.loads(pack_path(actions.base).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = []
            toronto = sum(1 for c in data if c["id"].startswith("to-"))
            ontario = sum(1 for c in data if c["id"].startswith("on-"))
            return COVERAGE + " Loaded now: " + str(toronto) + " Toronto and " + str(ontario) + " Ontario 511 cameras."
        return eye.refresh_cameras(cancelled)
    if command.kind == "gods_eye_camera":
        return eye.camera(json.loads(command.value or "{}"), cancelled)
    if command.kind == "gods_eye_status":
        s = eye.summary()
        if not s:
            return "God's Eye hasn't collected data yet; it polls every minute once Jarvis has your location."
        with eye.lock:
            cache = dict(eye.cache)
        age = int(eye.clock() - cache.get("at", eye.clock()))
        radius = cache.get("radius_km", eye.options.get("radius_km", 40))
        text = ("God's Eye last polled at " + str(s["as_of"]) + " (" + (str(age) + " seconds" if age < 120 else str(age // 60) + " minutes") +
                " ago), watching " + str(radius) + " km around you: " + str(s["aircraft_within_40km"]) + " aircraft, " +
                str(s["military_near"]) + " military nearby" + (", alerts: " + "; ".join(s["alerts"]) if s["alerts"] else ", no alerts") + ".")
        text += (" Local SDR receiver: " + str(cache["local_receiver"]["aircraft"]) + " aircraft." if cache.get("local_receiver")
                 else " No local SDR receiver (RTL-SDR) is configured, so that layer stays empty.")
        if not (cache.get("traffic") or {}).get("available"):
            text += " Live traffic needs a TomTom key."
        if cache.get("error"):
            text += " Last error: " + str(cache["error"])[:120] + "."
        return text
    if command.kind == "gods_eye_update":
        from .gods_eye_update import update
        from .gods_eye_view import SOURCE
        result = update(SOURCE, actions.report, cancelled)
        return ("God's Eye View updated to " + result["commit"][:8] + " (" + result["date"][:10] + ")" +
                (", dependencies reinstalled" if result.get("dependencies_reinstalled") else "") + ". Restart Jarvis to load it."
                if result["updated"] else result["message"])
    raise ValueError("Unknown God's Eye command")
