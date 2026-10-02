"""Read-only runtime routing checks; no model calls, app launches or synthetic learning."""
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
from types import SimpleNamespace

from jarvis.capabilities import runtime_context
from jarvis.memory_index import tool_entries
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory
from jarvis.tools import ToolRegistry


def main():
    base = Path(__file__).resolve().parent
    config = json.loads((base / 'config.json').read_text(encoding='utf-8'))
    memory = ObsidianMemory(base, config.get('memory'))
    skills = SkillMemory(memory)
    memory.skills = skills
    actions = SimpleNamespace(base=base, config=config, skills=skills, memory=memory)
    registry = ToolRegistry(actions)
    cases = [
        ('Debug my Python alarm script', {'repository_instructions', 'repository_map', 'read_file', 'write_tests'}, 'project-coding'),
        ('Research and compare free speech engines', {'web_search', 'scrape_web'}, 'web-research'),
        ('Search YouTube for jazz and play first video', {'media_search', 'media_control', 'browser_inspect'}, 'youtube-media'),
        ('Search Spotify for jazz', {'open', 'media_search', 'media_control'}, 'spotify-media'),
        ('Find a file in a folder', {'search_files', 'list_files', 'read_file'}, 'file-operations'),
        ('Discover MCP automation tools', {'mcp_status', 'mcp_list_tools', 'mcp_call'}, None),
        ('Open Obsidian', {'open'}, 'app-navigation'),
    ]
    results, elapsed = [], []
    for goal, required, guide in cases:
        report = None
        for _ in range(10):
            start = time.perf_counter()
            discovered = registry.search(goal)
            rows = registry.catalog(goal)
            saved = memory.task_context(goal)
            report = runtime_context(goal, rows, skills, saved)
            guidance = skills.context(goal)
            elapsed.append((time.perf_counter() - start) * 1000)
        names = {row['action'] for row in discovered}
        guides = [row['name'] for row in guidance.get('skills', [])]
        results.append({'goal': goal, 'selected_tools': sorted(names), 'selected_local_guides': guides,
                        'required_tools_found': required <= names,
                        'expected_guide_found': guide is None or guide in guides,
                        'program_reference_count': len(report['programs']),
                        'launchable_program_reference_count': sum(p['launchable'] for p in report['programs'])})
    report = {'at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'kind': 'live configured memory/registry routing; no task execution or model inference',
              'cases': results, 'all_checks_passed': all(r['required_tools_found'] and r['expected_guide_found'] for r in results),
              'lookup_ms': {'samples': len(elapsed), 'median': round(statistics.median(elapsed), 3), 'max': round(max(elapsed), 3)},
              'registered_tools': len(tool_entries()), 'configured_tools': sum(r['configured'] for r in tool_entries()),
              'local_guides': len(skills.catalog), 'hermes_reference_guides': len(skills.upstream.rows) if skills.upstream else 0,
              'guide_errors': len(skills.skill_errors),
              'limits': 'Checks tool/guide retrieval only, not model choice quality or end-to-end speed/accuracy. Memory program launchability is rechecked path/syntax evidence, not a live launch.'}
    path = base / 'artifacts/runtime-capabilities-check.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    if not report['all_checks_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
