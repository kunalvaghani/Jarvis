"""Live candidate acceptance on public disposable fixtures; never certifies all apps.

Run modes separately from timing benchmarks. Existing user models/services are
not terminated. Voice uses generated public PCM, not a microphone recording.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

BASE = Path(__file__).resolve().parents[2]


def files(out, configuration='both', selected_case=None):
    from jarvis.actions import Actions
    from jarvis.brain import BrainClient
    from jarvis.commands import Command
    from jarvis.task_state import TaskState
    rows = []
    for label in ('baseline', 'hierarchy'):
        if configuration != 'both' and label != configuration:
            continue
        for name, goal, expected in (
            ('read', 'Read one.txt in this folder and report its exact contents.', ['PUBLIC_ALPHA_731']),
            ('workflow', 'Inspect files one.txt and two.txt in this folder and report both contents.',
             ['PUBLIC_ALPHA_731', 'PUBLIC_BETA_942']),
            ('unfamiliar', 'An unfamiliar device calls its input a flarble. Read flarble.txt in this folder and report the documented safe operation.',
             ['rotate clockwise twice']),
        ):
            if selected_case and name != selected_case:
                continue
            root = (out/(label+'-'+name)).resolve()
            root.mkdir()
            for filename, content in {'one.txt':'PUBLIC_ALPHA_731', 'two.txt':'PUBLIC_BETA_942',
                                      'flarble.txt':'Safe operation: rotate clockwise twice.'}.items():
                (root/filename).write_text(content, encoding='utf-8')
            config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
            options = {**config['brain'], 'model_hierarchy': {'enabled':label == 'hierarchy',
                'execution_model':'qwen3.5:2b', 'reasoning_model':'qwen3.5:9b'}}
            # Actual execution/verification machinery; only the public fixture
            # capability is admitted. No optional private/cloud/background data.
            config.update(files_root='managed', apps={}, _ui_verification=True,
                          memory={'enabled':False}, groq={'enabled':False},
                          knowledge_acquisition={'enabled':False}, brain=options)
            actions = Actions(config, root, lambda *_:None)
            actions.allowed_tools = {'read_file'}
            def folder(value, cancelled):
                if value not in {'this folder', '.', str(root)}:
                    raise ValueError('Outside disposable live acceptance scope.')
                return root
            actions._task_folder = folder
            actions.task_state = TaskState(root)
            actions.brain.client.close()
            actions.brain.client = BrainClient(BASE, options)
            calls = []
            request = actions.brain.client.request
            def record(operation, cancelled, **data):
                result = request(operation, cancelled, **data)
                calls.append({'operation':operation, 'model':result.get('model_used'),
                              'route':result.get('model_route'), 'public_fixture_proposal':result})
                return result
            actions.brain.client.request = record
            row = {'configuration':label, 'case':name}
            started = time.monotonic()
            try:
                answer = str(actions.execute(Command('task', goal), lambda:time.monotonic()-started > 240))
                snapshot = actions.task_state.snapshot()
                row.update(status=snapshot.get('status'), calls=calls,
                    passed=snapshot.get('status') == 'completed' and all(value in answer for value in expected),
                    expected_contents_in_answer=all(value in answer for value in expected),
                    checkpoints=snapshot.get('checkpoints'), reply=answer)
            except Exception as exc:
                row.update(passed=False, error_type=type(exc).__name__, error=str(exc)[:600], calls=calls)
            finally:
                actions.close()
            row['seconds'] = time.monotonic()-started
            rows.append(row)
            (out/'results.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k not in {'checkpoints','reply','calls'}}), flush=True)
    return rows


def voice(out):
    import numpy as np
    from jarvis.kokoro_speech import load_voice, synthesize
    from jarvis.whisper_backend import load_model
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    text = 'Jarvis read the public test file.'
    started = time.monotonic()
    speaker = load_voice(BASE/'models/voices/kokoro/kokoro-v1.0.onnx', BASE/'models/voices/kokoro/voices-v1.0.bin')
    audio, rate = synthesize(speaker, text, {'voice':'af_heart', 'speed':1.0})
    synthesis_seconds = time.monotonic()-started
    # Whisper accepts 16 kHz mono; explicit linear resampling for this speech probe.
    pcm = np.interp(np.arange(int(len(audio)*16000/rate))*rate/16000,
                    np.arange(len(audio)), np.asarray(audio)).astype(np.float32)
    started = time.monotonic()
    recognizer = load_model(BASE/config['model_path'], config['whisper'])
    loaded = time.monotonic()-started
    started = time.monotonic()
    segments, _ = recognizer.transcribe(pcm, language='en', beam_size=1)
    transcript = ' '.join(segment.text for segment in segments).strip()
    normalized = ''.join(c.lower() for c in transcript if c.isalnum() or c == ' ')
    row = {'case':'synthetic_tts_stt', 'passed':'read the public test file' in normalized,
           'public_text':text, 'transcript':transcript, 'synthesis_seconds':synthesis_seconds,
           'recognizer_load_seconds':loaded, 'decode_seconds':time.monotonic()-started,
           'audio_seconds':len(audio)/rate,
           'scope':'Actual installed Kokoro and configured Whisper. No speaker playback, microphone, acoustic WER corpus or physical interaction.'}
    (out/'results.json').write_text(json.dumps([row], indent=2), encoding='utf-8')
    print(json.dumps(row), flush=True)
    return [row]


def media(out):
    from jarvis.actions import Actions, Desktop
    from jarvis.commands import Command
    from jarvis.tools import ToolRegistry
    from jarvis import youtube_chrome
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    config.update(_ui_verification=True, memory={'enabled':False}, groq={'enabled':False})
    actions = Actions(config, out.resolve(), lambda *_:None, Desktop())
    registry = ToolRegistry(actions)
    calls = []
    actions.brain.client.request = lambda *a, **k: calls.append(True) or (_ for _ in ()).throw(AssertionError('Deterministic media called a model'))
    rows = []
    try:
        for platform in ('youtube', 'spotify'):
            row = {'case':platform, 'passed':False}
            stage = 'session_discovery'
            started = time.monotonic()
            try:
                if platform == 'youtube':
                    sessions = youtube_chrome.sessions()
                    row['chrome_session_count'] = len(sessions)
                    if len(sessions) != 1:
                        raise ValueError('Need one unambiguous existing Chrome media session; no private title recorded or ambiguous session controlled.')
                    actions.youtube_target = 'user_chrome'
                    actions.last_youtube = {'title':sessions[0]['title']}
                stage = 'initial_status'
                before = str(actions.execute(Command('media_control','status',platform)))
                playing = before.startswith('Playing:') if platform == 'youtube' else before.startswith('Spotify is playing:')
                paused = before.startswith('Paused:') if platform == 'youtube' else before.startswith('Spotify is paused:')
                if not (playing or paused):
                    raise ValueError('Existing session is neither independently reported playing nor paused.')
                target = 'pause' if playing else 'play'
                stage = 'change_state'
                registry.execute({'action':'media_control','value':target,'platform':platform}, lambda:False)
                after = str(actions.execute(Command('media_control','status',platform)))
                changed = (after.startswith('Paused:') if platform == 'youtube' else after.startswith('Spotify is paused:')) if playing else (
                    after.startswith('Playing:') if platform == 'youtube' else after.startswith('Spotify is playing:'))
                row.update(initial_state='playing' if playing else 'paused', changed_state_verified=changed)
                if not changed:
                    raise ValueError('Fresh status did not confirm the requested state; no repeat or recovery replay.')
                stage = 'restore_state'
                registry.execute({'action':'media_control','value':'play' if playing else 'pause','platform':platform}, lambda:False)
                restored = str(actions.execute(Command('media_control','status',platform)))
                restored_state = (restored.startswith('Playing:') if platform == 'youtube' else restored.startswith('Spotify is playing:')) if playing else (
                    restored.startswith('Paused:') if platform == 'youtube' else restored.startswith('Spotify is paused:'))
                row.update(passed=restored_state, restored_state_verified=restored_state, model_calls=len(calls))
            except Exception as exc:
                # Never export media titles/artist names or a user transcript.
                row.update(error_type=type(exc).__name__, failed_stage=stage,
                           reason='Media check did not complete; inspect the current app/session before retrying.')
            row['seconds'] = time.monotonic()-started
            rows.append(row)
            print(json.dumps(row), flush=True)
            (out/'results.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    finally:
        actions.close()
    return rows


def playback(out):
    from jarvis.actions import Actions, Desktop
    from jarvis.commands import Command
    from jarvis import youtube_chrome, spotify
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    config.update(_ui_verification=True, memory={'enabled':False}, groq={'enabled':False})
    actions = Actions(config, out.resolve(), lambda *_:None, Desktop())
    rows = []
    try:
        for platform, query in (('youtube','Big Buck Bunny Blender Foundation'),
                                ('spotify','Never Gonna Give You Up Rick Astley')):
            row = {'case':platform, 'passed':False, 'public_query':query}
            started = time.monotonic()
            try:
                reply = str(actions.execute(Command('play_media',query,platform), lambda:time.monotonic()-started > 120))
                if platform == 'youtube':
                    title = (getattr(actions,'last_youtube',None) or {}).get('title','')
                    current = [s for s in youtube_chrome.sessions() if title and youtube_chrome.matches(title,s['title'])]
                    verified = len(current) == 1 and current[0]['status'] == 'playing' and 'bunny' in current[0]['title'].lower()
                else:
                    status = str(spotify.control('status'))
                    verified = status.startswith('Spotify is playing:') and 'never gonna give you up' in status.lower()
                row['playback_independently_verified'] = verified
                if not verified:
                    raise ValueError('Playback not independently verified; no repeat.')
                actions.execute(Command('media_control','pause',platform))
                status = str(actions.execute(Command('media_control','status',platform)))
                row.update(passed=status.startswith('Paused:') if platform == 'youtube' else status.startswith('Spotify is paused:'),
                           public_test_paused=True)
            except Exception as exc:
                row.update(error_type=type(exc).__name__, reason='Public playback not accepted; no retry after uncertain media effect.')
            row['seconds'] = time.monotonic()-started
            rows.append(row)
            print(json.dumps(row), flush=True)
            (out/'results.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    finally:
        actions.close()
    return rows


def youtube_exact(out):
    from jarvis.actions import Actions, Desktop
    from jarvis.commands import Command
    from jarvis.media_player import play_youtube_item
    from jarvis import youtube_chrome
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    config.update(_ui_verification=True, files_root=str(out.resolve()/'managed'),
                  memory={'enabled':False}, groq={'enabled':False})
    actions = Actions(config, BASE, lambda *_:None, Desktop())
    row = {'case':'youtube_exact_public_video', 'passed':False,
           'video_id':'aqz-KE-bpKQ', 'profile':config.get('media',{}).get('youtube_chrome_profile')}
    started = time.monotonic()
    try:
        play_youtube_item(actions, 'aqz-KE-bpKQ', 'Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film',
                          'Blender', lambda:time.monotonic()-started > 100)
        title = (getattr(actions,'last_youtube',None) or {}).get('title','')
        sessions = [r for r in youtube_chrome.sessions() if title and youtube_chrome.matches(title,r['title'])]
        verified = len(sessions) == 1 and sessions[0]['status'] == 'playing' and 'bunny' in sessions[0]['title'].lower()
        row['playback_verified'] = verified
        if verified:
            actions.execute(Command('media_control','pause','youtube'))
            row['passed'] = str(actions.execute(Command('media_control','status','youtube'))).startswith('Paused:')
    except Exception as exc:
        row.update(error_type=type(exc).__name__, reason='Exact public playback not confirmed; no replay or fallback browser.')
    finally:
        actions.close()
    row['seconds'] = time.monotonic()-started
    (out/'results.json').write_text(json.dumps([row], indent=2), encoding='utf-8')
    print(json.dumps(row), flush=True)
    return [row]


def coding(out):
    import ast
    import subprocess
    import sys
    from jarvis.actions import Actions
    from jarvis.brain import BrainClient
    from jarvis.commands import Command
    from jarvis.task_state import TaskState
    rows = []
    test = 'import unittest\nfrom calc import add\nclass TestAdd(unittest.TestCase):\n def test_sum(self):\n  self.assertEqual(add(2,3),5)\n  self.assertEqual(add(-4,1),-3)\n'
    for label in ('baseline','hierarchy'):
        root = (out/label).resolve()
        root.mkdir()
        (root/'calc.py').write_text('def add(a, b):\n    return a - b\n', encoding='utf-8')
        (root/'test_calc.py').write_text(test, encoding='utf-8')
        (root/'README.md').write_text('Public arithmetic fixture. Run python -m unittest -q. Only calc.py may change. No dependencies or network required.', encoding='utf-8')
        config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
        options = {**config['brain'],
                   'model_hierarchy':{'enabled':label == 'hierarchy','execution_model':'qwen3.5:2b','reasoning_model':'qwen3.5:9b'}}
        config.update(_ui_verification=True, files_root='managed', apps={}, memory={'enabled':False},
                      groq={'enabled':False}, brain=options)
        actions = Actions(config, root, lambda *_:None)
        actions.task_state = TaskState(root)
        actions.brain.client.close()
        actions.brain.client = BrainClient(BASE, options)
        row = {'case':'coding_bugfix', 'configuration':label, 'configured_backend':options.get('coding_backend'),
               'configured_coder':options.get('coder'), 'passed':False}
        started = time.monotonic()
        budget = min(3600,max(60,float(options.get('max_coding_seconds',1800))))
        row['configured_budget_seconds'] = budget
        try:
            answer = actions.execute(Command('code_task',
                'Fix calc.py so add(a, b) returns a + b for integers. Change only calc.py. Preserve test_calc.py and all documentation. '
                'Run python -m unittest -q. Use only installed Python standard library; no network, packages, installation or deletion.',str(root)),
                lambda:time.monotonic()-started > budget+30)
            source = (root/'calc.py').read_text(encoding='utf-8')
            tree = ast.parse(source)
            safe = (ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,ast.BinOp,ast.Add,
                    ast.Name,ast.Load,ast.Constant,ast.Expr)
            if any(not isinstance(node,safe) for node in ast.walk(tree)):
                raise ValueError('Generated arithmetic source exceeds independent execution oracle scope.')
            if (root/'test_calc.py').read_text(encoding='utf-8') != test:
                raise ValueError('Frozen public test was changed.')
            check = subprocess.run([sys.executable,'-m','unittest','-q'],cwd=root,capture_output=True,text=True,
                                   timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            row.update(passed=check.returncode == 0, independent_test_exit=check.returncode,
                       task_status=actions.task_state.snapshot().get('status'), public_reply=str(answer)[-1200:])
        except Exception as exc:
            row.update(error_type=type(exc).__name__, error=str(exc)[:700])
        finally:
            actions.close()
        row['seconds'] = time.monotonic()-started
        rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k != 'public_reply'}), flush=True)
        (out/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    return rows


def research(out):
    from jarvis.actions import Actions
    from jarvis.brain import BrainClient
    from jarvis.commands import Command
    from jarvis.task_state import TaskState
    rows = []
    for label in ('baseline','hierarchy'):
        root = (BASE/'.jarvis-runtime/student-system-live'/out.name/label).resolve()
        root.mkdir(parents=True)
        config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
        options = {**config['brain'], 'model_hierarchy':{'enabled':label == 'hierarchy',
                    'execution_model':'qwen3.5:2b','reasoning_model':'qwen3.5:9b'}}
        config.update(_ui_verification=True, files_root='managed', apps={}, memory={'enabled':False},
                      knowledge_acquisition={'enabled':False}, groq={'enabled':False}, brain=options)
        actions = Actions(config, root, lambda *_:None)
        actions.allowed_tools = {'scrape_web','think'}
        actions.task_state = TaskState(root)
        actions.brain.client.close()
        actions.brain.client = BrainClient(BASE, options)
        row = {'case':'public_documentation_research','configuration':label,'passed':False}
        started = time.monotonic()
        try:
            answer = str(actions.execute(Command('task',
                'Research https://docs.python.org/3/library/json.html and explain the difference between json.dump and json.dumps. '
                'Cite that source URL. Only read the supplied public documentation; no local files or other sites.'),
                lambda:time.monotonic()-started > 240))
            lower = answer.lower()
            checks = {'source_url':'https://docs.python.org/3/library/json.html' in answer,
                      'dump_named':'dump' in lower,'dumps_named':'dumps' in lower,
                      'file_and_string_terms':'file' in lower and ('string' in lower or 'str object' in lower)}
            row.update(passed=all(checks.values()) and actions.task_state.snapshot().get('status') == 'completed',
                       task_status=actions.task_state.snapshot().get('status'), checks=checks, public_answer=answer,
                       grading_scope='Bounded terminology/source checks; not a general semantic-quality or citation-entailment score.')
        except Exception as exc:
            row.update(error_type=type(exc).__name__,error=str(exc)[:700])
        finally:
            actions.close()
        row['seconds'] = time.monotonic()-started
        rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k != 'public_answer'}),flush=True)
        (out/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    return rows


def contention(out):
    from concurrent.futures import ThreadPoolExecutor
    import subprocess
    import threading
    from jarvis.brain_worker import Models
    from jarvis.tools import SPECS
    from scripts.verification.phase2_gpu_voice_probe import run_probe
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    trace = []
    stopped = threading.Event()
    began = time.monotonic()
    def sample():
        while not stopped.is_set():
            try:
                result = subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],
                    capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
                used, utilization = map(int,result.stdout.strip().split(','))
                trace.append({'seconds':time.monotonic()-began,'gpu_used_mb':used,'utilization_percent':utilization})
            except (ValueError,OSError,subprocess.SubprocessError):
                pass
            stopped.wait(.3)
    sampler = threading.Thread(target=sample,daemon=True)
    sampler.start()
    rows = []
    try:
        for label in ('baseline','hierarchy'):
            for repetition in range(2):
                def proposal():
                    worker = Models()
                    try:
                        result = worker.predict({'operation':'next_step','options':{**config['brain'],
                            'model_hierarchy':{'enabled':label == 'hierarchy','execution_model':'qwen3.5:2b','reasoning_model':'qwen3.5:9b'}},
                            'goal':'Read public.txt in this folder.', 'screen':{},'apps':{},'completed':[],
                            'tools':[{'action':s.name,'description':s.description} for s in SPECS if s.name == 'read_file']})
                        return {'completed':bool(result.get('steps')),'model':result.get('model_used'),
                                'action':(result.get('steps') or [{}])[0].get('action')}
                    finally:
                        worker.client.close()
                started = time.monotonic()
                with ThreadPoolExecutor(max_workers=3) as pool:
                    futures = {'planner':pool.submit(proposal), 'whisper':pool.submit(run_probe,'whisper','.venv',150),
                               'kokoro':pool.submit(run_probe,'kokoro','.venv',150)}
                    probes = {}
                    for name, future in futures.items():
                        try:
                            probes[name] = future.result()
                        except Exception as exc:
                            probes[name] = {'completed':False,'error_type':type(exc).__name__}
                row = {'case':'simultaneous_model_voice_submissions','configuration':label,'repetition':repetition,
                       'seconds':time.monotonic()-started,'probes':probes,
                       'passed':all(p.get('completed') for p in probes.values()) and probes['planner'].get('action') == 'read_file'}
                rows.append(row)
                print(json.dumps(row),flush=True)
                (out/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    finally:
        stopped.set()
        sampler.join(4)
        (out/'gpu-samples.json').write_text(json.dumps({'samples':trace,
            'max_sampled_mb':max((r['gpu_used_mb'] for r in trace),default=None),
            'scope':'Shared host sampled VRAM, not allocator peak or isolated model usage. Whisper probe decodes synthetic silence; Kokoro synthesizes public text; no physical microphone/speaker.'},indent=2),encoding='utf-8')
    return rows


def transfer(out):
    from types import SimpleNamespace
    from jarvis.obsidian_memory import ObsidianMemory
    from jarvis.skill_memory import SkillMemory
    from jarvis.brain_worker import Models
    from jarvis.tools import ToolRegistry, SPECS
    packet = BASE/'artifacts/jarvis-audit/small-model/2026-10-21'
    source = next(json.loads(line) for line in (packet/'final-owned-file-execution/rows.jsonl').read_text(encoding='utf-8').splitlines()
                  if json.loads(line).get('configuration') == 'baseline' and json.loads(line).get('case') == 'routine' and json.loads(line).get('verified'))
    if not all(attempt['model'] == 'qwen3.5:9b' for attempt in source['attempts']):
        raise ValueError('Public source is not a verified teacher trace.')
    task = {'task_id':'public-transfer-reconstruction','goal':'Read notes.txt in this folder','kind':'task',
            'status':'completed','result':'Independent public exact-byte proof', 'plan':{'completed':source['steps']},
            'model_routes':[{'model':'qwen3.5:9b','category':'files','reason':'public_fixture'}],
            'checkpoints':[{'stage':'verified','evidence':source['steps'][0]['result']},
                           {'stage':'goal_verified','evidence':'Actual public benchmark exact bytes matched.'}]}
    root = (BASE/'.jarvis-runtime/student-system-live'/out.name).resolve()
    root.mkdir(parents=True)
    (root/'other.txt').write_text('NEW_PUBLIC_TARGET_516',encoding='utf-8')
    memory = ObsidianMemory(root,{'enabled':True,'vault':'vault'})
    skills = SkillMemory(memory)
    memory.skills = skills
    worker = Models()
    row = {'case':'bounded_teacher_procedure_transfer','passed':False,
           'envelope':'Reconstructed from actual verified public benchmark, not a foreground task capture.',
           'general_transfer_quality_proved':False, 'causal_training_gain_claimed':False}
    try:
        skills.record(task)
        context = skills.context('Read other.txt in this folder')
        templates = [p['teacher_procedure'] for p in context.get('procedures',[]) if p.get('teacher_procedure')]
        if not templates or 'notes.txt' in json.dumps(templates):
            raise ValueError('Parameterized teacher procedure was not safely retrieved.')
        config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
        result = worker.predict({'operation':'next_step','options':config['brain'],
            'goal':'Read other.txt in this folder','screen':{},'apps':{},'completed':[], 'skill_context':context,
            'tools':[{'action':s.name,'description':s.description} for s in SPECS if s.name == 'read_file']})
        proposal = (result.get('steps') or [{}])[0]
        if proposal.get('action') != 'read_file' or proposal.get('value') != 'other.txt':
            raise ValueError('Student did not bind the current public target; no action dispatched.')
        def folder(value,cancelled):
            if value not in {'this folder','.',str(root)}:
                raise ValueError('Outside public transfer scope.')
            return root
        actions = SimpleNamespace(base=root,config={},allowed_tools={'read_file'},report=lambda *_:None,_task_folder=folder)
        receipt = ToolRegistry(actions).execute(proposal,lambda:False)
        row.update(passed=result.get('model_used') == 'qwen3.5:2b' and receipt.evidence == 'NEW_PUBLIC_TARGET_516',
                   model=result.get('model_used'), retrieved_parameterized_procedure=True,
                   new_target_used=proposal['value'] == 'other.txt',exact_new_bytes_verified=receipt.evidence == 'NEW_PUBLIC_TARGET_516')
    except Exception as exc:
        row.update(error_type=type(exc).__name__,error=str(exc)[:500])
    finally:
        skills.close()
        worker.client.close()
    (out/'results.json').write_text(json.dumps([row],indent=2),encoding='utf-8')
    print(json.dumps(row),flush=True)
    return [row]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('files','voice','media','playback','youtube_exact','coding','research','contention','transfer'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--configuration', choices=('both','baseline','hierarchy'), default='both')
    parser.add_argument('--case', choices=('read','workflow','unfamiliar'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'scope.json').write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),
        'mode':args.mode, 'timing':'Functional acceptance; host load is not controlled.'}, indent=2), encoding='utf-8')
    rows = files(args.out, args.configuration, args.case) if args.mode == 'files' else globals()[args.mode](args.out)
    return 0 if rows and all(row.get('passed') for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
