import unittest
from youtube_connector import normalize_playlist, video_url
class Core(unittest.TestCase):
    def test_existing_url(self):
        self.assertEqual(video_url("v1"), "https://www.youtube.com/watch?v=v1")
    def test_missing_playlist(self):
        self.assertEqual(normalize_playlist(None), [])
    def test_valid_items_preserve_order_without_duplicates(self):
        self.assertEqual(normalize_playlist([{"id":"v1"}, {}, {"id":"v2"}, {"id":"v1"}, {"id":""}, None,
            {"id":None}, {"id":123}, {"id":[]}, {"id":"  "}]), ["v1", "v2"])
