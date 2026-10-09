import gc
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.interface import build_interface
from main import App


class NotchTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = Mock()
        self.app.root = self.root
        self.app.config = {'whisper':{'model':'test'}, 'knowledge':{}, '_ui_verification':True}
        self.app.speech.options = {'enabled':False}
        build_interface(self.app)
        self.root.update_idletasks()

    def tearDown(self):
        self.app.desk.close()
        self.root.destroy()
        self.app = self.root = None
        gc.collect()

    def test_every_feature_and_console_share_the_single_native_window(self):
        self.assertIs(self.app.panel.master, self.root)
        self.assertEqual(self.app.panel.winfo_class(), 'Frame')
        for name in self.app.desk.views:
            self.app.desk.show(name, reveal=True)
            self.app.panel.geometry('650x700+20000+20000')
            self.app.panel.deiconify()
            self.root.update_idletasks()
            self.assertIs(self.app.desk.views[name].winfo_toplevel(), self.root)
        App.show_command_prompt(self.app)
        App.show_command_prompt(self.app)
        self.assertEqual(self.app.desk.view, 'Console')
        self.assertIs(self.app.command_window.winfo_toplevel(), self.root)
        self.assertFalse(any(child.winfo_class() == 'Toplevel' for child in self.root.winfo_children()))

    def test_code_copy_preserves_full_result_without_replacing_task_preview(self):
        content = '```python\ndef add(a, b):\n    return a + b\n```\n' + 'Long result\n'*7000
        self.app.desk.notify('answer', content)
        self.assertLessEqual(len(self.app.desk.reply), 64000)
        with patch.object(self.root, 'clipboard_clear') as clear, patch.object(self.root, 'clipboard_append') as append:
            self.app.desk.copy_answer()
            clear.assert_called_once()
            append.assert_called_once_with(content)
        self.assertEqual(self.app.desk.work['preview'], '')

    def test_capture_and_collapse_hide_embedded_content_and_release_focus(self):
        self.app.config['ui'] = {'reduced_motion':True}
        self.app.capture_count = 0
        self.app.island.expand(True)
        self.app.island.tick('STANDBY')
        self.assertEqual(self.app.panel.state(), 'withdrawn')
        self.root.geometry('400x40+20000+20000')
        self.root.deiconify()
        self.app.island.tick('STANDBY')
        self.assertEqual(self.app.panel.state(), 'normal')
        self.app.capture_count = 1
        self.app.island.tick('STANDBY')
        self.assertEqual(self.app.panel.state(), 'withdrawn')
        self.app.island.expand(False)
        self.assertFalse(self.app.island.focus_pending)

    def test_answer_stream_updates_same_card_and_copy_preserves_code(self):
        source = '```cpp\nint main() {\n    return 0;\n}\n```'
        self.app.desk.notify('answer_stream', {'phase': 'Generating answer', 'text': source})
        self.assertIn('incomplete', self.app.desk.answer_title.cget('text'))
        self.assertIn(source, self.app.desk.overview.get('1.0', 'end-1c'))
        self.app.desk.overview.tag_add('sel', '2.0', '2.3')
        self.app.desk.notify('answer_stream', {'phase': 'Generating answer', 'text': source + '\nMore code'})
        self.assertEqual(self.app.desk.overview.get('sel.first', 'sel.last'), 'int')
        self.app.desk.notify('answer_stream', {'phase': 'Generating answer', 'text': source})
        with patch.object(self.root, 'clipboard_append') as append:
            self.app.desk.copy_answer()
        append.assert_called_once_with(source)
        self.app.desk.notify('answer', source)
        self.assertEqual(self.app.desk.answer_title.cget('text'), 'Jarvis · Answer')
        self.assertFalse(any(child.winfo_class() == 'Toplevel' for child in self.root.winfo_children()))

    def test_interruption_preserves_preview_with_incomplete_label(self):
        self.app.desk.notify('answer_stream', {'phase': 'Generating answer', 'text': 'Partial code'})
        self.app.desk.notify('answer_error', 'Ollama disconnected')
        self.assertIn('incomplete', self.app.desk.answer_title.cget('text'))
        self.assertIn('Partial code', self.app.desk.overview.get('1.0', 'end-1c'))
        self.app.desk.notify('answer_stream', {'phase': 'Preparing answer', 'text': ''})
        self.assertNotIn('Partial code', self.app.desk.overview.get('1.0', 'end-1c'))

    def test_stream_updates_never_remount_current_view(self):
        overview = self.app.desk.views['Overview']
        with patch.object(overview, 'pack_forget', wraps=overview.pack_forget) as unmount, \
                patch.object(overview, 'pack', wraps=overview.pack) as mount:
            for index in range(100):
                self.app.desk.notify('answer_stream', {'phase': 'Generating answer', 'text': 'line\n'*index})
            self.app.desk.notify('answer', 'line\n'*100)
        unmount.assert_not_called()
        mount.assert_not_called()
        self.assertEqual(self.app.desk.full_reply, 'line\n'*100)
        # Explicit feature navigation still changes the view and can reveal chrome.
        self.app.desk.show('Overview', reveal=True)
        self.assertTrue(self.app.island.features_open)
        self.app.desk.show('History')
        self.assertEqual(self.app.desk.view, 'History')

    def test_panel_growth_does_not_relayout_or_reapply_unchanged_bounds(self):
        self.app.question.set('A long question whose wrapping must use the incoming width')
        panel = self.app.panel
        with patch.object(self.app, 'layout_notch', wraps=self.app.layout_notch) as layout, \
                patch.object(panel, 'place', wraps=panel.place) as place:
            for height in (150, 210, 310, 330, 400, 710):
                panel.present(614, height, True)
                panel.deiconify()
            layout.assert_called_once()
            calls = place.call_count
            for _ in range(20):
                panel.present(614, 710, True)
                panel.deiconify()
            self.assertEqual(place.call_count, calls)
        self.assertGreater(float(self.app.question_label.cget('wraplength')), 400)

    def test_append_preserves_reading_line_instead_of_scroll_fraction(self):
        self.app.panel.geometry('614x600+20000+20000')
        self.app.panel.deiconify()
        content = '\n'.join('line '+str(n) for n in range(200))
        self.app.desk.notify('answer_stream', {'phase': 'Generating answer', 'text': content})
        self.root.update_idletasks()
        self.app.desk.overview.yview('30.0')
        before = self.app.desk.overview.index('@0,0')
        self.app.desk.notify('answer_stream', {'phase': 'Generating answer', 'text': content+'\nmore'*100})
        self.root.update_idletasks()
        self.assertEqual(self.app.desk.overview.index('@0,0'), before)

    def test_glass_composer_retains_readable_input_and_mic_handler(self):
        self.app.panel.geometry('650x180+20000+20000')
        self.app.panel.deiconify()
        self.app.preview.insert(0,'A request typed into the glass field')
        self.root.update()
        self.assertEqual(self.app.preview.get(),'A request typed into the glass field')
        _x,y,_width,height=self.app.preview.bbox(0)
        self.assertGreaterEqual(y,0)
        self.assertLessEqual(y+height,self.app.preview.winfo_height())
        mic=next(child for child in self.app.preview.master.winfo_children()
                 if child.winfo_class()=='TButton' and child.cget('text')=='Mic')
        mic.invoke()
        self.app.toggle_listening.assert_called_once()

    def test_clicked_dropdown_retains_focus_during_island_expansion(self):
        self.app.panel.geometry('650x700+20000+20000')
        self.app.panel.deiconify()
        self.app.desk.show('Settings')
        self.app.island.expanded = False
        self.app.island.surface_open = True
        self.app.island.focus_pending = True
        combo = self.app.answer_language
        self.root.update()
        combo.event_generate('<ButtonPress-1>',x=5,y=5)
        self.root.update()
        self.assertFalse(self.app.island.focus_pending)
        popdown=self.root.tk.call('ttk::combobox::PopdownWindow',str(combo))
        listbox=str(popdown)+'.f.l'
        self.root.tk.call(listbox,'selection','clear',0,'end')
        self.root.tk.call(listbox,'selection','set',2)
        self.root.tk.call('ttk::combobox::LBSelected',listbox)
        self.root.update()
        self.assertEqual(combo.get(),'Hindi')
        self.app.save_speech_settings.assert_called_once()

    def test_real_glass_choice_mouse_release_routes_bound_memory_index(self):
        self.app.panel.geometry('650x700+20000+20000')
        self.app.panel.deiconify()
        pending={'token':'memory-token','kind':'memory','expires':9999999999,
                 'options':[{'label':'Python calculator session','context':'Matched: calculator\nA: Tkinter UI'},
                            {'label':'C++ calculator session','context':'Matched: calculator\nA: Win32 UI'}]}
        self.app.desk.update_choices(pending)
        self.root.update()
        button=self.app.desk.choice_buttons[1]
        button.event_generate('<Enter>',x=10,y=10)
        button.event_generate('<ButtonPress-1>',x=10,y=10)
        button.event_generate('<ButtonRelease-1>',x=10,y=10)
        self.root.update()
        from jarvis.commands import Command
        self.app.actions.submit.assert_called_once_with(Command('memory_choice','1','memory-token'))

    def test_coding_preview_reveals_once_without_taking_focus(self):
        self.app.island.notify('task_status',{'phase':'Opening Claude Code project','active':True,'reveal':True})
        self.assertTrue(self.app.island.expanded)
        self.assertFalse(self.app.island.focus_pending)
        self.app.island.expand(False)
        self.app.island.notify('task_status',{'phase':'Claude Code: Edit','active':True,'preview':'source'})
        self.assertFalse(self.app.island.expanded)
        self.app.island.notify('task_status',{'phase':'Claude Code session ended','active':False})
        self.app.island.notify('answer','Files updated')
        self.assertTrue(self.app.island.stream_hidden)
        self.assertFalse(self.app.island.work_completion_pending)


if __name__ == '__main__':
    unittest.main()
