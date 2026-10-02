import base64
import asyncio
from datetime import datetime, timezone, timedelta
import gc
import io
import os
from pathlib import Path
import queue
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch, AsyncMock

from PIL import Image
from jarvis.actions import Actions
from jarvis.commands import Command, parse
from jarvis.interface import build_interface
from jarvis.island_choices import snapshot, resolve, task_answer
from jarvis.island_desk import Approval
from jarvis.island_games import Game, GAMES, merge, winner, best_move
from jarvis.island_artwork import unobscured
from jarvis.island_media import MediaJobs, thumbnail, metadata


def pending_actions():
    actions = Actions.__new__(Actions)
    actions.generation = 3
    actions.pending_open = actions.pending_question = None
    actions.projects = SimpleNamespace(pending=None)
    actions.ui_controls = None
    actions.task_active = False
    actions.report = Mock()
    return actions


class ChoiceTests(unittest.TestCase):
    def test_click_routes_original_command_and_never_another_option_list(self):
        actions = pending_actions()
        original = Command('open','spotify')
        actions.pending_open = {'time':time.monotonic(),'choices':[original,Command('open','chrome')]}
        token = snapshot(actions)['token']
        self.assertEqual(resolve(actions,token,0),original)
        actions.pending_open = {'time':time.monotonic(),'choices':[Command('close_app','spotify')]}
        with self.assertRaisesRegex(ValueError,'changed or expired'):
            resolve(actions,token,0)

    def test_expired_choices_and_changed_generation_are_rejected(self):
        actions = pending_actions()
        actions.pending_open = {'time':time.monotonic()-46,'choices':[Command('open','spotify')]}
        self.assertIsNone(snapshot(actions))
        actions.pending_open['time'] = time.monotonic()
        token = snapshot(actions)['token']
        actions.generation += 1
        with self.assertRaises(ValueError):
            resolve(actions,token,0)

    def test_native_card_keeps_control_path_and_revalidates_before_dispatch(self):
        actions = pending_actions()
        actions.ui_controls = Mock()
        actions.ui_controls.pending = {'time':time.monotonic(),'handle':12,'signature':'state-a',
                                      'choices':[{'name':'Song A','id':[1]}],'verb':'play'}
        token = snapshot(actions)['token']
        command = resolve(actions,token,0)
        self.assertEqual(command.kind,'island_control_choice')
        actions._ui = Mock(return_value=actions.ui_controls)
        actions._execute(command)
        actions.ui_controls.execute.assert_called_once()
        self.assertEqual(actions.ui_controls.execute.call_args[0][0].extra,'island_bound')
        actions.ui_controls.pending['signature']='state-b'
        with self.assertRaisesRegex(ValueError,'changed or expired'):
            actions._execute(command)
        self.assertEqual(actions.ui_controls.execute.call_count,1)

    def test_spoken_choice_from_island_focus_uses_bound_window_and_foreign_focus_rejects(self):
        from jarvis.ui_controls import UIControls
        values=[{'name':'Song A','id':[1],'role':'DataItem','rect':[10,10,100,40]}]
        requests=[]
        def runner(request,cancelled):
            requests.append(request)
            return {'controls':values,'signature':'same','message':'Activated Song A'}
        def owned_pid(handle,pointer): pointer._obj.value=os.getpid()
        user=SimpleNamespace(GetForegroundWindow=lambda:777,GetWindowThreadProcessId=owned_pid)
        ui=UIControls(SimpleNamespace(target=99,user=user),runner=runner)
        ui._handle=lambda:99
        ui.pending={'time':time.monotonic(),'handle':123,'signature':'same','choices':values,'verb':'select'}
        self.assertIn('Activated',ui.execute(Command('choose_control','1')))
        self.assertTrue(all(request['handle']==123 for request in requests))
        ui.pending={'time':time.monotonic(),'handle':123,'signature':'same','choices':values,'verb':'select'}
        user.GetWindowThreadProcessId=lambda handle,pointer:setattr(pointer._obj,'value',222)
        with self.assertRaisesRegex(ValueError,'changed'):
            ui.execute(Command('choose_control','1'))
        self.assertEqual(sum(request['operation']=='activate' for request in requests),1)

    def test_expired_open_does_not_intercept_fresh_project_card(self):
        actions = pending_actions()
        actions.pending_open = {'time':time.monotonic()-46,'choices':[Command('open','chrome')]}
        actions.projects.pending = {'time':time.monotonic(),'choices':[Path('D:/demo')]}
        card = snapshot(actions)
        self.assertEqual(resolve(actions,card['token'],0),Command('open_project',str(Path('D:/demo'))))

    def test_games_and_scoped_transport_preserve_running_task(self):
        actions = pending_actions()
        actions.task_active = True
        actions.memory = Mock()
        actions.queue = queue.Queue()
        for name in GAMES:
            actions.submit(parse('play '+name+' game'))
        actions.submit(Command('spotify_control','pause','island'))
        actions.submit(Command('spotify_control','status'))
        self.assertEqual(actions.generation,3)
        self.assertTrue(actions.queue.empty())
        actions.memory.ensure_index.assert_not_called()
        self.assertEqual(actions.report.call_count,7)

    def test_spoken_game_controls_preserve_background_work(self):
        actions = pending_actions()
        actions.task_active=True
        for phrase in ('please play snake game','pause game','resume game','restart game','stop game'):
            actions.submit(parse(phrase))
        self.assertEqual(actions.generation,3)
        self.assertEqual(actions.report.call_count,5)

    def test_current_goal_answer_is_recorded_and_date_checked(self):
        state = Mock()
        state.snapshot.return_value = {'goal':'Build the calculator','status':'running','stage':'writing',
            'started_at':datetime.now(timezone.utc).isoformat(),'checkpoints':[{'target':'D:/demo/calc.py'}]}
        self.assertIn('Build the calculator',task_answer(state,"what's my goal today"))
        self.assertIn('calc.py',task_answer(state,'what was I working on'))
        state.snapshot.return_value['started_at'] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        self.assertIn('No daily goal',task_answer(state,"what's my goal today"))
        self.assertIsNone(task_answer(None,'make a website'))


class GameTests(unittest.TestCase):
    def test_five_engines_have_distinct_real_rendered_boards(self):
        self.assertEqual(len(GAMES),5)
        renders = {Game(name,random.Random(1)).render().tobytes() for name in GAMES}
        self.assertEqual(len(renders),5)

    def test_2048_merge_does_not_merge_new_tile_twice(self):
        self.assertEqual(merge([2,2,2,2]),([4,4,0,0],8))
        game = Game('2048',random.Random(1))
        game.grid = [[1024,1024,0,0],[0]*4,[0]*4,[0]*4]
        game.key('Left')
        self.assertTrue(game.over)
        self.assertIn('won',game.outcome)

    def test_2048_noop_does_not_spawn_and_full_board_ends(self):
        game = Game('2048',random.Random(1))
        game.grid = [[2,0,0,0],[0]*4,[0]*4,[0]*4]
        game.key('Left')
        self.assertEqual(sum(bool(x) for row in game.grid for x in row),1)
        game.grid = [[2,4,2,4],[4,2,4,2],[2,4,2,4],[4,2,4,2]]
        game.key('Left')
        self.assertTrue(game.over)

    def test_snake_wall_collision_and_no_reverse(self):
        game = Game('Snake')
        game.key('Left')
        self.assertEqual(game.next_direction,(1,0))
        game.snake = [(19,0),(18,0),(17,0)]
        for _ in range(4):
            game.tick(.05)
        self.assertTrue(game.over)

    def test_snake_food_grows_and_paused_game_freezes(self):
        game = Game('Snake')
        game.food = (8,7)
        game.key('Right')
        for _ in range(3): game.tick(.05)
        self.assertEqual(game.score,1)
        self.assertEqual(len(game.snake),4)
        before = game.snake[:]
        game.paused = True
        for _ in range(20): game.tick(.05)
        self.assertEqual(before,game.snake)

    def test_flappy_collision_restart_and_score(self):
        game = Game('Flappy')
        game.key('space')
        game.pipes = [[40,140,False],[440,140,False]]
        game.tick(.01)
        self.assertEqual(game.score,1)
        game.bird = 300
        game.tick(.01)
        self.assertTrue(game.over)
        game.reset()
        self.assertFalse(game.over)
        self.assertEqual(game.score,0)

    def test_tic_tac_toe_ai_blocks_wins_and_clicks_ignore_outside(self):
        self.assertEqual(best_move(['X','X','','','O','','','','']),2)
        self.assertEqual(winner(['O','O','O','','','','','','']),'O')
        game = Game('Tic Tac Toe')
        game.click(0,0)
        self.assertFalse(any(game.board))
        game.click(110,30)
        self.assertEqual(game.board.count('X'),1)
        self.assertEqual(game.board.count('O'),1)

    def test_memory_mismatch_delay_and_complete_game(self):
        game = Game('Memory')
        game.cards = [0,1,2,3,4,5,0,1,2,3,4,5]
        def click(index): game.click(110+(index%4)*70,30+(index//4)*80)
        click(0); click(1)
        self.assertEqual(len(game.opened),2)
        for _ in range(17): game.tick(.05)
        self.assertFalse(game.opened)
        for i in range(6): click(i); click(i+6)
        self.assertTrue(game.over)
        self.assertEqual(len(game.matched),12)


class ApprovalAndMediaTests(unittest.TestCase):
    def test_media_metadata_reads_real_winrt_memory_stream_and_excludes_browser_session(self):
        # Match production isolation: WinRT native factories live in a child,
        # not in the Tk/speech test runner's COM apartment and DLL lifetime.
        if os.environ.get('JARVIS_STREAM_TEST_CHILD')!='1':
            environment=dict(os.environ,JARVIS_STREAM_TEST_CHILD='1')
            result=subprocess.run([sys.executable,'-m','unittest',
                'test_island_desk.ApprovalAndMediaTests.test_media_metadata_reads_real_winrt_memory_stream_and_excludes_browser_session'],
                capture_output=True,text=True,timeout=15,env=environment,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.assertEqual(result.returncode,0,result.stderr)
            return
        async def exercise():
            from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
            stream=InMemoryRandomAccessStream()
            writer=DataWriter(stream)
            raw=io.BytesIO(); Image.new('RGB',(240,240),'purple').save(raw,format='PNG')
            writer.write_bytes(raw.getvalue())
            await writer.store_async()
            writer.detach_stream(); writer.close(); stream.seek(0)
            properties=SimpleNamespace(title='Fixture track',artist='Fixture artist',album_title='Fixture album',
                thumbnail=SimpleNamespace(open_read_async=AsyncMock(return_value=stream)))
            spotify=SimpleNamespace(source_app_user_model_id='SpotifyAB.SpotifyMusic!Spotify',
                try_get_media_properties_async=AsyncMock(return_value=properties),
                get_timeline_properties=lambda:SimpleNamespace(position=timedelta(seconds=30),end_time=timedelta(seconds=180)),
                get_playback_info=lambda:SimpleNamespace(playback_status=SimpleNamespace(name='PAUSED')))
            chrome=SimpleNamespace(source_app_user_model_id='chrome.exe')
            manager=SimpleNamespace(get_sessions=lambda:[chrome,spotify])
            factory=SimpleNamespace(request_async=AsyncMock(return_value=manager))
            with patch('winrt.windows.media.control.GlobalSystemMediaTransportControlsSessionManager',factory):
                result=await metadata()
            self.assertEqual(result['title'],'Fixture track')
            self.assertEqual(result['position'],30)
            self.assertEqual(result['status'],'paused')
            self.assertEqual(Image.open(io.BytesIO(base64.b64decode(result['image']))).size,(192,192))
        asyncio.run(exercise())

    def test_media_metadata_multiple_sources_and_missing_properties_are_explicit(self):
        if os.environ.get('JARVIS_STREAM_TEST_CHILD')!='1':
            result=subprocess.run([sys.executable,'-m','unittest',
                'test_island_desk.ApprovalAndMediaTests.test_media_metadata_multiple_sources_and_missing_properties_are_explicit'],
                capture_output=True,text=True,timeout=15,env=dict(os.environ,JARVIS_STREAM_TEST_CHILD='1'),
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.assertEqual(result.returncode,0,result.stderr)
            return
        spotify=SimpleNamespace(source_app_user_model_id='Spotify!App')
        factory=SimpleNamespace(request_async=AsyncMock(return_value=SimpleNamespace(get_sessions=lambda:[spotify,spotify])))
        with patch('winrt.windows.media.control.GlobalSystemMediaTransportControlsSessionManager',factory):
            with self.assertRaisesRegex(ValueError,'Multiple Spotify'):
                asyncio.run(metadata())
        spotify.try_get_media_properties_async=AsyncMock(return_value=None)
        factory.request_async=AsyncMock(return_value=SimpleNamespace(get_sessions=lambda:[spotify]))
        with patch('winrt.windows.media.control.GlobalSystemMediaTransportControlsSessionManager',factory):
            with self.assertRaisesRegex(ValueError,'not exposed'):
                asyncio.run(metadata())

    def test_approval_is_explicit_idempotent_and_cancelled_or_expired_never_yes(self):
        for cancelled,now,expected in ((False,11,True),(True,11,False),(False,191,False)):
            answer,ready = {},threading.Event()
            approval = Approval(('delete','D:/exact.txt',answer,ready,lambda:cancelled),10)
            approval.decide(True,now)
            approval.decide(False,now)
            self.assertTrue(ready.is_set())
            self.assertEqual(answer['approved'],expected)

    def test_artwork_is_bounded_real_image_and_bad_data_rejected(self):
        image = Image.new('RGB',(512,512),'#ab98dd')
        output = io.BytesIO(); image.save(output,format='PNG')
        result = thumbnail(output.getvalue())
        self.assertEqual(Image.open(io.BytesIO(base64.b64decode(result))).size,(192,192))
        self.assertEqual(thumbnail(b'x'*2_000_001),'')
        with self.assertRaises(OSError): thumbnail(b'broken')

    def test_occluded_or_foreign_window_cannot_supply_choice_photo(self):
        gui = Mock()
        gui.GetForegroundWindow.return_value=12
        gui.GetWindowRect.return_value=(0,0,500,500)
        gui.GetAncestor.return_value=12
        self.assertTrue(unobscured(gui,12,(10,10,70,70)))
        gui.GetAncestor.return_value=99
        self.assertFalse(unobscured(gui,12,(10,10,70,70)))
        gui.GetForegroundWindow.return_value=99
        self.assertFalse(unobscured(gui,12,(10,10,70,70)))

    def test_media_timeout_is_not_replayed_and_quit_kills_only_owned_child(self):
        jobs = MediaJobs(Mock(),'.')
        process = Mock()
        process.poll.return_value=None
        import subprocess
        process.communicate.side_effect=[subprocess.TimeoutExpired('observe',8),('','')]
        with patch('jarvis.island_media.subprocess.Popen',return_value=process) as launch:
            jobs._run('pause')
            self.assertEqual(launch.call_count,1)
            process.kill.assert_called_once()
            self.assertIn('no retry',jobs.report.call_args[0][1]['error'].lower())
        jobs.process=process
        jobs.close()
        self.assertFalse(jobs.start())


class DeskWidgetTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk(); self.root.withdraw()
        self.app = Mock()
        self.app.root=self.root
        self.app.config={'whisper':{'model':'test'},'knowledge':{},'_ui_verification':True}
        self.app.speech.options={'enabled':False}
        build_interface(self.app)
        self.app.panel.geometry('660x760+20000+20000')
        self.app.panel.deiconify()
        self.root.update()

    def tearDown(self):
        self.app.desk.close()
        self.root.destroy()
        self.app=None; self.root=None
        gc.collect()

    def test_background_file_visible_in_every_view_and_code_draft_is_not_saved(self):
        desk = self.app.desk
        desk.notify('task_status',{'phase':'Writing 300 chars','target':'D:/demo/app.tsx','file':'D:/demo/app.tsx',
            'preview':'export const App = () => null','characters':300,'outcome':'Incomplete draft','active':True})
        actions = pending_actions()
        self.app.actions=actions
        desk.tick(False)
        for name in ('Overview','Music','Games','History','Settings'):
            desk.show(name)
            self.assertIn('app.tsx',desk.now.get())
        self.assertIn('Incomplete draft',desk.overview.get('1.0','end'))
        desk.notify('task_status',{'phase':'Ready','active':False})
        self.assertEqual(desk.work['outcome'],'Incomplete draft')

    def test_click_and_voice_use_same_bound_choice_path_and_old_button_cannot_retarget(self):
        actions = pending_actions()
        actions.pending_open={'time':time.monotonic(),'choices':[Command('open','spotify'),Command('open','chrome')]}
        actions.submit=Mock()
        self.app.actions=actions
        desk=self.app.desk
        card=snapshot(actions)
        desk.update_choices(card)
        desk.choice_buttons[1].invoke()
        selected=actions.submit.call_args[0][0]
        self.assertEqual(selected,Command('island_choice','1',card['token']))
        self.assertEqual(resolve(actions,selected.extra,1),Command('open','chrome'))
        with self.assertRaises(ValueError): resolve(actions,selected.extra,1)

    def test_inline_approval_does_not_block_game_or_task_and_close_denies(self):
        desk=self.app.desk
        desk.show('Games')
        ready=threading.Event(); answer={}
        desk.add_approval(('delete','D:/exact.txt',answer,ready,lambda:False))
        self.assertEqual(desk.view,'Approval')
        self.assertFalse(ready.is_set())
        self.assertIn('D:/exact.txt',desk.approval_text.get('1.0','end'))
        self.app.actions.cancel.assert_not_called()
        desk.close()
        self.assertTrue(ready.is_set())
        self.assertFalse(answer['approved'])

    def test_actual_game_widgets_pause_restart_and_keep_task_queue_independent(self):
        desk=self.app.desk
        desk.show('Games'); desk.select_game('2048')
        desk.game.grid=[[2,2,0,0],[0]*4,[0]*4,[0]*4]
        desk.game_key(SimpleNamespace(keysym='Left'))
        self.assertEqual(desk.game.score,4)
        desk.pause_game()
        self.assertTrue(desk.game.paused)
        desk.restart_game()
        self.assertFalse(desk.game.paused)
        self.app.actions.submit.assert_not_called()


if __name__=='__main__': unittest.main()
