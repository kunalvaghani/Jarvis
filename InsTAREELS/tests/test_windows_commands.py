import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from jarvis.windows_commands import catalog,match,parse,prepare,powershell,interpret,execute,run_ps,ROOT


def examples(row):
    result={}
    for key,spec in row['parameters'].items():
        v=spec.get('example')
        if key=='app_id':v='Microsoft.WindowsCalculator_8wekyb3d8bbwe!App'
        if spec['type']=='path':v=str(ROOT/'fixture.png')
        result[key]=v
    return result


class ReferenceTests(unittest.TestCase):
    def test_all_493_source_commands_preserved(self):
        rows=catalog(); source=json.loads((ROOT/'Jarvis_Windows_11_Commands.json').read_text())
        self.assertEqual(len(rows),493)
        for row,original in zip(rows,source):
            for key in original:self.assertEqual(row[key],original[key])
        self.assertEqual(len({r['category'] for r in rows}),21)

    def test_every_recipe_is_compilable_and_reachable(self):
        class Fake:
            def __getattr__(self,name):return self
            def __call__(self,*args,**kwargs):return self
            def __str__(self):return 'fixture observation'
        rows=catalog()
        for row in rows:
            with self.subTest(id=row['id']):
                params=examples(row)
                ids=[row['id']]; bindings=params
                if row['id']==294:ids=[294,295];bindings={'294':{},'295':{}}
                if row['id']>=481 and row['id']<=490:
                    ids=[480,481]
                    if row['id']==482:ids=[480]
                    if row['id']>=483:ids.append(483)
                    if row['id'] not in ids:ids.append(row['id'])
                    bindings={str(i):examples(rows[i-1]) for i in ids}
                if row['id']>=492:ids=[491,row['id']];bindings={str(row['id']):params}
                ready=prepare(ids,bindings)
                if row['type']=='PS':
                    script=powershell(ready)
                    self.assertNotIn('C:\\Work',script) if not params else None
                    self.assertIn('Command '+str(row['id']),script)
                else:
                    self.assertTrue(interpret(ready,{'pg':Fake(),'Desktop':Fake(),'w':Fake(),'page':Fake(),'print':Fake()})['message'])

    def test_missing_bindings_block_entire_batch_before_dispatch(self):
        actions=Mock()
        with patch('jarvis.windows_commands.run_ps') as run:
            with self.assertRaises(ValueError):execute(actions,[119,140],{'119':{},'140':{} })
            run.assert_not_called();actions._approve.assert_not_called()

    def test_literals_cannot_inject_powershell(self):
        value="x'; Start-Process evil; '$(secret)`x"
        text=powershell(prepare([169],{'text1':value}))
        self.assertIn("'x''; Start-Process evil; ''$(secret)`x'",text)
        with self.assertRaises(ValueError):prepare([100],{'pid':'1;shutdown /s'})

    def test_coordinate_examples_are_not_default_inputs(self):
        with self.assertRaises(ValueError):prepare([286],{})
        with self.assertRaises(ValueError):prepare([302],{'arg1':'screen.png'})
        with self.assertRaises(ValueError):prepare([294],{})
        with self.assertRaises(ValueError):prepare([309],{'arg1':['enter']})

    def test_safety_gate_and_stop_before_effect(self):
        actions=Mock();actions._approve.side_effect=ValueError('Declined')
        with patch('jarvis.windows_commands.run_ps') as run:
            with self.assertRaises(ValueError):execute(actions,[148],{'path1':str(ROOT/'fixture.txt')})
            run.assert_not_called()
        with patch('jarvis.windows_commands.subprocess.Popen') as launch:
            with self.assertRaises(ValueError):run_ps('Get-Date',lambda:True)
            launch.assert_not_called()

    def test_uncertain_failure_never_replays(self):
        with patch('jarvis.windows_commands.run_ps',side_effect=ValueError('Uncertain')) as run:
            with self.assertRaises(ValueError):execute(Mock(),[119],{})
            self.assertEqual(run.call_count,1)

    def test_stop_during_helper_kills_only_that_helper_without_retry(self):
        child=Mock();child.poll.return_value=None
        cancelled=Mock(side_effect=[False,True])
        with patch('jarvis.windows_commands.subprocess.Popen',return_value=child) as launch:
            with self.assertRaisesRegex(ValueError,'Inspect state'):run_ps('Get-Date',cancelled)
            launch.assert_called_once();child.kill.assert_called_once();child.wait.assert_called_once()

    def test_helper_deadline_does_not_replay(self):
        child=Mock();child.poll.return_value=None
        with patch('jarvis.windows_commands.subprocess.Popen',return_value=child) as launch, patch('jarvis.windows_commands.time.monotonic',side_effect=[0,30]):
            with self.assertRaises(ValueError):run_ps('Get-Date',lambda:False)
            launch.assert_called_once();child.kill.assert_called_once()

    def test_root_delete_and_invalid_batch_rejected(self):
        with self.assertRaises(ValueError):prepare([148],{'path1':'D:\\'})
        with self.assertRaises(ValueError):prepare([1,225],{})
        with self.assertRaises(ValueError):prepare([119]*21,{})
        with self.assertRaises(ValueError):prepare([484],{'text1':'A1','text2':'x'})
        with self.assertRaises(ValueError):prepare([146],{'path1':str(ROOT/'a'),'name':'../oops'})

    def test_exact_routing_and_context_ambiguity(self):
        self.assertEqual(match('open camera'),1)
        self.assertEqual(match('open youtube for me'),88)
        self.assertEqual(match('open display settings'),38)
        self.assertEqual(match('open chrome'),66)
        self.assertIsNone(match('why open camera'))
        self.assertIsNone(match('do not open camera'))
        self.assertIsNone(match('open camera and write a script'))
        self.assertIsNone(match('Navigate to URL'))  # Browser shortcut versus owned DOM.
        self.assertEqual(parse('windows command 1').kind,'windows_command')

    def test_hash_mismatch_rejects_modified_recipes(self):
        with patch.object(Path,'read_bytes',return_value=b'[]'):
            with self.assertRaises(ValueError):catalog()

    def test_closing_browser_never_restarts_for_recipe(self):
        from jarvis.browser_worker import Session
        session=Session()
        with patch.object(session,'open') as opening:
            with self.assertRaises(ValueError):session.perform({'operation':'windows_commands','ids':[467],'bindings':{}})
            opening.assert_not_called()

    def test_dom_ambiguity_stops_before_click(self):
        from jarvis.windows_command_browser import perform
        page=Mock();page.url='https://example.org';page.is_closed.return_value=False
        page.get_by_role.return_value.count.return_value=2
        with self.assertRaises(ValueError):perform({'ids':[468],'bindings':{'arg1':'Continue'},'url':page.url},page)
        page.get_by_role.return_value.click.assert_not_called()

    def test_interpreter_stops_between_calls_on_changed_target(self):
        guard=Mock(side_effect=[None,None,ValueError('Closed')])
        pg=Mock()
        with self.assertRaises(ValueError):interpret(prepare([336],{'arg1':'https://example.org'}),{'pg':pg},guard)
        pg.hotkey.assert_called_once();pg.write.assert_not_called();pg.press.assert_not_called()

    def test_registered_tools_are_discoverable(self):
        from jarvis.tools import ToolRegistry
        actions=SimpleNamespace(config={})
        names={r['action'] for r in ToolRegistry(actions).catalog()}
        self.assertTrue({'windows_command_search','windows_command'}<=names)

    def test_youtube_reference_shortcuts_reject_search_pages_and_spoofed_titles(self):
        from jarvis.windows_command_desktop import matches_app
        self.assertFalse(matches_app(r'C:\Apps\chrome.exe','YouTube - Google Search - Google Chrome','youtube'))
        self.assertFalse(matches_app(r'C:\Apps\notepad.exe','YouTube','youtube'))
        self.assertTrue(matches_app(r'C:\Apps\chrome.exe','Example video - YouTube - Google Chrome','youtube'))

    def test_natural_literal_bindings(self):
        command=parse(r'read entire file as string "D:\Work\notes.txt"')
        self.assertEqual(json.loads(command.extra),{'path1':r'D:\Work\notes.txt'})
        command=parse(r'copy file "D:\Work\a.txt" to "D:\Work\b.txt"')
        self.assertEqual(json.loads(command.value),[143])
        self.assertEqual(json.loads(command.extra),{'path1':r'D:\Work\a.txt','path2':r'D:\Work\b.txt'})

    def test_audio_recipes_wait_for_final_and_preserve_literal_punctuation(self):
        from jarvis.engine import Engine
        sent=[];engine=Engine(sent.append,lambda *_:None)
        text='jarvis windows command 169 {"text1":"Line one. Then line two."}'
        engine.feed(text,final=False);self.assertEqual(sent,[])
        engine.feed(text,final=True)
        self.assertEqual(len(sent),1)
        self.assertEqual(json.loads(sent[0].extra),{'text1':'Line one. Then line two.'})

    def test_planner_cannot_change_explicit_literal_parameters(self):
        from jarvis.agent_tools import execute as agent_execute
        actions=SimpleNamespace(task_state=Mock())
        actions.task_state.snapshot.return_value={'goal':'windows command 169 {"text1":"literal"}'}
        with patch('jarvis.windows_commands.execute') as effect:
            with self.assertRaises(ValueError):agent_execute(actions,{'action':'windows_command','value':'169','content':'{"text1":"invented"}'},lambda:False)
            effect.assert_not_called()
