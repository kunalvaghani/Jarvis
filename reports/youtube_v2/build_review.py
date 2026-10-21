"""Build bounded review artifacts; never modifies runtime or connector registration."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
inventory = json.loads((HERE/'command-inventory.json').read_text())
catalog = json.loads((HERE/'candidate-contract-elevated.json').read_text(encoding='utf-8-sig'))
old = {'search_videos','search_playlists','video_details','playlist_videos','parse_link'}
supplied_legacy = {'youtube_search_videos','youtube_search_playlists','youtube_play_video','youtube_play_playlist',
                   'youtube_pause','youtube_resume','youtube_next','youtube_previous','youtube_status'}
text = ['# Command acceptance matrix — 2026-10-21', '',
        'Staged real-stdio discovery is distinct from active registration and live acceptance. '
        'All 103 supplied handler dispatch contracts are tested with mocks; selected semantic tests are additional. '
        'The existing profile media route has live pause/resume/status evidence, but these prefixed MCP calls have not run through Jarvis.', '',
        '| Command | Existing vs New | Unit | Live Standalone | Live Through Jarvis | Status | Evidence |',
        '|---|---|---|---|---|---|---|']
for row in catalog:
    name = row['name']
    kind = 'Installed' if name in old else 'Supplied legacy' if name in supplied_legacy else 'New'
    unit = 'Existing baseline' if name in old else 'Typed dispatch; selected behavior'
    evidence = '[Baseline](baseline-pytest.log)' if name in old else '[Tests](candidate-tests.log), [wire](candidate-wire.json)'
    text.append(f'| `{name}` | {kind} | {unit} | Candidate not live accepted | Expanded MCP not run | '
                f'{"Installed; unchanged" if name in old else "STAGED / acceptance pending"} | {evidence} |')
(HERE/'coverage.md').write_text('\n'.join(text)+'\n', encoding='utf-8')

tracked = subprocess.check_output(['git','diff','--name-only','--','README.md','app'],cwd=ROOT,text=True).splitlines()
tracked = [p for p in tracked if p!='app/artifacts/jarvis-audit/blender-connector/natural-language-fixture.json']
patch = subprocess.check_output(['git','diff','--no-ext-diff','--',*tracked],cwd=ROOT).decode('utf-8')
new_sources = [ROOT/'app/tests/test_youtube_profile_lock.py', *sorted((HERE/'candidate').rglob('*.py'))]
for path in new_sources:
    relative = path.relative_to(ROOT).as_posix()
    content = path.read_text(encoding='utf-8').splitlines(keepends=True)
    if content and not content[-1].endswith('\n'):
        content[-1] += '\n'
    patch += f'diff --git a/{relative} b/{relative}\nnew file mode 100644\n'
    patch += ''.join(difflib.unified_diff([],content,fromfile='/dev/null',tofile='b/'+relative))
(HERE/'source.patch').write_text(patch,encoding='utf-8',newline='\n')
hashes = {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
          for path in [*(ROOT/p for p in tracked), *new_sources]}
(HERE/'review-source-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n', encoding='utf-8')

diffs = []
for relative in json.loads((HERE/'upstream-sha256.json').read_text()):
    original = Path(r'D:\Phython Project\Connectors\jarvis_youtube_connector')/relative
    candidate = HERE/'candidate'/('upstream_server.py' if relative=='server.py' else relative)
    diffs.extend(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(True),
        candidate.read_text(encoding='utf-8').splitlines(True),fromfile='upstream/'+relative,tofile='candidate/'+relative))
(HERE/'upstream-repairs.diff').write_text(''.join(diffs),encoding='utf-8')
