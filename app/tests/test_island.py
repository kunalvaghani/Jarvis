import unittest
from unittest.mock import Mock
from types import SimpleNamespace

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
        self.assertEqual(idle.getpixel((0,idle.height-1)),(255,0,255))
        self.assertEqual(idle.getpixel((idle.width//2,0)),(0,0,0))
        speaking = render_island(300,60,'SPEAKING',1)
        self.assertNotEqual(speaking.tobytes(),render_island(300,60,'LISTENING',1,level=80).tobytes())

    def test_display_tick_never_reopens_during_capture(self):
        app=Mock()
        app.root.winfo_screenwidth.return_value=1920
        app.root.winfo_screenheight.return_value=1080
        app.root.state.return_value='normal'
        app.config={'ui':{'reduced_motion':True}}
        app.capture_count=1
        app.desk=SimpleNamespace(view='Overview',has_reply=False,work={'active':False},reply='')
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

    def test_content_height_grows_and_features_keep_a_scrollable_workspace(self):
        app=Mock()
        app.root.winfo_screenwidth.return_value=1920
        app.desk=SimpleNamespace(view='Overview',has_reply=False,work={'active':False},reply='')
        island=Island(app,Mock())
        island.expanded=True
        compact,workspace,_=island.layout_target('', '', 'STANDBY', 1000, 900)
        self.assertFalse(workspace)
        app.desk.has_reply=True
        app.desk.reply='A useful answer.\n'*100
        tall,workspace,_=island.layout_target('', '', 'STANDBY', 1000, 900)
        self.assertTrue(workspace)
        self.assertGreater(tall[1],compact[1])
        app.desk.view='Games'
        small,_,_=island.layout_target('', '', 'STANDBY', 420, 480)
        self.assertEqual(small,(420,480))

    def test_action_results_return_to_the_notch_without_stealing_focus(self):
        app=Mock()
        app.root.winfo_screenwidth.return_value=1920
        app.desk=SimpleNamespace(view='Overview',has_reply=True,work={'active':False},reply='Created calculator.py')
        island=Island(app,Mock())
        island.notify('action','Created calculator.py')
        self.assertGreater(island.message_until,0)
        target,workspace,opened=island.layout_target(island.message,'','STANDBY',1000,900)
        self.assertTrue(opened and workspace)
        self.assertGreater(target[1],144)
        self.assertFalse(island.focus_pending)

    def test_stream_stays_open_during_token_gaps_and_keeps_growth_on_draft_reset(self):
        app = Mock()
        app.root.winfo_screenwidth.return_value = 1920
        app.desk = SimpleNamespace(view='Overview', has_reply=True, work={'active': False}, reply='')
        island = Island(app, Mock())
        island.notify('answer_stream', {'phase': 'Generating answer', 'text': 'first'})
        # Simulate the short-lived header message expiring while inference is alive.
        app.desk.reply = 'line\n'*40
        tall, _, opened = island.layout_target('', '', 'WORKING', 1000, 900)
        self.assertTrue(opened)
        app.desk.reply = ''
        island.notify('answer_stream', {'phase': 'Verifying online', 'text': ''})
        replacement, _, opened = island.layout_target('', '', 'WORKING', 1000, 900)
        self.assertEqual(replacement, tall)
        self.assertTrue(opened)
        island.notify('answer', 'Shorter final result')
        self.assertEqual(island.layout_target('Final result', '', 'STANDBY', 1000, 900)[0], tall)

    def test_user_collapse_wins_over_later_stream_tokens(self):
        app = Mock()
        app.root.winfo_screenwidth.return_value = 1920
        app.desk = SimpleNamespace(view='Overview', has_reply=True, work={'active': False}, reply='text')
        island = Island(app, Mock())
        island.notify('answer_stream', {'phase': 'Generating answer', 'text': 'text'})
        island.expand(False)
        island.notify('answer_stream', {'phase': 'Generating answer', 'text': 'text more'})
        self.assertFalse(island.layout_target('text more', '', 'WORKING', 1000, 900)[2])
        island.notify('answer', 'Final text')
        self.assertFalse(island.layout_target('Final text', '', 'STANDBY', 1000, 900)[2])
        island.notify('answer', 'A fresh quick answer')
        self.assertTrue(island.layout_target('A fresh quick answer', '', 'STANDBY', 1000, 900)[2])
        island.expand(True)
        self.assertTrue(island.layout_target('', '', 'WORKING', 1000, 900)[2])

