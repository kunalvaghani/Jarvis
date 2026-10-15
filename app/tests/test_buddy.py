import itertools
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from jarvis import buddy_engine as be
from jarvis.island_buddy import EMOTIONS, mood_for, paint, pose_for


def render(emotion, t=1.37, look=None, outfit=()):
    image = Image.new("RGB", (120, 120))
    paint(image, 60, 64, 52, pose_for(emotion, t, look, outfit), 1)
    return image


class Looks(unittest.TestCase):
    def test_every_emotion_has_its_own_look(self):
        self.assertGreaterEqual(len(EMOTIONS), 30)
        images = {name: render(name).tobytes() for name in EMOTIONS}
        same = [(a, b) for a, b in itertools.combinations(images, 2) if images[a] == images[b]]
        self.assertEqual(same, [])

    def test_animations_move(self):
        for name in EMOTIONS:
            frames = {render(name, t).tobytes() for t in (0.1, 0.6, 1.3, 2.2)}
            self.assertGreater(len(frames), 1, name)  # Every emotion is animated, not a still face.

    def test_eyes_follow_the_pointer_and_outfits_draw(self):
        self.assertNotEqual(render("idle", look=(-1, 0)).tobytes(), render("idle", look=(1, 0)).tobytes())
        plain = render("idle").tobytes()
        for item in ("glasses", "sunglasses", "headphones", "beanie", "santa", "witch", "party", "crown", "bow"):
            self.assertNotEqual(render("idle", outfit=[item]).tobytes(), plain, item)

    def test_card_phases(self):
        self.assertEqual((mood_for("eating"), mood_for("ready"), mood_for("sent"), mood_for("error")),
                         ("eating", "question", "finished", "sad"))


class Brain(unittest.TestCase):
    def setUp(self):
        # Resting moods depend on local hour. These tests exercise daytime
        # behavior; dedicated night/outfit tests override this fixed clock.
        calendar = patch('jarvis.buddy_engine.datetime')
        self.addCleanup(calendar.stop)
        calendar.start().now.return_value = datetime(2026,10,14,15,0)
        self.clock = [100.0]
        self.pip = be.Buddy(sense=False, clock=lambda: self.clock[0])

    def step(self, seconds=.1, **signals):
        self.clock[0] += seconds
        return self.pip.update(self.clock[0], **signals)[0]

    def test_hello_then_rest(self):
        self.assertEqual(self.step(), "greeting")
        self.assertEqual(self.step(3.5), "idle")

    def test_mouse_reactions(self):
        self.step(3.5)
        self.assertEqual(self.pip.poke(), "boop")
        self.assertEqual(self.step(), "surprised")
        self.assertEqual(self.step(.7), "laughing")
        for _ in range(4):
            self.pip.poke()
        self.assertEqual(self.step(), "dizzy")
        for _ in range(4):
            self.pip.poke()
        self.assertEqual(self.step(), "ouch")
        self.step(4)
        self.pip.pet()
        self.assertEqual(self.step(), "love")
        self.step(4)
        self.pip.drag()
        self.assertEqual(self.step(), "whee")
        self.step(2)
        self.pip.hover()
        self.assertEqual(self.step(), "curious")

    def test_files(self):
        self.step(3.5)
        self.pip.file_over()
        self.assertEqual(self.step(), "hungry")
        self.pip.dropped()
        self.assertEqual(self.step(), "eating")
        self.step(3)
        self.assertEqual(self.step(card_phase="ready"), "question")
        self.assertEqual(self.step(card_phase="sent"), "finished")

    def test_jarvis_states_and_events(self):
        # This checks media/event priority. Random idle dancing is a separate
        # allowed fidget and must not make the paused-media assertion flaky.
        self.pip.next_fidget = float('inf')
        self.step(3.5)
        self.assertEqual(self.step(approval=True), "approval")
        self.assertEqual(self.step(question=True), "question")
        self.assertEqual(self.step(speaking=True), "talking")
        self.assertEqual(self.step(status="THINKING"), "thinking")
        self.assertEqual(self.step(status="WORKING"), "working")
        self.pip.event("warning", "Something failed")
        self.assertEqual(self.step(), "error")
        self.step(4)
        self.pip.event("action", "Created notes.txt")
        self.assertEqual(self.step(), "finished")
        self.step(3)
        self.pip.event("media_card", {"service": "whatsapp", "phase": "message"})
        self.assertEqual(self.step(), "surprised")
        self.step(3)
        self.pip.event("media_card", {"service": "github", "phase": "learned"})
        self.assertEqual(self.step(), "proud")
        self.step(5)
        self.pip.event("media_card", {"service": "spotify", "phase": "playing"})
        self.assertEqual(self.step(), "dancing")
        self.assertIn("headphones", self.pip.update(self.clock[0])[1]["outfit"])
        self.pip.event("media_card", {"service": "spotify", "phase": "paused"})
        self.assertEqual(self.pip.music_until, 0.)
        self.assertNotEqual(self.step(), "dancing")

    def test_what_you_are_doing(self):
        self.step(3.5)
        self.assertEqual(be.categorize("Code.exe", "app.py - Jarvis - Visual Studio Code"), "code")
        self.assertEqual(be.categorize("chrome.exe", "Funny cats - YouTube - Google Chrome"), "video")
        self.assertEqual(be.categorize("chrome.exe", "Instagram • Messages - Google Chrome"), "chat")
        self.assertEqual(be.categorize("Spotify.exe", ""), "music")
        self.assertEqual(be.categorize("chrome.exe", "Google"), "browser")
        for context, emotion in (("code", "focused"), ("video", "watching"), ("chat", "chatty"), ("docs", "reading"),
                                 ("music", "dancing")):
            self.pip.context = context
            self.assertEqual(self.step(), emotion, context)
        self.pip.context = "code"
        self.assertIn("glasses", self.pip.update(self.clock[0])[1]["outfit"])

    def test_idle_sleep_and_welcome_back(self):
        self.step(3.5)
        with patch("jarvis.buddy_engine.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 12, 15, 0)
            self.pip.idle = 400
            self.assertEqual(self.step(), "bored")
            self.pip.idle = 1000
            self.assertEqual(self.step(), "sleeping")
        self.pip.sense = True
        with patch("jarvis.buddy_engine.idle_seconds", return_value=0.5), \
                patch("jarvis.buddy_engine.foreground", return_value=("explorer.exe", "")):
            self.pip.was_away = True
            self.pip.next_sense = 0
            self.assertEqual(self.step(), "greeting")  # Welcome back.

    def test_its_own_mood_and_fidgets(self):
        self.step(3.5)
        self.pip.next_fidget = self.clock[0]
        fidget = self.step()
        self.assertIn(fidget, be.FIDGETS + ["yawn", "curious", "wink"])
        self.step(5)
        self.pip.affection = 1.
        self.pip.next_fidget = self.clock[0] + 99
        moods = {self.step(2) for _ in range(12)}
        self.assertIn("shy", moods)  # Very fond of you: it gets shy now and then (and wears a bow).

    def test_outfits_follow_the_date(self):
        with patch("jarvis.buddy_engine.datetime") as clock:
            clock.now.return_value = datetime(2026, 12, 20, 15, 0)
            self.assertIn("santa", self.pip.outfit("idle", False))
            clock.now.return_value = datetime(2026, 10, 30, 15, 0)
            self.assertIn("witch", self.pip.outfit("idle", False))
            clock.now.return_value = datetime(2026, 10, 12, 23, 30)
            self.assertIn("beanie", self.pip.outfit("sleeping", True))

    def test_look_at_is_bounded(self):
        self.assertEqual(be.look_at((5000, 5000), (100, 0))[0], 1.)
        self.assertLess(be.look_at((0, 0), (900, 20))[0], 0)


class InTheIsland(unittest.TestCase):
    def island(self):
        from jarvis.island import Island
        app = Mock()
        app.root.winfo_screenwidth.return_value = 1920
        app.root.winfo_screenheight.return_value = 1080
        app.root.winfo_rootx.return_value = 760
        app.root.winfo_rooty.return_value = 0
        app.root.state.return_value = "normal"
        app.config = {"ui": {"reduced_motion": False, "buddy": True}, "_ui_verification": True}
        app.capture_count = 0
        app.desk = SimpleNamespace(view="Overview", has_reply=False, work={"active": False}, reply="", approvals=[])
        app.actions = SimpleNamespace(whatsapp_prompts=[])
        with patch("jarvis.island.window_scale", return_value=1.0):
            island = Island(app, Mock())
        return island, app

    def test_clicking_pip_boops_and_elsewhere_opens_the_panel(self):
        island, app = self.island()
        with patch("jarvis.island.window_scale", return_value=1.0):
            island.press(SimpleNamespace(x_root=820, y_root=20))
            island.release(SimpleNamespace(x=59, y=20))
            app.toggle_panel.assert_not_called()
            self.assertEqual(island.pip.events[-1][1], "poke")
            island.press(SimpleNamespace(x_root=1000, y_root=20))
            island.release(SimpleNamespace(x=250, y=20))
            app.toggle_panel.assert_called_once()
            island.double_click(SimpleNamespace(x=60, y=18))
            self.assertEqual(island.pip.events[-1][1], "pet")
            island.pointer(SimpleNamespace(x=300, y=20))
            self.assertEqual(island.pip.events[-1][1], "pet")  # Hovering away from Pip does nothing.

    def test_ticks_draw_pip_and_jarvis_events_reach_it(self):
        island, _ = self.island()
        island.notify("warning", "Something failed")
        with patch("jarvis.island.ImageTk.PhotoImage"), patch("jarvis.island.window_scale", return_value=1.0):
            island.tick("STANDBY")
            self.assertEqual(island.emotion, "error")
            island.tick("THINKING")
        self.assertIsNotNone(island.preview_image)


if __name__ == "__main__":
    unittest.main()
