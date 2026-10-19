"""Generate the sealed evaluation datasets (train split for proposers, held-out split for the gate).

Provenance: every case is either generated here from a fixed seed (DAGs, salience streams,
retry cases) or authored in this file as a labelled oracle (tool queries, lessons, routing
goals, multiple-choice questions). Authored labels reflect the intended Jarvis behaviour and
are a limitation: they are not drawn from user logs and contain no private data.
Run: python evolution_eval/generate_data.py   (refuses to overwrite existing files)
"""
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parent


def dags(seed, count):
    rng = random.Random(seed)
    cases = []
    for index in range(count):
        concurrency = rng.choice([2, 2, 3])
        steps = []
        kind = index % 3
        if kind == 0:  # many short independent steps listed before a long chain
            for i in range(rng.randint(4, 7)):
                steps.append({'id': f's{i}', 'ms': rng.randint(20, 45), 'deps': []})
            previous = []
            for j in range(rng.randint(3, 4)):
                steps.append({'id': f'c{j}', 'ms': rng.randint(50, 90), 'deps': previous})
                previous = [f'c{j}']
        elif kind == 1:  # two chains of different length plus fillers, long chain listed last
            previous = []
            for j in range(2):
                steps.append({'id': f'a{j}', 'ms': rng.randint(30, 60), 'deps': previous})
                previous = [f'a{j}']
            for i in range(rng.randint(2, 4)):
                steps.append({'id': f'f{i}', 'ms': rng.randint(20, 40), 'deps': []})
            previous = []
            for j in range(rng.randint(4, 5)):
                steps.append({'id': f'b{j}', 'ms': rng.randint(40, 70), 'deps': previous})
                previous = [f'b{j}']
        else:  # random layered DAG
            layers, names = rng.randint(3, 4), []
            for layer in range(layers):
                current = []
                for i in range(rng.randint(1, 3)):
                    name = f'l{layer}n{i}'
                    deps = rng.sample(names[-1], k=min(len(names[-1]), rng.randint(1, 2))) if names else []
                    steps.append({'id': name, 'ms': rng.randint(20, 80), 'deps': deps})
                    current.append(name)
                names.append(current)
            rng.shuffle(steps)
        cases.append({'concurrency': concurrency, 'steps': steps})
    return {'cases': cases}


def salience(seed, count):
    rng = random.Random(seed)
    cases = []
    for index in range(count):
        events, important = [], []
        for i in range(rng.randint(6, 12)):
            name = f'important-{index}-{i}'
            source, modality = rng.choice([('screen', 'vision'), ('calendar', 'alert'), ('system', 'alert')])
            events.append({'dt': rng.uniform(.5, 3), 'source': source, 'modality': modality, 'content': name,
                           'salience': .95})
            important.append(name)
        for i in range(rng.randint(205, 260)):
            events.append({'dt': rng.uniform(.2, 1.5), 'source': 'sensor', 'modality': 'telemetry',
                           'content': f'noise-{index}-{i}', 'salience': rng.uniform(.05, .45)})
        cases.append({'events': events, 'important': important})
    return {'cases': cases}


def retry(seed, count):
    rng = random.Random(seed)
    cases = []
    for _ in range(count):
        cases.append({'recover_after_ms': rng.choice([rng.randint(20, 200), rng.randint(200, 1200), rng.randint(1200, 3500)]),
                      'attempt_ms': rng.randint(5, 40), 'attempts': rng.randint(3, 5), 'budget_ms': 4000})
    return {'cases': cases}


TOOL_QUERIES = [
    ('open my downloads folder', ['open', 'list_files']), ('find every pdf in my documents', ['search_files', 'list_files']),
    ('read the notes.txt file on my desktop', ['read_file']), ('create a new text file called ideas', ['create_file']),
    ('append a line to my todo list file', ['append_file']), ('delete the old draft file', ['delete_file']),
    ('search the web for the latest python release', ['web_search', 'google_search', 'searx_search', 'serp_search']),
    ('what is the weather in toronto tomorrow', ['realtime_query']), ('play some jazz on spotify', ['media_search']),
    ('pause the music', ['media_control']), ('close notepad', ['close_app']), ('launch blender', ['open', 'blender_task']),
    ('show my git status', ['git_status']), ('what changed in the last commit', ['git_log', 'git_diff']),
    ('write a python script that renames photos', ['write_code']), ('add unit tests for my parser', ['write_tests']),
    ('refactor this function to be faster', ['improve_code']), ('map the structure of this repository', ['repository_map']),
    ('search github for a markdown parser', ['github_search']), ('open a pull request on github', ['github_pull_request']),
    ('put 42 into cell B3 of budget.xlsx', ['office_xlsx', 'strategy_execute']), ('replace a paragraph in report.docx', ['office_docx', 'strategy_execute']),
    ('merge two pdf files', ['pdf_document', 'strategy_execute']), ('export the blender scene as glb', ['blender_task', 'strategy_execute']),
    ('open main.py in vs code at line 40', ['vscode_cli']), ('click the save button in the dialog', ['select', 'handle_dialog']),
    ('type my address into the form field', ['fill_text', 'type_text', 'browser_fill']), ('scroll down the page', ['scroll']),
    ('fill the login form in chrome', ['browser_fill', 'browser_inspect']), ('go to example.com in the browser', ['browser_navigate', 'browse']),
    ('scrape the article text from this page', ['scrape_web', 'firecrawl_scrape']), ('what tools can you use', ['runtime_capabilities', 'tool_search']),
    ('list the mcp servers', ['mcp_status', 'mcp_list_tools']), ('search my notes for the project plan', ['knowledge_search']),
    ('schedule a meeting on my calendar friday', ['calendar_create']), ('show my calendar events today', ['calendar_list']),
    ('send a slack message to the team', ['slack_send']), ('find jira tickets assigned to me', ['jira_search']),
    ('run the command ipconfig', ['run_command', 'windows_command']), ('which windows command shows the battery report', ['windows_command_search']),
    ('open the file menu in paint', ['open_menu']), ('save this document as final', ['save_file']),
    ('read these three files together', ['read_batch', 'read_file']), ('modify the config file to add a key', ['modify_file']),
    ('what integrations are connected', ['integration_status', 'toolkit_status']), ('check which skills you have', ['skill_list']),
    ('review this pull request', ['review_pull_request', 'github_pr_files']), ('research the history of the transistor', ['deerflow_research', 'web_search']),
    ('show the files changed in pull request 12', ['github_pr_files']), ('inspect the elements on this web page', ['browser_inspect']),
    ('search youtube for a cooking video', ['media_search']), ('skip to the next track', ['media_control']),
    ('find installed applications for video editing', ['application_search']), ('read my latest email', ['read_email']),
    ('create a jira ticket for the login bug', ['jira_create']), ('run my unreal engine export', ['unreal_task']),
    ('how should i automate this excel workbook', ['execution_methods', 'office_xlsx']), ('list the files in my projects folder', ['list_files']),
    ('look up crypto prices', ['realtime_query']), ('use the press shortcut ctrl s', ['shortcut']),
    ('think about the best plan for this', ['think']), ('learn this github repository', ['repository_learn']),
    ('explain the skill called weather', ['repository_skill_explain', 'skill_read']), ('reverse engineer this app', ['rea_status', 'rea_ingest', 'rea_analyze']),
    ('generate a sandboxed chart from data', ['deerflow_free_media', 'deerflow_sandbox_task']), ('summarize this repository instructions file', ['repository_instructions', 'read_file']),
    ('delete the event from my calendar', ['calendar_delete']), ('edit the jira issue description', ['jira_edit']),
    ('search for files named invoice', ['search_files']), ('tweet this announcement', ['twitter_send']),
    ('find people at a company with apollo', ['apollo_search']), ('crawl the docs site map', ['firecrawl_map']),
    ('query the knowledge resource about my vault', ['query_resource', 'knowledge_search']), ('send an email to my manager', ['send_email']),
    ('check the deerflow status', ['deerflow_status']), ('call an mcp tool', ['mcp_call']),
]

LESSONS = [
    {'label': 'xlsx-api', 'title': 'Spreadsheet cells', 'description': 'Edit workbook cells', 'content': 'Edit spreadsheet cells through the workbook API and read values back.', 'conditions': {'application': 'excel'}, 'confidence': .8},
    {'label': 'xlsx-gui', 'title': 'Spreadsheet cells by clicking', 'description': 'Older approach', 'content': 'Click spreadsheet cells and type values when no API exists.', 'conditions': {'application': 'excel', 'version': '2013'}, 'confidence': .5},
    {'label': 'docx', 'title': 'Document paragraphs', 'description': 'Word adapter', 'content': 'Change document paragraphs with the document adapter and confirm the text.', 'conditions': {'application': 'word'}, 'confidence': .7},
    {'label': 'pdf', 'title': 'PDF pages', 'description': 'Merge split', 'content': 'Merge or split pdf pages into a new file rather than editing the original.', 'conditions': {}, 'confidence': .7},
    {'label': 'blender4', 'title': 'Blender export', 'description': 'glTF binary', 'content': 'Export blender scenes as binary glb files from a disposable scene.', 'conditions': {'application': 'blender', 'version': '4'}, 'confidence': .75},
    {'label': 'blender3', 'title': 'Blender export legacy', 'description': 'glTF separate', 'content': 'Export blender scenes with the legacy gltf separate option.', 'conditions': {'application': 'blender', 'version': '3'}, 'confidence': .6},
    {'label': 'browser', 'title': 'Required form fields', 'description': 'Forms', 'content': 'Fill required form fields before pressing the submit control.', 'conditions': {'environment': 'browser'}, 'confidence': .7},
    {'label': 'spotify', 'title': 'Media controls', 'description': 'Playback', 'content': 'Use the media session controls to pause or skip tracks.', 'conditions': {}, 'confidence': .65},
    {'label': 'gmail', 'title': 'Email drafts first', 'description': 'Approval', 'content': 'Create an email draft first and wait for approval before sending mail.', 'conditions': {}, 'confidence': .8},
    {'label': 'vscode', 'title': 'Editor line jump', 'description': 'VS Code', 'content': 'Open source files at a line with the editor command line.', 'conditions': {'application': 'vscode'}, 'confidence': .7},
    {'label': 'git', 'title': 'Repository status first', 'description': 'Git', 'content': 'Inspect repository status before committing any change.', 'conditions': {}, 'confidence': .75},
    {'label': 'docker', 'title': 'Untrusted code', 'description': 'Sandbox', 'content': 'Run untrusted code only in the network-less container sandbox.', 'conditions': {}, 'confidence': .85},
    {'label': 'stale-weather', 'title': 'Weather scraping', 'description': 'Old lesson', 'content': 'Scrape weather pages for the forecast.', 'conditions': {}, 'confidence': .4, 'updated_at': '2024-01-01T00:00:00+00:00'},
    {'label': 'weather', 'title': 'Weather provider', 'description': 'Current lesson', 'content': 'Query the registered weather provider for the forecast instead of scraping pages.', 'conditions': {}, 'confidence': .8},
]
LESSON_QUERIES = [
    ('update numbers in my excel sheet cells', {'application': 'excel'}, 'xlsx-api'), ('type values into old excel cells', {'application': 'excel', 'version': '2013'}, 'xlsx-gui'),
    ('rewrite a paragraph of the word document', {'application': 'word'}, 'docx'), ('combine two pdf files', {}, 'pdf'),
    ('export my blender scene for a game', {'application': 'blender', 'version': '4'}, 'blender4'), ('export scene from blender 3', {'application': 'blender', 'version': '3'}, 'blender3'),
    ('the form says a field is required', {'environment': 'browser'}, 'browser'), ('skip this track', {}, 'spotify'),
    ('send an email for me', {}, 'gmail'), ('jump to a line in the editor', {'application': 'vscode'}, 'vscode'),
    ('commit my changes', {}, 'git'), ('run this downloaded code safely', {}, 'docker'),
    ('what is the weather forecast', {}, 'weather'), ('edit cells in a spreadsheet workbook', {'application': 'excel'}, 'xlsx-api'),
    ('blender glb export', {'application': 'blender', 'version': '4'}, 'blender4'), ('pause the song', {}, 'spotify'),
    ('change document text', {'application': 'word'}, 'docx'), ('split pages out of a pdf', {}, 'pdf'),
    ('fill the signup form fields', {'environment': 'browser'}, 'browser'), ('get tomorrow forecast', {}, 'weather'),
]

ROUTING = [
    ('plan my week step by step', 'planning'), ('organize the steps to set up a new laptop', 'planning'),
    ('first back up the folder and then compress it', 'planning'), ('prepare a workflow for publishing the video', 'planning'),
    ('fix the bug in my python script', 'coding'), ('write unit tests for the parser function', 'coding'),
    ('refactor the repository code', 'coding'), ('debug the stack trace in my code', 'coding'),
    ('click the export button in the window', 'ui_automation'), ('fill in the textbox in the dialog', 'ui_automation'),
    ('open the menu and click save', 'ui_automation'), ('scroll the window and click the tab', 'ui_automation'),
    ('explain how transformers work', 'knowledge'), ('research the history of rome', 'knowledge'),
    ('summarize my notes about the project', 'knowledge'), ('tell me about black holes', 'knowledge'),
    ('which tool should i use for this pdf', 'tool_selection'), ('what can you do with mcp integrations', 'tool_selection'),
    ('is there a skill or api adapter for excel', 'tool_selection'), ('best way to use a plugin for this', 'tool_selection'),
    ('it failed again with an error', 'error_recovery'), ('the export keeps failing, try again', 'error_recovery'),
    ('the app crashed and is stuck', 'error_recovery'), ('retry the broken download after the timeout', 'error_recovery'),
    ('hello there', None), ('good morning', None), ('thanks', None), ('ok', None),
    ('then after lunch schedule the review steps', 'planning'), ('compile the code and test it', 'coding'),
    ('click on the button labeled next', 'ui_automation'), ('look up the documentation for numpy', 'knowledge'),
    ('which tool can merge files', 'tool_selection'), ('that did not work, recover the file', 'error_recovery'),
    ('set up a multi step plan for moving house', 'planning'), ('find the function causing the bug', 'coding'),
    ('type my name in the field and press tab', 'ui_automation'), ('why is the sky blue', 'knowledge'),
    ('use the api instead of clicking', 'tool_selection'), ('the timeout error keeps happening', 'error_recovery'),
]

CHOICES = [
    ('I want to change cell B3 in budget.xlsx. Which tool is best?', {'A': 'office_xlsx', 'B': 'select', 'C': 'scroll', 'D': 'type_text'}, 'A'),
    ('I need to merge two PDF files. Which tool is best?', {'A': 'browse', 'B': 'pdf_document', 'C': 'fill_text', 'D': 'scroll'}, 'B'),
    ('Show the current git status. Which tool?', {'A': 'web_search', 'B': 'select', 'C': 'git_status', 'D': 'scroll'}, 'C'),
    ('Pause the music. Which tool?', {'A': 'media_control', 'B': 'delete_file', 'C': 'git_log', 'D': 'open_menu'}, 'A'),
    ('Find files named invoice. Which tool?', {'A': 'scroll', 'B': 'media_search', 'C': 'send_email', 'D': 'search_files'}, 'D'),
    ('Write tests for my parser. Which tool?', {'A': 'write_tests', 'B': 'calendar_list', 'C': 'scroll', 'D': 'close_app'}, 'A'),
    ('What is the weather tomorrow? Which tool?', {'A': 'open_menu', 'B': 'realtime_query', 'C': 'git_diff', 'D': 'append_file'}, 'B'),
    ('Export the Blender scene as GLB. Which tool?', {'A': 'scroll', 'B': 'type_text', 'C': 'blender_task', 'D': 'read_email'}, 'C'),
    ('Close Notepad. Which tool?', {'A': 'close_app', 'B': 'create_file', 'C': 'github_search', 'D': 'think'}, 'A'),
    ('Read notes.txt. Which tool?', {'A': 'slack_send', 'B': 'scroll', 'C': 'media_control', 'D': 'read_file'}, 'D'),
    ('Open main.py at line 40 in VS Code. Which tool?', {'A': 'vscode_cli', 'B': 'scroll', 'C': 'pdf_document', 'D': 'jira_search'}, 'A'),
    ('List my calendar events today. Which tool?', {'A': 'git_status', 'B': 'calendar_list', 'C': 'scroll', 'D': 'fill_text'}, 'B'),
    ('Search GitHub for a markdown parser. Which tool?', {'A': 'close_app', 'B': 'scroll', 'C': 'github_search', 'D': 'media_control'}, 'C'),
    ('Send a Slack message. Which tool?', {'A': 'slack_send', 'B': 'office_docx', 'C': 'scroll', 'D': 'git_log'}, 'A'),
    ('Replace a paragraph in report.docx. Which tool?', {'A': 'scroll', 'B': 'office_docx', 'C': 'media_search', 'D': 'close_app'}, 'B'),
    ('Run ipconfig. Which tool?', {'A': 'think', 'B': 'scroll', 'C': 'run_command', 'D': 'calendar_create'}, 'C'),
]


def split(rows, holdout_every=2):
    """Deterministic interleaved split: every second labelled row is held out."""
    return [r for i, r in enumerate(rows) if i % holdout_every], [r for i, r in enumerate(rows) if not i % holdout_every]


def build():
    train, heldout = {}, {}
    train['dag_makespan'], heldout['dag_makespan'] = dags(11, 9), dags(1011, 12)
    train['salience_retention'], heldout['salience_retention'] = salience(21, 6), salience(1021, 8)
    train['retry_recovery'], heldout['retry_recovery'] = retry(31, 40), retry(1031, 60)
    a, b = split(TOOL_QUERIES)
    train['tool_selection'] = {'cases': [{'query': q, 'expected': e} for q, e in a]}
    heldout['tool_selection'] = {'cases': [{'query': q, 'expected': e} for q, e in b]}
    a, b = split(LESSON_QUERIES)
    train['lesson_retrieval'] = {'lessons': LESSONS, 'cases': [{'query': q, 'conditions': c, 'label': l} for q, c, l in a]}
    heldout['lesson_retrieval'] = {'lessons': LESSONS, 'cases': [{'query': q, 'conditions': c, 'label': l} for q, c, l in b]}
    a, b = split(ROUTING)
    train['prompt_routing'] = {'cases': [{'goal': g, 'slot': s} for g, s in a]}
    heldout['prompt_routing'] = {'cases': [{'goal': g, 'slot': s} for g, s in b]}
    a, b = split(CHOICES)
    train['prompt_slots'] = {'model': 'qwen3.5:0.8b', 'cases': [{'question': q, 'choices': c, 'answer': x} for q, c, x in a]}
    heldout['prompt_slots'] = {'model': 'qwen3.5:0.8b', 'cases': [{'question': q, 'choices': c, 'answer': x} for q, c, x in b]}
    return train, heldout


def main():
    train, heldout = build()
    for folder, sets in (('train', train), ('heldout', heldout)):
        for name, data in sets.items():
            path = ROOT / folder / (name + '.json')
            if path.exists():
                raise SystemExit('Refusing to overwrite sealed data: ' + str(path))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8')
            print(path.relative_to(ROOT), len(data['cases']))


if __name__ == '__main__':
    main()
