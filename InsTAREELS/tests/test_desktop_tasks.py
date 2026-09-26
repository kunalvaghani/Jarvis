import tempfile
import unittest
from pathlib import Path

from jarvis.browser import music_search_url
from jarvis.commands import Command, parse
from jarvis.desktop_tasks import write_new_file
from jarvis.engine import Engine


class DesktopTaskTests(unittest.TestCase):
    def test_compound_folder_file_instruction_stays_one_task(self):
        sent = []
        engine = Engine(sent.append, lambda *_: None)
        engine.activate()
        utterance = "open folder Downloads and create a file called ideas dot txt and write hello kunal"
        engine.feed(utterance)
        self.assertEqual(sent, [])
        engine.feed(utterance, final=True)
        self.assertEqual(sent, [Command("task", utterance)])

    def test_media_and_close_commands(self):
        self.assertEqual(parse("play my playlist on spotify"), Command("play_media", "my playlist", "spotify"))
        self.assertEqual(parse("play jazz on youtube"), Command("play_media", "jazz", "youtube"))
        self.assertEqual(parse("close chrome"), Command("close_app", "chrome"))
        self.assertEqual(parse("close"), Command("close_app", "this app"))
        self.assertEqual(parse("click close"), Command("click_control", "close", "click"))

    def test_music_urls(self):
        self.assertEqual(music_search_url("blue sky", "youtube"),
                         "https://www.youtube.com/results?search_query=blue+sky")
        self.assertEqual(music_search_url("blue sky", "spotify"),
                         "https://open.spotify.com/search/blue%20sky")

    def test_file_writes_exact_content_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_new_file(directory, "ideas dot txt", "my name is Kunal")
            self.assertEqual(path, Path(directory) / "ideas.txt")
            self.assertEqual(path.read_text(encoding="utf-8"), "my name is Kunal")
            with self.assertRaises(FileExistsError):
                write_new_file(directory, "ideas.txt", "different")
            self.assertEqual(path.read_text(encoding="utf-8"), "my name is Kunal")
            with self.assertRaises(ValueError):
                write_new_file(directory, "../outside.txt", "bad")


if __name__ == "__main__":
    unittest.main()
