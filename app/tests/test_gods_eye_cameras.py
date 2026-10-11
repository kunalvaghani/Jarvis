import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis import gods_eye_cameras as gc
from jarvis.commands import parse

TORONTO = {"features": [
    {"properties": {"REC_ID": 8001, "IMAGEURL": "https://opendata.toronto.ca/x/loc8001.jpg", "MAINROAD": "YORK ST",
                    "CROSSROAD": "BREMNER BLVD"}, "geometry": {"type": "MultiPoint", "coordinates": [[-79.3826, 43.6426]]}},
    {"properties": {"REC_ID": 8002, "IMAGEURL": "http://insecure/loc.jpg"}, "geometry": {"type": "Point", "coordinates": [-79.4, 43.7]}},
]}
ONTARIO = [{"Id": 42, "Latitude": 43.69, "Longitude": -79.76, "Location": "Highway 410 at Queen St", "Direction": "Northbound",
            "Views": [{"Url": "/map/Cctv/2898", "Status": "Enabled", "Description": ""}]},
           {"Id": 43, "Latitude": 43.6, "Longitude": -79.6, "Views": [{"Url": "/map/Cctv/1", "Status": "Disabled"}]}]


def http(ontario_rows=ONTARIO):
    def get(url, params=None, timeout=None):
        return Mock(json=lambda: TORONTO if "toronto" in url else ontario_rows)
    return SimpleNamespace(get=Mock(side_effect=get))


class CameraPackTests(unittest.TestCase):
    def setUp(self):
        self.base, self.root = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (self.root / ".env").write_text("GOOGLE_MAPS_API_KEY=keep-me\nCCTV_MAX_SOURCES=100\n", encoding="utf-8")

    def test_toronto_without_key_and_env_keeps_your_lines(self):
        client = http()
        result = gc.build(self.base, self.root, client, force=True)
        self.assertEqual((result["toronto"], result["ontario"]), (1, 0))  # The http:// row is skipped.
        camera = json.loads(gc.pack_path(self.base).read_text(encoding="utf-8"))[0]
        self.assertEqual((camera["id"], camera["name"], camera["lat"]), ("to-8001", "York St at Bremner Blvd", 43.6426))
        env = (self.root / ".env").read_text(encoding="utf-8")
        self.assertIn("GOOGLE_MAPS_API_KEY=keep-me", env)
        self.assertIn("CCTV_FORCE_AUSTIN=1", env)  # God's Eye's own live packs stay on.
        self.assertIn("CCTV_MAX_SOURCES=5000", env)
        self.assertNotIn("CCTV_MAX_SOURCES=100", env)
        self.assertIn("CCTV_SOURCES_FILE=" + str(gc.pack_path(self.base)).replace("\\", "/"), env)
        self.assertEqual(client.get.call_count, 1)  # No key: Ontario 511 isn't called.
        self.assertIn("511on.ca", gc.summary(result, False))

    def test_ontario_with_key(self):
        (self.base / "secrets").mkdir()
        (self.base / "secrets" / "ontario511.json").write_text('{"api_key": "abc"}', encoding="utf-8")
        client = http()
        result = gc.build(self.base, self.root, client, force=True)
        self.assertEqual(result["ontario"], 1)
        args = client.get.call_args_list[1]
        self.assertEqual(args.kwargs["params"]["key"], "abc")
        camera = [c for c in json.loads(gc.pack_path(self.base).read_text(encoding="utf-8")) if c["id"] == "on-42"][0]
        self.assertEqual((camera["url"], camera["headingDeg"]), ("https://511on.ca/map/Cctv/2898", 0))
        refused = gc.build(self.base, self.root, http({"Message": "Invalid Key"}), force=True)
        self.assertIn("refused the key", refused["errors"][0])

    def test_cached_pack_is_reused_and_kept_when_offline(self):
        gc.build(self.base, self.root, http(), force=True)
        self.assertTrue(gc.build(self.base, self.root, http())["cached"])
        broken = SimpleNamespace(get=Mock(side_effect=OSError("offline")))
        result = gc.build(self.base, self.root, broken, force=True)
        self.assertTrue(result["cached"])
        self.assertEqual(len(json.loads(gc.pack_path(self.base).read_text(encoding="utf-8"))), 1)

    def test_phrasings(self):
        self.assertEqual(parse("Why can't I see any CCTV in Toronto, Canada or in India?").value, "coverage")
        self.assertEqual(parse("Add cameras for Mississauga and Brampton").value, "refresh")
        self.assertEqual(parse("Refresh God's Eye cameras").kind, "gods_eye_cameras")
        self.assertEqual(json.loads(parse("Show traffic cameras in Toronto").value)["layers"], ["cctv"])


if __name__ == "__main__":
    unittest.main()
