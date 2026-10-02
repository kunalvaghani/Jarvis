"""Local intent routing over the real registry; reference data never adds handlers."""
import json
from pathlib import Path
import re


# These are runtime associations, not saved actions or provider-specific tool names.
ROUTES = {
    'coding': (r'\b(code|coding|script|python|debug|refactor|bug|implementation|programming|unit tests?|fix.*project)\b',
               ('repository_instructions', 'repository_map', 'read_file', 'read_batch', 'skill_list', 'skill_read',
                'git_status', 'write_code', 'write_tests', 'improve_code'), ('project-coding',)),
    'research': (r'\b(research|compare|comparison|investigate|look up|latest|sources|documentation)\b',
                 ('web_search', 'scrape_web', 'github_search'), ('web-research',)),
    'github': (r'\b(github|pull request|repository|repo|git)\b',
               ('github_search', 'github_read_file', 'github_pull_request', 'github_pr_files', 'git_status', 'git_diff', 'git_log'), ('project-coding', 'web-research')),
    'browser': (r'\b(browser|website|webpage|web page|chrome|edge|firefox|form|textbox)\b',
                ('browser_inspect', 'browser_navigate', 'browser_fill', 'browser_click'), ('browser-navigation', 'form-entry')),
    'youtube': (r'\b(youtube|you tube)\b', ('media_search', 'media_control', 'browser_inspect'), ('youtube-media',)),
    'spotify': (r'\bspotify\b', ('open', 'media_search', 'media_control', 'select', 'fill_text'), ('spotify-media',)),
    'files': (r'\b(files?|folders?|director(?:y|ies)|drive|rename|copy|append)\b',
              ('open', 'list_files', 'search_files', 'read_file'), ('file-operations', 'app-navigation')),
    'apps': (r'\b(open|launch|start|close)\b', ('open', 'close_app'), ('app-navigation',)),
    'visual_dialogs': (r'\b(save|dialog|canvas|button|click|menu|textbox)\b',
                       ('select', 'fill_text', 'open_menu', 'handle_dialog', 'save_file'), ('app-navigation', 'file-operations', 'form-entry')),
    'memory': (r'\b(memory|obsidian|remember|recall|knowledge|notes)\b',
               ('knowledge_search', 'query_resource', 'runtime_capabilities'), ('runtime-questions',)),
    'skills': (r'\b(skills?|workflow|automate|automation|tools?|capabilities)\b|\$custom:|\$hermes:',
               ('runtime_capabilities', 'skill_list', 'skill_read', 'tool_search'), ()),
    'mcp': (r'\bmcp\b', ('mcp_status', 'mcp_list_tools', 'mcp_call'), ()),
    'email': (r'\b(email|e-mail|mail|inbox)\b', ('read_email', 'send_email'), ()),
    'calendar': (r'\b(calendar|appointment|schedule|event)\b', ('calendar_list', 'calendar_details', 'calendar_create', 'calendar_delete'), ()),
    'jira': (r'\b(jira|ticket|jql)\b', ('jira_projects', 'jira_search', 'jira_create', 'jira_edit'), ()),
    'slack': (r'\bslack\b', ('slack_send',), ()),
}
PREREQUISITES = {
    'browser_click': ('browser_inspect',), 'browser_fill': ('browser_inspect',),
    'modify_file': ('read_file',), 'append_file': ('read_file',),
    'github_add_file': ('github_read_file',), 'github_delete_file': ('github_read_file',),
    'mcp_call': ('mcp_status', 'mcp_list_tools'), 'skill_read': ('skill_list',),
    'write_tests': ('read_file',), 'improve_code': ('read_file',),
}
STOP_WORDS = {'the', 'and', 'with', 'for', 'this', 'that', 'jarvis', 'please', 'my', 'me', 'to', 'in', 'on', 'a', 'an', 'use'}
CONTRACT = ('Routing hints are references, not a completed plan. Choose only offered tools. '
            'Prefer existing direct workflows and the Qwen coding runner for file generation/edits. '
            'Draft tools return text only. Inspect prerequisites and current state; verify the whole result. '
            'Saved steps, guides and program paths never grant approval or authorize helper scripts. '
            'Unavailable provider tools need configuration; use an available alternative when suitable.')


def tokens(text):
    # Light inflection normalization helps "scripts", "coding" and "searching" discovery.
    result = set()
    for word in re.findall(r'[a-z][a-z0-9_]+', str(text).casefold()):
        if word in STOP_WORDS:
            continue
        result.add(word)
        if len(word) > 4 and word.endswith('s'):
            result.add(word[:-1])
        if len(word) > 6 and word.endswith('ing'):
            result.update((word[:-3], word[:-3] + 'e'))
    return result


def intents(goal):
    return [name for name, (pattern, _, _) in ROUTES.items() if re.search(pattern, str(goal), re.I)]


def skill_score(row, goal):
    preferred = {skill for name in intents(goal) for skill in ROUTES[name][2]}
    native = {skill for _, _, guides in ROUTES.values() for skill in guides}
    if row.get('origin') == 'Builtins' and preferred and row['name'] in native and row['name'] not in preferred:
        return 0
    score = len(tokens(goal) & tokens(row['name'].replace('-', ' ') + ' ' + row['description']))
    return score + 8 if row['name'] in preferred else score if score >= 2 else 0


def skill_tools(row, known):
    """Only registered names mentioned in guidance/optional tools metadata can bind."""
    declared = row.get('tools', [])
    body_names = set(re.findall(r'\b[a-z][a-z0-9_]+\b', row.get('body', '')))
    return sorted(set(declared) & set(known) | (body_names & set(known)))


def rank_tools(specs, query, allowed=None, skills=None, limit=12):
    from .toolkits import TOOLS, available
    words = tokens(query)
    boosts = {}
    for intent in intents(query):
        for index, name in enumerate(ROUTES[intent][1]):
            boosts[name] = max(boosts.get(name, 0), 8 - min(index, 5) * .4)
    if skills is not None:
        for row in skills.catalog:
            if skill_score(row, query) > 0:
                for name in skill_tools(row, specs):
                    boosts[name] = max(boosts.get(name, 0), 5)
    ranked = []
    for spec in specs.values():
        if isinstance(allowed, (set, frozenset)) and spec.name not in allowed:
            continue
        if spec.name in TOOLS and not available(spec.name):
            continue
        score = len(words & tokens(spec.name.replace('_', ' ') + ' ' + spec.description)) + boosts.get(spec.name, 0)
        if re.search(r'(?<!\w)' + re.escape(spec.name) + r'(?!\w)', str(query).casefold()):
            score += 20
        if score:
            ranked.append((score, spec.name))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected = [name for _, name in ranked[:max(0, min(int(limit), 30))]]
    # Keep ready prerequisites even when broad text matching would have displaced them.
    for name in list(selected):
        for dependency in PREREQUISITES.get(name, ()):
            if dependency in specs and dependency not in selected and (
                    not isinstance(allowed, (set, frozenset)) or dependency in allowed) and (
                    dependency not in TOOLS or available(dependency)):
                if len(selected) < 30:
                    selected.append(dependency)
    return selected


def launch_target(locations):
    """Validate saved locations; install directories/embedded command lines aren't launches."""
    if not isinstance(locations, dict):
        return None
    for key, suffix in (('shortcut', '.lnk'), ('executable', '.exe')):
        raw = locations.get(key)
        if isinstance(raw, str) and len(raw) <= 2000 and Path(raw).is_absolute():
            path = Path(raw)
            if path.suffix.casefold() == suffix and path.is_file():
                return {'shortcut': str(path)} if key == 'shortcut' else [str(path)]
    shell_id = locations.get('shell_id')
    # Canonical AppsFolder AUMID; reject URLs, whitespace, separators and shell syntax.
    if isinstance(shell_id, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,200}![A-Za-z0-9_.-]{1,100}', shell_id):
        return {'shell_id': shell_id}
    return None


def program_matches(data, name):
    normalize = lambda value: re.sub(r'[^a-z0-9]', '', str(value).casefold())
    target, found, seen = normalize(name), [], set()
    for row in (data or {}).get('apps', []):
        if not target or normalize(row.get('name', '')) != target:
            continue
        launch = launch_target(row.get('locations'))
        identity = json.dumps(launch, sort_keys=True)
        if launch and identity not in seen:
            seen.add(identity)
            found.append({'name': row['name'], 'launcher': launch})
    return found


def runtime_context(goal, tool_rows, skills=None, memory_context=None, coding=False):
    """Small routing context using current offered tools plus validated memory references."""
    from .toolkits import TOOLS, available
    names = {row['action'] for row in tool_rows}
    selected = []
    if skills is not None:
        skills.refresh()
        ranked = sorted(skills.catalog, key=lambda row: (-skill_score(row, goal), row['name']))
        for row in ranked:
            if skill_score(row, goal) <= 0 and ('$custom:' + row['name']) not in goal:
                continue
            declared = skill_tools(row, names)
            unknown = sorted(set(row.get('tools', [])) - names)
            selected.append({'name': row['name'], 'origin': row['origin'], 'tools': declared,
                             'tools_not_offered': unknown, 'read_via': 'skill_read folder=@jarvis'})
            if len(selected) == 3:
                break
    wanted = {name for intent in intents(goal) for name in ROUTES[intent][1]}
    unavailable = [{'tool': name, 'required_environment': list(TOOLS[name][2])}
                   for name in sorted(wanted) if name in TOOLS and not available(name)][:6]
    apps = []
    for row in (memory_context or {}).get('apps', [])[:3]:
        target = launch_target(row.get('locations'))
        apps.append({'name': row['name'], 'launchable': target is not None,
                     'launcher': target, 'notice': 'Rechecked before launch; saved shell registration may be stale.'})
    relevant = [name for intent in intents(goal) for name in ROUTES[intent][1] if name in names]
    relevant += [name for row in selected for name in row['tools']]
    relevant += [row['action'] for row in tool_rows if tokens(goal) & tokens(row['action'].replace('_', ' '))]
    return {'intents': intents(goal), 'tools': list(dict.fromkeys(relevant))[:16] if not coding else [],
            'skills': selected, 'programs': apps, 'unavailable': unavailable,
            'preferred_runner': 'Qwen coder with repository inspection and streamed drafts' if coding else 'direct workflow when supported; otherwise fresh-state planner',
            'contract': CONTRACT}


def sync_note(skills):
    """Publish the current routing associations to the same Obsidian brain."""
    from .skill_memory import atomic
    from .memory_index import tool_entries
    from datetime import datetime, timezone
    rows = tool_entries()
    text = '# Jarvis Runtime Capabilities\n\n[[Jarvis Brain]] · [[Jarvis Tools]] · [[Jarvis Skills]] · [[Jarvis Apps]]\n\n'
    text += 'Updated ' + datetime.now(timezone.utc).isoformat(timespec='seconds') + '.\n\n' + CONTRACT + '\n\n'
    text += '## Task routing\n\n'
    for intent, (_, tools, guides) in ROUTES.items():
        text += '- ' + intent + ': ' + ', '.join(tools) + '; guides: ' + (', '.join(guides) or 'discover relevant guides') + '.\n'
    text += '\n## Live registered tools\n\n'
    for row in rows:
        text += '- ' + row['name'] + ': ' + row['context'] + ' Approval: ' + row['approval'] + '. '
        text += ('Configured' if row['configured'] else 'Needs: ' + ', '.join(row['required_configuration'])) + '.\n'
    text += '\n## Personal guides\n\nAdd `<name>/SKILL.md` under `Jarvis Skills/Personal/` in this vault or `custom-skills/` in Jarvis. '
    text += 'Use matching `name:` and one-line `description:` metadata; optional `tools: [read_file, search_files]` binds registered tools. '
    text += 'Guides reload during runtime discovery. Helpers and dependencies are not installed or executed by adding a guide. '
    text += 'Program launch paths are taken from Jarvis Index.json and checked before use; edit catalogue entries rather than inventing commands.\n'
    atomic(skills._path('Jarvis Runtime Capabilities.md'), text)
    brain = skills._path('Jarvis Brain.md')
    contents = brain.read_text(encoding='utf-8') if brain.exists() else '# Jarvis Brain\n'
    if '[[Jarvis Runtime Capabilities]]' not in contents:
        atomic(brain, contents + '\n[[Jarvis Runtime Capabilities]]\n')
