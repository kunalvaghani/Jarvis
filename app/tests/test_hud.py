from pathlib import Path
import gc
import tempfile
import unittest
from unittest.mock import patch, Mock
import tkinter as tk

from jarvis.hud import logo_frames, render_hud
from jarvis.interface import build_interface
from jarvis.display import window_scale


class HudTests(unittest.TestCase):
    def tearDown(self):
        logo_frames.cache_clear()

    def test_missing_and_damaged_artwork_use_emblem_without_retrying(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "damaged.gif"
            for damaged in (False, True):
                if damaged:
                    path.write_bytes(b"not an image")
                logo_frames.cache_clear()
                with patch("jarvis.hud.ASSET", path):
                    image = render_hud(size=128, active=True)
                    self.assertEqual(image.size, (128, 128))
                    self.assertEqual(logo_frames(107), ())

    def test_bundled_logo_animates_with_distinct_speaking_status(self):
        standby = render_hud(size=128)
        self.assertGreater(len(logo_frames(107)), 1)
        self.assertNotEqual(standby.tobytes(), render_hud(active=True, size=128).tobytes())
        self.assertNotEqual(standby.tobytes(), render_hud(speaking=True, size=128).tobytes())


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Production keeps one Tcl interpreter. Repeated interpreter teardown
        # intermittently fails Tk's own script loading on this Windows host.
        # Exercise one interface instance, as the actual app does; layout cases
        # set their own inputs and handler call counts are reset between cases.
        cls.interface_root = tk.Tk()
        cls.interface_root.withdraw()
        cls.interface_app = Mock()
        cls.interface_app.root = cls.interface_root
        cls.interface_app.config = {"whisper": {"model": "test"}, "knowledge": {"answer_language": "en"}}
        cls.interface_app.speech.options = {"enabled": True}
        build_interface(cls.interface_app)
        cls.interface_root.update_idletasks()
        cls.initial_panel_state = cls.interface_app.panel.state()

    @classmethod
    def tearDownClass(cls):
        cls.interface_app.island.close()
        cls.interface_root.destroy()
        cls.interface_app = None
        cls.interface_root = None
        gc.collect()

    def setUp(self):
        self.root = self.interface_root
        self.root.withdraw()
        self.addCleanup(self.close_interface)
        self.app = self.interface_app
        self.app.reset_mock()
        self.app.panel.withdraw()
        self.app.live.set('')
        self.app.question.set('')
        self.root.update_idletasks()

    def close_interface(self):
        self.app.panel.withdraw()
        self.app = None
        self.root = None

    def buttons(self, parent):
        for child in parent.winfo_children():
            if child.winfo_class() == "TButton":
                yield child
            yield from self.buttons(child)

    def test_controls_preserve_handlers_and_initially_hide_panel(self):
        self.assertEqual(self.initial_panel_state, "withdrawn")
        self.assertEqual(self.app.panel.state(), "withdrawn")
        controls = {button.cget("text"): button for button in self.buttons(self.app.panel)}
        for text, handler in (("Start listening", self.app.toggle_listening), ("Stop tasks", self.app.stop),
                              ("Stop voice", self.app.speech.cancel), ("Ask", self.app.ask_question),
                              ("Ask screen", self.app.ask_screen), ("Do task", self.app.do_task),
                              ("Quit Jarvis", self.app.close)):
            controls[text].invoke()
            handler.assert_called_once()

    def test_primary_controls_remain_accessible_at_small_window_size(self):
        self.app.panel.geometry("660x620+20000+20000")
        self.app.panel.deiconify()
        self.root.update()
        for button in self.buttons(self.app.panel):
            if button.winfo_ismapped():
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                     self.app.panel.winfo_rooty() + self.app.panel.winfo_height(), button.cget("text"))
        self.assertTrue(self.app.preview.winfo_ismapped())

    def test_compact_island_controls_fit_with_long_response_and_question(self):
        scale = window_scale(self.root)
        self.app.panel.geometry(f"{round(500*scale)}x{round(316*scale)}+20000+20000")
        self.app.live.set("A long response with project details. " * 50)
        self.app.question.set("Which project folder do you mean? " * 50)
        self.app.panel.deiconify()
        self.root.update()
        for button in self.buttons(self.app.panel):
            if button.winfo_ismapped():
                self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                                     self.app.panel.winfo_rooty()+self.app.panel.winfo_height(),button.cget("text"))
        self.assertTrue(self.app.preview.winfo_ismapped())
