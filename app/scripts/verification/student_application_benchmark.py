"""Live model -> scoped ToolRegistry -> disposable Blender / read-only Unreal.

No user project is opened. Scene outputs remain in the new evidence directory.
Unreal acceptance is build metadata only, never editor/project correctness.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from jarvis.brain_worker import Models
from jarvis.blender_installation import executables
from jarvis.tools import ToolRegistry, SPECS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a new evidence directory.')
    args.out.mkdir(parents=True)
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    blender = next(iter(executables(r'D:\Blender\blender.exe')), None)
    unreal = Path(r'D:\UE_5.8')
    worker = Models()
    rows = []
    for label in ('baseline', 'hierarchy'):
        options = {**config['brain'], 'model_hierarchy': {'enabled': label == 'hierarchy',
                    'execution_model': 'qwen3.5:2b', 'reasoning_model': 'qwen3.5:9b'}}
        for app, tool in (('blender', 'blender_task'), ('unreal', 'unreal_task')):
            folder = (args.out/(label+'-'+app)).resolve()
            folder.mkdir()
            row = {'configuration': label, 'application': app}
            if (app == 'blender' and (not blender or not Path(blender).is_file())) or (app == 'unreal' and not (unreal/'Engine/Build/Build.version').is_file()):
                row.update(status='blocked', reason='Installed application absent')
                rows.append(row)
                continue
            def scope(name, cancelled):
                if name not in {'this folder', '.', str(folder)}:
                    raise ValueError('Outside disposable application scope.')
                return str(folder)
            def approve(kind, detail, cancelled):
                data = json.loads(detail)
                if kind != 'blender_task':
                    raise ValueError('Only the explicitly requested disposable Blender fixture may write.')
                # Adapter admission still validates every operation/path/value.
                if 'scene.blend' not in json.dumps(data):
                    raise ValueError('Unknown application output refused.')
            actions = SimpleNamespace(base=folder, task_state=None, report=lambda *a: None,
                allowed_tools={tool}, _task_folder=scope, _approve=approve,
                config={'execution_strategy': {'blender_executable': str(blender or ''), 'unreal_engine_root': str(unreal)}})
            registry = ToolRegistry(actions)
            tools = [{'action': s.name, 'description': s.description} for s in SPECS if s.name == tool]
            if app == 'blender':
                goal = ('Create scene.blend in this folder in Blender. Use blender_task with value scene.blend and '
                        'content {"operation":"create","objects":[{"type":"cube","name":"PublicCube","location":[1,2,3]}]}.')
            else:
                goal = 'Inspect Unreal Engine installed build version with unreal_task value inspect. Do not change any project.'
            started = time.perf_counter()
            try:
                proposal = worker.predict({'operation': 'next_step', 'options': options, 'goal': goal,
                    'tools': tools, 'screen': {'title': 'Disposable application fixture'}, 'completed': [], 'steps_left': 1})
                steps = proposal.get('steps', [])
                if len(steps) != 1 or steps[0].get('action') != tool:
                    raise ValueError('No exact offered application proposal.')
                step = steps[0]
                row['proposal'] = step
                if app == 'blender':
                    payload = json.loads(step.get('content') or '{}')
                    expected = {'operation': 'create', 'objects': [{'type': 'cube', 'name': 'PublicCube', 'location': [1,2,3]}]}
                    if step.get('value') != 'scene.blend' or payload != expected:
                        raise ValueError('Model arguments differ from the exact public scene fixture; nothing dispatched.')
                elif step.get('value') != 'inspect':
                    raise ValueError('Only read-only Unreal inspection is authorized.')
                result = json.loads(registry.execute(step, lambda: False).evidence)
                if app == 'blender':
                    inspected = json.loads(registry.execute({'action': 'blender_task', 'value': 'scene.blend',
                        'folder': 'this folder', 'content': '{"operation":"inspect"}'}, lambda: False).evidence)
                    cube = next((r for r in inspected.get('objects', []) if r.get('name') == 'PublicCube'), {})
                    verified = cube.get('vertices') == 8 and cube.get('location') == [1.0,2.0,3.0] and (folder/'scene.blend').is_file()
                    evidence = {'object': cube, 'file_exists': (folder/'scene.blend').is_file()}
                else:
                    version = json.loads((unreal/'Engine/Build/Build.version').read_text(encoding='utf-8-sig'))
                    expected = '.'.join(str(version[k]) for k in ('MajorVersion', 'MinorVersion', 'PatchVersion'))
                    verified = result.get('version') == expected
                    evidence = {'returned_version': result.get('version'), 'independent_manifest_version': expected}
                row.update(status='completed', verified=verified, model_used=proposal.get('model_used'),
                    route=proposal.get('model_route'), inference=proposal.get('inference'), evidence=evidence)
            except Exception as error:
                row.update(status='failed', verified=False, error_type=type(error).__name__, error=str(error)[:500])
            row['wall_s'] = time.perf_counter()-started
            rows.append(row)
            with (args.out/'rows.jsonl').open('a', encoding='utf-8') as output:
                output.write(json.dumps(row)+'\n')
            print(json.dumps(row), flush=True)
    (args.out/'summary.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    worker.client.close()


if __name__ == '__main__':
    main()
