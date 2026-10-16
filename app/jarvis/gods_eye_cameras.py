"""Extra live traffic cameras for God's Eye View: Toronto (keyless) and Ontario 511 (with your free key).

God's Eye ships camera packs for London, Austin, Calgary, British Columbia, Finland, Norway and a few others.
Its own Ontario 511 pack stopped working when 511on.ca started requiring a developer key for its camera list,
which left Toronto, Mississauga and Brampton empty. This module builds a camera pack God's Eye already knows
how to read (CCTV_SOURCES_FILE) from:

- City of Toronto open data: 336 intersection cameras, refreshed every few minutes, no key.
- Ontario 511's official API, when you save a free developer key in secrets/ontario511.json
  ({"api_key": "..."}) or the ONTARIO_511_API_KEY environment variable. That adds the 400-series highway
  cameras through Toronto, Mississauga, Brampton and the rest of Ontario.

The pack lives under .jarvis-runtime (outside God's Eye's source, so "update God's Eye" keeps it) and God's Eye's
own .env points at it. Live packs stay on (CCTV_FORCE_AUSTIN=1), so nothing God's Eye already shows is lost.
"""
import json
import os
import re
import time
import zlib
from urllib.parse import urlsplit
from pathlib import Path

TORONTO_URL = ("https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/a3309088-5fd4-4d34-8297-77c8301840ac/resource/"
               "4a568300-c7f8-496d-b150-dff6f5dc6d4f/download/traffic-camera-list-4326.geojson")
ONTARIO_URL = "https://511on.ca/api/v2/get/cameras"
ONTARIO_ORIGIN = "https://511on.ca"
MAX_AGE = 24 * 3600
ENV_KEYS = {"CCTV_FORCE_AUSTIN": "1", "CCTV_MAX_SOURCES": "5000", "CCTV_ONTARIO_ENABLED": "0"}


def public_camera(url,hosts):
    try:
        parsed=urlsplit(url)
        return parsed.scheme=='https' and parsed.hostname in hosts and not parsed.username and not parsed.password and parsed.port in (None,443)
    except ValueError: return False


def pack_path(base):
    return Path(base) / ".jarvis-runtime" / "gods-eye" / "cctv_sources.jarvis.json"


def ontario_key(base):
    key = os.environ.get("ONTARIO_511_API_KEY", "").strip()
    if key:
        return key
    try:
        return json.loads((Path(base) / "secrets" / "ontario511.json").read_text(encoding="utf-8")).get("api_key", "").strip()
    except (OSError, ValueError):
        return ""


def _heading(camera_id):
    return zlib.crc32(camera_id.encode()) % 360  # A stable guess when the feed gives no direction.


def _point(geometry):
    coords = (geometry or {}).get("coordinates")
    while isinstance(coords, list) and coords and isinstance(coords[0], list):
        coords = coords[0]  # MultiPoint -> first point.
    if isinstance(coords, list) and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    return None


def toronto(http):
    rows = http.get(TORONTO_URL, timeout=(5, 40)).json().get("features") or []
    cameras = []
    for row in rows:
        props, point = row.get("properties") or {}, _point(row.get("geometry"))
        url = str(props.get("IMAGEURL") or "").strip()
        if not point or not public_camera(url,{'opendata.toronto.ca'}):
            continue
        camera_id = "to-" + str(props.get("REC_ID") or props.get("_id"))
        name = " at ".join(x.title() for x in (str(props.get("MAINROAD") or "").strip(), str(props.get("CROSSROAD") or "").strip()) if x)
        cameras.append({"id": camera_id, "name": name or "Toronto camera " + camera_id[3:], "city": "Toronto", "cityId": "toronto",
                        "provider": "City of Toronto", "lat": point[0], "lon": point[1], "headingDeg": _heading(camera_id),
                        "headingConfidence": "low", "pitchDeg": -18, "fovDeg": 44, "rangeM": 145, "mountHeightM": 8,
                        "groundElevationM": 110, "feedType": "image", "url": url, "snapshotUrl": url,
                        "sourceKind": "toronto-open-data", "license": "Open Government Licence - Toronto"})
    return cameras


DIRECTIONS = {"north": 0, "northbound": 0, "east": 90, "eastbound": 90, "south": 180, "southbound": 180, "west": 270, "westbound": 270}


def ontario(http, key):
    rows = http.get(ONTARIO_URL, params={"key": key, "format": "json", "lang": "en"}, timeout=(5, 60)).json()
    if not isinstance(rows, list):
        raise ValueError("Ontario 511 refused the key or returned an invalid camera list")
    cameras = []
    for row in rows:
        lat, lon = row.get("Latitude"), row.get("Longitude")
        views = [v for v in row.get("Views") or [] if str(v.get("Status", "")).lower() == "enabled" and v.get("Url")]
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not views:
            continue
        view = next((v for v in views if not re.search(r"\bdown\b", str(v.get("Description", "")), re.I)), views[0])
        url = str(view["Url"])
        url = url if url.startswith("http") else ONTARIO_ORIGIN + "/" + url.lstrip("/")
        if not public_camera(url,{'511on.ca'}): continue
        camera_id = "on-" + str(row.get("Id"))
        direction = DIRECTIONS.get(str(row.get("Direction") or "").strip().lower())
        place = str(row.get("Location") or row.get("Roadway") or "Ontario 511 camera").strip()
        cameras.append({"id": camera_id, "name": place, "city": place, "cityId": "ontario", "provider": "Ontario 511",
                        "lat": float(lat), "lon": float(lon), "headingDeg": direction if direction is not None else _heading(camera_id),
                        "headingConfidence": "high" if direction is not None else "low", "pitchDeg": -24, "fovDeg": 56,
                        "rangeM": 210, "mountHeightM": 10, "groundElevationM": 200, "feedType": "image", "url": url,
                        "snapshotUrl": url, "sourceKind": "ontario-511-api", "license": "Open Government Licence - Ontario"})
    return cameras


def configure_env(root, path):
    """Point God's Eye's .env at the pack; other lines (your keys) are kept as they are."""
    env = Path(root) / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    wanted = {"CCTV_SOURCES_FILE": str(path).replace("\\", "/"), **ENV_KEYS}
    kept = [line for line in lines if line.split("=", 1)[0].strip() not in wanted]
    new = kept + [key + "=" + value for key, value in wanted.items()]
    changed = new != lines
    if changed:
        env.write_text("\n".join(new) + "\n", encoding="utf-8")
    return changed


def build(base, root, http=None, force=False):
    """Write the pack and configure God's Eye. Returns {"toronto", "ontario", "changed", "path", "errors"}."""
    import requests
    http = http or requests
    path = pack_path(base)
    if not force and path.exists() and time.time() - path.stat().st_mtime < MAX_AGE:
        data = json.loads(path.read_text(encoding="utf-8"))
        counts = {"toronto": sum(1 for c in data if c["id"].startswith("to-")), "ontario": sum(1 for c in data if c["id"].startswith("on-"))}
        return {**counts, "changed": configure_env(root, path), "path": str(path), "errors": [], "cached": True}
    cameras, errors, counts = [], [], {"toronto": 0, "ontario": 0}
    try:
        found = toronto(http)
        cameras += found
        counts["toronto"] = len(found)
    except Exception as exc:
        errors.append("Toronto open data: " + str(exc)[:120])
    key = ontario_key(base)
    if key:
        try:
            found = ontario(http, key)
            cameras += found
            counts["ontario"] = len(found)
        except Exception as exc:
            errors.append("Ontario 511: " + str(exc)[:120])
    if not cameras and path.exists():
        return {**counts, "changed": configure_env(root, path), "path": str(path), "errors": errors, "cached": True}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(cameras, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return {**counts, "changed": configure_env(root, path), "path": str(path), "errors": errors, "cached": False}


COVERAGE = ("God's Eye's live camera catalogue covers London, Austin and parts of Texas, California, Calgary, British "
            "Columbia, Delaware, New South Wales, Finland, Estonia and Norway. Toronto comes from City of Toronto open data "
            "(336 intersection cameras, still frames refreshed every few minutes). Mississauga and Brampton have no city "
            "camera feeds; their cameras are Ontario 511's highway cameras, which need a free Ontario 511 developer key "
            "saved in secrets/ontario511.json. India has no public live traffic-camera feed that can be used, so no Indian "
            "city has cameras in God's Eye. These are traffic cameras, not private CCTV.")


def summary(result, key_set):
    parts = [str(result["toronto"]) + " Toronto cameras"]
    if key_set:
        parts.append(str(result["ontario"]) + " Ontario 511 highway cameras")
    text = "God's Eye camera pack ready: " + " and ".join(parts) + "."
    if not key_set:
        text += (" Mississauga and Brampton need Ontario 511: sign up free at 511on.ca, request a developer key, and save it "
                 "in secrets/ontario511.json as {\"api_key\": \"...\"}; then say 'refresh God's Eye cameras'.")
    if result["errors"]:
        text += " Problems: " + "; ".join(result["errors"]) + "."
    return text
