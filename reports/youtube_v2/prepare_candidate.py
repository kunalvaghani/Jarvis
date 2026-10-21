"""Stage upstream sources and real-parent adapter without registering them.

Run from this repository. Originals remain untouched; repairs are separate diffs.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = Path(r'D:\Phython Project\Connectors\jarvis_youtube_connector')
DEST = HERE / 'candidate'


def main():
    if DEST.exists():
        raise SystemExit('Candidate already staged; preserve its repairs and use the saved upstream hashes/diff.')
    DEST.mkdir(exist_ok=True)
    hashes = {}
    for relative in ['youtube_connector/__init__.py', 'youtube_connector/base.py',
                     'youtube_connector/youtube.py', 'youtube_connector/youtube_v2.py',
                     'youtube_connector/data_api.py', 'COMMANDS.md', 'server.py']:
        original = SOURCE / relative
        target = DEST / ('upstream_server.py' if relative == 'server.py' else relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        hashes[relative] = hashlib.sha256(original.read_bytes()).hexdigest()
    shutil.copytree(SOURCE/'tests', DEST/'tests', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    inventory = []
    tree = ast.parse((SOURCE/'server.py').read_text(encoding='utf-8'))
    lines = ['"""Staged real Jarvis BaseConnector adapter; NOT registered/accepted."""',
             'import asyncio', 'import importlib.util', 'from pathlib import Path', 'import sys',
             'ROOT = Path(__file__).resolve().parents[3]',
             'PARENT = ROOT / "app/integrations/jarvis-connectors"',
             'sys.path.insert(0, str(PARENT))',
             'from jarvis_connector import tool, ToolError',
             'from youtube_connector.youtube_v2 import YouTubeConnector as Service',
             'from youtube_connector.base import ConnectorError',
             'spec = importlib.util.spec_from_file_location("youtube_installed_baseline", PARENT/"connectors/apps/youtube/server.py")',
             'legacy = importlib.util.module_from_spec(spec)',
             'spec.loader.exec_module(legacy)', '',
             'class YouTubeConnector(legacy.YouTubeConnector):',
             '    """Five installed lookup tools plus 103 staged supplied tools."""',
             '    version = "2.0.0-candidate"',
             '    def __init__(self, page=None, allow_write=False):',
             '        super().__init__(allow_write=allow_write)',
             '        self.loop = asyncio.new_event_loop()',
             '        self.service = Service(page=page, profile_dir=str(ROOT/"app/.jarvis-runtime/youtube-v2-disabled"))',
             '        if page is None:',
             '            async def refuse_browser():',
             '                raise ConnectorError("Chrome Default profile only: browser Page adapter is not accepted; no alternate profile was opened")',
             '            self.service.connect = refuse_browser',
             '    def dispatch(self, operation, arguments):',
             '        try:',
             '            return self.loop.run_until_complete(getattr(self.service, operation)(**arguments))',
             '        except ConnectorError as exc:',
             '            raise ToolError(str(exc)) from None',
             '    def close_service(self):',
             '        self.loop.run_until_complete(self.service.close())',
             '        self.loop.close()', '']
    reads = {'health', 'get_status', 'media_status', 'queue_list', 'queue_status',
             'get_page_diagnostics', 'search_videos', 'search_playlists', 'search_channels',
             'search_videos_filtered'}
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        operation = node.body[-1].value.value.func.attr
        access = 'read' if operation in reads or operation.startswith('get_') else 'write'
        arguments = ', '.join(f'{arg.arg!r}: {arg.arg}' for arg in node.args.args)
        signature = ast.unparse(node.args)
        lines += [f'    @tool(access={access!r})',
                  f'    def {node.name}(self{", " if signature else ""}{signature}) -> dict:',
                  f'        {ast.get_docstring(node)!r}',
                  f'        return self.dispatch({operation!r}, {{{arguments}}})', '']
        inventory.append(dict(name=node.name, method=operation, signature=signature, access=access,
                              source='supplied', unit='catalog only; see test-specific evidence',
                              live_standalone='unaccepted', live_jarvis='not run'))
    lines += ['if __name__ == "__main__":', '    YouTubeConnector.main()']
    (DEST/'server.py').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    (HERE/'upstream-sha256.json').write_text(json.dumps(hashes, indent=2)+'\n')
    (HERE/'command-inventory.json').write_text(json.dumps(inventory, indent=2)+'\n')

if __name__ == '__main__':
    main()
