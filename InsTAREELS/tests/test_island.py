import unittest
from unittest.mock import Mock

from jarvis.island import Morph, Island, render_island


class IslandTests(unittest.TestCase):
    def test_interrupted_morph_starts_at_current_size_and_settles(self):
        morph = Morph()
        morph.set_target((540,392), 10)
        middle = morph.sample(10.15)
        self.assertGreater(middle[0],208)
        self.assertLess(middle[0],540)
        morph.set_target((208,52),10.15)
        self.assertEqual(middle,morph.sample(10.15))
        self.assertEqual(morph.sample(11),(208,52))
        morph.set_target((540,392),12)
        self.assertEqual(morph.sample(12,reduced=True),(540,392))

    def test_idle_is_static_and_live_statuses_change(self):
        idle = render_island(phase=0)
        self.assertEqual(idle.tobytes(), render_island(phase=10).tobytes())
        self.assertEqual(idle.getpixel((0,0)),(255,0,255))
        speaking = render_island(300,60,'SPEAKING',1)
        self.assertNotEqual(speaking.tobytes(),render_island(300,60,'LISTENING',1,level=80).tobytes())

    def test_display_tick_never_reopens_during_capture(self):
        app=Mock()
        app.root.winfo_screenwidth.return_value=1920
        app.root.winfo_screenheight.return_value=1080
        app.root.state.return_value='normal'
        app.config={'ui':{'reduced_motion':True}}
        app.capture_count=1
        island=Island(app,Mock())
        island.expand(True)
        from unittest.mock import patch
        with patch('jarvis.island.ImageTk.PhotoImage'):
            island.tick('THINKING')
            app.panel.deiconify.assert_not_called()
            app.capture_count=0
            app.panel.state.return_value='withdrawn'
            island.tick('THINKING')
            app.panel.deiconify.assert_called_once()
        island.notify('answer','A real result')
        self.assertGreater(island.message_until,0)
        island.expand(False)
        self.assertEqual(island.message_until,0)

