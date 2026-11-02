"""What each existing capability consumes and produces: the explicit port contracts of the brain.

Explicit rows were written by reading each tool's code and description (2026-11-02). A tool with no row gets a
*derived* contract: its side-effect class comes from a name heuristic and its ports are generic, so it can be
ranked and called as today but never auto-wires a synapse. Unknown side effects are denied until reviewed.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

# name: (inputs, outputs, side_effect_class, runtime). A port is "name:Type", "name:Type?" when optional.
Contract = Tuple[Tuple[str, ...], Tuple[str, ...], str, str]

TOOLS: Dict[str, Contract] = {
    # Research and the web (read-only by contract; consequential clicks are gated inside the adapter).
    'web_search': (('query:Query',), ('results:SearchResults',), 'read_only', 'network'),
    'google_search': (('query:Query',), ('results:SearchResults',), 'read_only', 'network'),
    'serp_search': (('query:Query',), ('results:SearchResults',), 'read_only', 'network'),
    'searx_search': (('query:Query',), ('results:SearchResults',), 'read_only', 'network'),
    'firecrawl_search': (('query:Query',), ('results:SearchResults',), 'read_only', 'network'),
    'github_search': (('query:Query',), ('results:SearchResults',), 'read_only', 'network'),
    'scrape_web': (('url:Url', 'results:SearchResults?'), ('page:WebPage',), 'read_only', 'network'),
    'firecrawl_scrape': (('url:Url', 'results:SearchResults?'), ('page:WebPage',), 'read_only', 'network'),
    'firecrawl_map': (('url:Url',), ('results:SearchResults',), 'read_only', 'network'),
    'deerflow_web_research': (('query:Query',), ('report:Report',), 'read_only', 'network'),
    'deerflow_research': (('query:Query',), ('report:Report',), 'read_only', 'local_or_network'),
    'realtime_query': (('query:Query',), ('answer:Answer',), 'read_only', 'network'),
    'web_open': (('url:Url', 'results:SearchResults?'), ('page:WebPage',), 'ui_or_media_state', 'network'),
    'web_read': (('page:WebPage?',), ('page:WebPage',), 'read_only', 'local'),
    'web_act': (('page:WebPage', 'action:PageAction'), ('page:WebPage',), 'ui_or_media_state', 'network'),
    'browse': (('url:Url',), ('status:Status',), 'ui_or_media_state', 'local'),
    'browser_search': (('query:Query',), ('status:Status',), 'ui_or_media_state', 'local'),
    # Windows apps (UI Automation first, local vision last).
    'app_open': (('app:AppName',), ('window:WindowRefs',), 'ui_or_media_state', 'local'),
    'app_read': (('window:WindowRefs?',), ('window:WindowRefs',), 'read_only', 'local'),
    'app_act': (('window:WindowRefs', 'action:UiAction'), ('window:WindowRefs',), 'ui_or_media_state', 'local'),
    'screen_act': (('target:ScreenTarget',), ('window:WindowRefs',), 'ui_or_media_state', 'local'),
    'type_text': (('window:WindowRefs', 'text:Text'), ('status:Status',), 'ui_or_media_state', 'local'),
    'control_check': ((), ('status:Status',), 'read_only', 'local'),
    'application_inspect': (('app:AppName',), ('window:WindowRefs',), 'read_only', 'local'),
    # Files (exact paths inside approved roots).
    'read_file': (('path:FilePath',), ('text:FileText',), 'read_only', 'local'),
    'read_batch': (('path:FilePath',), ('text:FileText',), 'read_only', 'local'),
    'list_files': (('folder:FolderPath',), ('listing:FolderListing',), 'read_only', 'local'),
    'search_files': (('query:Query',), ('listing:FolderListing',), 'read_only', 'local'),
    'create_file': (('folder:FolderPath', 'name:Text', 'text:FileText'), ('path:FilePath',), 'local_write', 'local'),
    'modify_file': (('path:FilePath', 'text:FileText'), ('path:FilePath',), 'local_write', 'local'),
    'append_file': (('path:FilePath', 'text:FileText'), ('path:FilePath',), 'local_write', 'local'),
    'delete_file': (('path:FilePath',), ('status:Status',), 'destructive', 'local'),
    'run_command': (('command:CommandLine',), ('output:CommandOutput',), 'local_write', 'local'),
    # Media connectors (playback state is the user's own UI state).
    'media_search': (('query:MediaQuery',), ('media:MediaState',), 'ui_or_media_state', 'local'),
    'media_control': (('media:MediaState',), ('media:MediaState',), 'ui_or_media_state', 'local'),
    # Documents and 3D (read or write per operation: split per operation before they can be auto-wired).
    'office_docx': (('plan:Plan',), ('document:Document',), 'operation_dependent', 'local'),
    'office_xlsx': (('plan:Plan',), ('sheet:Spreadsheet',), 'operation_dependent', 'local'),
    'pdf_document': (('path:FilePath',), ('pdf:Pdf',), 'operation_dependent', 'local'),
    'blender_task': (('plan:Plan',), ('scene:BlendScene',), 'operation_dependent', 'local'),
    # Code.
    'think': (('goal:Goal',), ('plan:Plan',), 'read_only', 'local'),
    'write_spec': (('goal:Goal',), ('plan:Plan',), 'read_only', 'local'),
    'write_code': (('plan:Plan',), ('code:Code',), 'local_write', 'local'),
    'write_tests': (('code:Code',), ('code:Code',), 'local_write', 'local'),
    'improve_code': (('code:Code', 'verdict:Verdict?'), ('patch:CodePatch',), 'local_write', 'local'),
    'repository_map': (('folder:FolderPath',), ('repo:Repository',), 'read_only', 'local'),
    'git_status': (('repo:Repository',), ('status:Status',), 'read_only', 'local'),
    'git_diff': (('repo:Repository',), ('patch:CodePatch',), 'read_only', 'local'),
    'git_log': (('repo:Repository',), ('report:Report',), 'read_only', 'local'),
    'development_verify': (('repo:Repository',), ('report:TestReport',), 'local_write', 'local'),
    # Memory and knowledge.
    'knowledge_search': (('query:Query',), ('hits:MemoryHits',), 'read_only', 'local'),
    # Messages and accounts (external writes: approval every time, never learnable).
    'read_email': (('query:Query',), ('message:Message',), 'read_only', 'network'),
    'send_email': (('draft:EmailDraft',), ('message:Message',), 'external_write', 'network'),
    'slack_send': (('text:Text',), ('message:Message',), 'external_write', 'network'),
    'twitter_send': (('text:Text',), ('message:Message',), 'external_write', 'network'),
    'calendar_list': (('query:Query',), ('event:CalendarEvent',), 'read_only', 'network'),
    'calendar_create': (('event:CalendarEvent',), ('event:CalendarEvent',), 'external_write', 'network'),
    'calendar_delete': (('event:CalendarEvent',), ('status:Status',), 'destructive', 'network'),
    'mcp_list_tools': (('query:Query?',), ('tools:ToolList',), 'read_only', 'local'),
}

# Brain-owned neurons wrapping existing modules (sensors, cortex, memory, motor) and upgrade v2 fixed routes.
# name: (kind, provider, inputs, outputs, side_effect_class, tool or None, description)
CORE: Dict[str, Tuple[str, str, Tuple[str, ...], Tuple[str, ...], str, str, str]] = {
    'sensor.text.input': ('sensor', 'jarvis.engine.Engine.feed', (), ('goal:Goal',), 'read_only', '',
                          'A typed or spoken request becomes a goal signal.'),
    'sensor.speech.final': ('sensor', 'jarvis.voice_runtime', (), ('goal:Goal',), 'read_only', '',
                            'A final speech transcript becomes a goal signal.'),
    'cortex.intent.classify': ('skill', 'jarvis.neural.router (deterministic)', ('goal:Goal',),
                               ('plan:Plan',), 'read_only', '', 'Deterministic intent and needed data types.'),
    'cortex.planner.legacy': ('model', 'jarvis.brain.Brain.run', ('goal:Goal',), ('answer:Answer',),
                              'operation_dependent', '', 'Today\'s planner loop (9B tool-calling), wrapped whole.'),
    'memory.search': ('memory', 'jarvis.memory_index', ('query:Query',), ('hits:MemoryHits',), 'read_only', '',
                      'Search verified memories (read-only).'),
    'memory.commit_episode': ('memory', 'jarvis.neural.journal', ('episode:Episode',), ('status:Status',),
                              'read_only', '', 'Record the verified trace of a goal in the brain journal.'),
    'motor.report': ('skill', 'jarvis.neural.adapters (report)', ('report:Report', 'verdict:Verdict'),
                     ('answer:Answer',), 'read_only', '', 'Tell the user the result together with its check.'),
    # Brain-native neurons of the Phase 2 vertical slices (jarvis/neural/adapters.py).
    'skill.research.pick_source': ('skill', 'jarvis.neural.adapters (pick source)', ('results:SearchResults',),
                                   ('url:Url',), 'read_only', '', 'Choose the most useful result link to read.'),
    'skill.research.analyse': ('skill', 'jarvis.neural.adapters (analyse)', ('query:Query', 'page:WebPage'),
                               ('report:Report',), 'read_only', '', 'Answer from the page only (local model).'),
    'verifier.report_grounded': ('verifier', 'jarvis.neural.adapters (grounded)', ('report:Report', 'page:WebPage'),
                                 ('verdict:Verdict',), 'read_only', '', 'Numbers and wording appear in the source.'),
    'skill.code.inspect': ('skill', 'jarvis.neural.adapters (inspect)', ('folder:FolderPath',),
                           ('repo:Repository',), 'read_only', '', 'Read the Python files and tests of one folder.'),
    'skill.code.patch': ('skill', 'jarvis.neural.adapters (patch)', ('repo:Repository', 'goal:Goal',
                                                                     'verdict:Verdict?'),
                         ('patch:CodePatch',), 'read_only', '', 'Propose whole-file fixes; tests are never edited.'),
    'skill.code.test': ('skill', 'jarvis.neural.adapters (test)', ('repo:Repository', 'patch:CodePatch?'),
                        ('report:TestReport',), 'local_write', '',
                        'Run the folder tests on a scratch copy (with the patch, if any).'),
    'verifier.tests_pass': ('verifier', 'jarvis.neural.adapters (tests pass)', ('report:TestReport',),
                            ('verdict:Verdict',), 'read_only', '', 'Every test ran and passed.'),
    'skill.code.apply': ('skill', 'jarvis.neural.adapters (apply)', ('repo:Repository', 'patch:CodePatch',
                                                                     'verdict:Verdict'),
                         ('repo:Repository',), 'local_write', '', 'Write the checked fix; old text kept for rollback.'),
    'skill.code.summarise': ('skill', 'jarvis.neural.adapters (summarise)', ('patch:CodePatch', 'verdict:Verdict'),
                             ('report:Report',), 'read_only', '', 'Say what changed, as a short diff.'),
    'route.calculator': ('route', 'jarvis.fast_routes (calculator)', ('calc:Calculation',), ('answer:Answer',),
                         'ui_or_media_state', '', 'Calculator typed once, display read back.'),
    'route.web_question': ('route', 'jarvis.fast_routes (site question)', ('url:Url', 'query:Query'),
                           ('answer:Answer',), 'read_only', '', 'Read a page fully; numbers must be grounded.'),
    'route.small_program': ('route', 'jarvis.small_program', ('plan:Plan',), ('code:Code',), 'local_write', '',
                            'One-file program checked against a reference program.'),
    'route.small_edit': ('route', 'jarvis.small_edit', ('path:FilePath', 'plan:Plan'), ('code:Code',),
                         'local_write', '', 'One-file edit checked by output and function agreement.'),
    'route.web_app': ('route', 'jarvis.web_app', ('plan:Plan', 'verdict:Verdict?'), ('code:Code',), 'local_write',
                      '', 'Web app built, checked in headless Chrome, repaired.'),
    'route.blender_live': ('route', 'jarvis.blender_live', ('plan:Plan', 'verdict:Verdict?'),
                           ('scene:BlendScene',), 'local_write', '', 'Model built live in a visible Blender.'),
    'route.blender_wireframe': ('route', 'jarvis.blender_live (wireframe)', ('plan:Plan',),
                                ('wireframe:Wireframe',), 'local_write', '',
                                'Wireframe blockout shown for approval before the full model.'),
    'verifier.text_file_saved': ('verifier', 'jarvis.learning.verifiers.text_file', ('path:FilePath',
                                                                                     'expected:FileText?'),
                                 ('verdict:Verdict',), 'read_only', '', 'Sealed: file saved with the exact text.'),
    'verifier.blender_object': ('verifier', 'jarvis.learning.verifiers.blender_object', ('scene:BlendScene',),
                                ('verdict:Verdict',), 'read_only', '', 'Sealed: object in the saved scene.'),
    'verifier.blender_scene': ('verifier', 'jarvis.learning.verifiers.blender_scene', ('scene:BlendScene',),
                               ('verdict:Verdict',), 'read_only', '', 'Sealed: shapes, head, human, car, house.'),
    'verifier.python_project': ('verifier', 'jarvis.learning.verifiers.python_project', ('code:Code',),
                                ('verdict:Verdict',), 'read_only', '', 'Sealed: program runs with expected output.'),
    'verifier.goal': ('verifier', 'jarvis.brain (goal check)', ('answer:Answer',), ('verdict:Verdict',),
                      'read_only', '', 'Independent end-of-goal check against the request.'),
}

TOKEN = r'(?:^|_)(?:{})(?:_|$)'
READ = re.compile(TOKEN.format('read|list|lists|search|get|inspect|status|find|check|describe|show|query|lookup|details|'
                               'map|log|diff|explain|health|ledger|instructions|tracks|albums|chapters|episodes|artists|'
                               'profile|devices|top|projects|files|methods|scrape|think|review|feedback|parse|videos|'
                               'playlists|playlist|capability|knowledge|application|repository|research|web|mcp_list'), re.I)
DESTRUCTIVE = re.compile(TOKEN.format('delete|remove|trash|purge|destroy|uninstall|drop'), re.I)
EXTERNAL = re.compile(TOKEN.format('send|post|reply|tweet|publish|email|gmail|slack|jira|github|calendar|apollo|issue|'
                                   'comment|purchase|order|pay|pull_request'), re.I)
CONTROL = re.compile(TOKEN.format('next|previous|seek|shuffle|repeat|resume|toggle|queue|transfer|mute|scroll|shortcut|'
                                  'navigate|dialog|close|browse|media|control|volume|play|pause|skip|command'), re.I)
WRITE = re.compile(TOKEN.format('create|modify|append|write|save|set|update|edit|act|type|click|select|fill|move|rename|'
                                'copy|open|launch|run|install|apply|promote|rollback|start|stop|add|commit|expand|record|'
                                'ingest|learn|lifecycle|improve|sandbox'), re.I)
OPERATION_TOOLS = frozenset({'office_xlsx', 'office_docx', 'pdf_document', 'office_automation', 'blender_task',
                             'unreal_task', 'vscode_cli', 'strategy_execute', 'deerflow_sandbox_task',
                             'deerflow_free_media', 'mcp_call'})


def side_effect(name: str, approval: str = 'none') -> str:
    """Name heuristic for tools without an explicit contract (labelled ``derived``)."""
    if name in TOOLS:
        return TOOLS[name][2]
    if name in OPERATION_TOOLS:
        return 'operation_dependent'
    if DESTRUCTIVE.search(name):
        return 'destructive'
    if EXTERNAL.search(name) and (approval != 'none' or WRITE.search(name)):
        return 'external_write'
    if CONTROL.search(name):
        return 'ui_or_media_state'
    if WRITE.search(name) or approval != 'none':
        return 'local_write'
    if READ.search(name):
        return 'read_only'
    return 'unknown'
