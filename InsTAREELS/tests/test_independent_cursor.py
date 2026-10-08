import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis.independent_cursor import CursorCue
from jarvis.browser_cursor import click
from jarvis.execution_adapters import AgentS, Prepared, Unsupported
from jarvis.execution_router import execute, UncertainAction


class IndependentCursorTests(unittest.TestCase):
    def test_invalid_geometry_never_starts_renderer(self):
        for rect in ([0,0,0,10],[0,0,float('nan'),10],[0,0,float('inf'),10],
                     [True,0,10,10],[0,0,50000,10],[0,0,10],['1',0,10,10]):
            with self.assertRaises(ValueError): CursorCue(rect)
        self.assertEqual((CursorCue([-300,-100,-100,100]).x,CursorCue([-300,-100,-100,100]).y),(-200,0))

    def test_agent_s_missing_native_pattern_never_uses_mouse(self):
        element=Mock()
        with patch('jarvis.execution_adapters.pattern',side_effect=Unsupported('missing')):
            with self.assertRaises(Unsupported):
                AgentS().prepare(element,{'role':'Button'},{'operation':'activate'},None)
        element.click_input.assert_not_called()

    def test_focus_change_during_animation_stops_before_mutation(self):
        call=Mock(); trace=[]
        @contextmanager
        def cue(control):
            trace.append('open')
            try: yield
            finally: trace.append('closed')
        guard=Mock(side_effect=[None,None,None,ValueError('focus changed')])
        other=SimpleNamespace(name='other',prepare=Mock())
        provider=SimpleNamespace(name='native',prepare=lambda *a:Prepared(call))
        with self.assertRaisesRegex(ValueError,'focus changed'):
            execute({'operation':'activate'},None,{'role':'Button'},None,guard,
                    providers=[provider,other],cue=cue)
        self.assertEqual(trace,['open','closed']);call.assert_not_called();other.prepare.assert_not_called()

    def test_provider_error_disposes_cue_without_replaying(self):
        call=Mock(side_effect=RuntimeError('lost response'));trace=[]
        @contextmanager
        def cue(control):
            trace.append('open')
            try: yield
            finally: trace.append('closed')
        provider=SimpleNamespace(name='native',prepare=lambda *a:Prepared(call))
        other=SimpleNamespace(name='other',prepare=Mock())
        with self.assertRaises(UncertainAction):
            execute({'operation':'activate'},None,{'role':'Button'},None,lambda:None,
                    providers=[provider,other],cue=cue)
        call.assert_called_once();other.prepare.assert_not_called();self.assertEqual(trace,['open','closed'])

    def browser(self):
        page=Mock(url='https://example.com/');page.is_closed.return_value=False
        element=Mock();element.bounding_box.return_value={'x':20,'y':10,'width':80,'height':30}
        target=Mock();target.element_handle.return_value=element
        return page,element,target

    def test_browser_navigation_during_cue_blocks_click(self):
        page,element,target=self.browser()
        def change(delay):page.url='https://example.com/other'
        page.wait_for_timeout.side_effect=change
        with self.assertRaisesRegex(ValueError,'page changed'):click(target,page)
        element.click.assert_not_called();self.assertEqual(page.evaluate.call_count,2)

    def test_browser_failed_click_and_cleanup_are_never_retried(self):
        page,element,target=self.browser()
        element.click.side_effect=RuntimeError('unknown click outcome')
        page.evaluate.side_effect=[None,RuntimeError('page closed')]
        with self.assertRaisesRegex(RuntimeError,'unknown click'):click(target,page)
        element.click.assert_called_once()

    def test_browser_pins_one_element_and_cleans_up_on_success(self):
        page,element,target=self.browser();click(target,page,timeout=3000)
        target.element_handle.assert_called_once()
        target.click.assert_not_called();element.click.assert_called_once_with(timeout=3000)
        self.assertEqual(page.evaluate.call_count,2)

    def test_browser_hidden_target_never_creates_cue_or_clicks(self):
        page,element,target=self.browser();element.bounding_box.return_value=None
        with self.assertRaisesRegex(ValueError,'visible bounds'):click(target,page)
        element.click.assert_not_called();page.evaluate.assert_not_called()


if __name__=='__main__':unittest.main()
