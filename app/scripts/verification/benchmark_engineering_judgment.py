"""Owned deterministic policy/skill/coder benchmark; inference is a labelled stub."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
import psutil
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis.coder import Coder
from jarvis.commands import parse
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', default='disabled', choices=('disabled', 'advisory', 'enforced'))
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2]
    options = {'enabled': args.mode != 'disabled', 'mode': args.mode if args.mode != 'disabled' else 'advisory'}
    rss_before = psutil.Process().memory_info().rss / (1024 * 1024)
    samples, calls, cases, selections, prompt_chars = [], [], [], [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-engineering-') as temporary:
        root = Path(temporary)
        memory = ObsidianMemory(root, {'enabled': True, 'vault': 'vault'})
        memory.engineering_options = options
        skills = SkillMemory(memory, base / 'skills')
        timings = []
        for goal in ('Open Notepad', 'Fix the YouTube connector', 'Refactor the Python parser', 'Create a Blender scene'):
            for _ in range(30):
                start = time.perf_counter()
                context = skills.context(goal)
                timings.append((time.perf_counter() - start) * 1000)
            selections.append({'goal': goal, 'skills': [row['name'] for row in context['skills']]})
            prompt_chars.append(len(json.dumps(context)))
        command_times = []
        for _ in range(200):
            start = time.perf_counter(); parse('open notepad')
            command_times.append((time.perf_counter() - start) * 1000)
        for index in range(5):
            project = root / str(index); project.mkdir()
            (project / 'pyproject.toml').write_text('[project]\nname="fixture"\n')
            target = project / 'app.py'; target.write_text('def value():\n    return 1\n')
            untouched = project / 'notes.txt'; untouched.write_text('Existing uncommitted user notes.\n')
            client = Mock(); client.options = {}
            client.request.return_value = {'content': 'def value():\n    return 7\n', 'explanation': 'Requested literal fix'}
            actions = SimpleNamespace(base=root, report=lambda *a: None)
            if args.mode != 'disabled':
                from jarvis.engineering_judgment import EngineeringJudgmentEngine
                actions.engineering = EngineeringJudgmentEngine(actions, options)
            start = time.perf_counter()
            result = Coder(actions, client).run(project, 'Modify app.py to return 7', selected=True)
            samples.append((time.perf_counter() - start) * 1000); calls.append(client.request.call_count)
            cases.append({'target_matches': target.read_text() == 'def value():\n    return 7\n',
                'unrelated_unchanged': untouched.read_text() == 'Existing uncommitted user notes.\n',
                'claims_functional_verification': 'Build and test' not in result})
        skills.close()
    data = {'at': datetime.now(timezone.utc).isoformat(), 'mode': args.mode,
        'scope': 'Actual bounded SkillMemory selection, command parser and Coder atomic edits of owned temporary files. Model output is a stub; no acoustic, real-model, VRAM or account benchmark.',
        'skill_selection_median_ms': statistics.median(timings), 'command_parse_median_ms': statistics.median(command_times),
        'coding_task_median_ms': statistics.median(samples), 'coding_samples_ms': samples,
        'model_calls_per_task': calls, 'selected_skills': selections, 'prompt_context_characters': prompt_chars,
        'cases': cases, 'verified_fixture_outputs': sum(c['target_matches'] and c['unrelated_unchanged'] for c in cases),
        'vram': 'No inference in this fixture; GPU allocation not measured',
        'ram_rss_before_mb': rss_before, 'ram_rss_after_mb': psutil.Process().memory_info().rss / (1024 * 1024),
        'ram_scope': 'Process RSS samples, including imports/catalog/coder work; not peak or isolated engine allocation'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(data))


if __name__ == '__main__':
    main()
