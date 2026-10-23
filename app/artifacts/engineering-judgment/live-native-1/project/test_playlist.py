import unittest
from youtube_connector import playlist_title
class Playlist(unittest.TestCase):
    def test_missing_title(self):
        self.assertEqual(playlist_title(None), "Untitled")
        self.assertEqual(playlist_title({}), "Untitled")
    def test_valid_title(self):
        self.assertEqual(playlist_title({"title":" Mix "}), "Mix")
