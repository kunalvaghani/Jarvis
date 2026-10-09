"""Copy reviewed Python classes and notices; never run upstream setup code."""
import ast
import json
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parents[2]
UPSTREAM = BASE / 'integrations/execution-upstream'
DEST = BASE / 'integrations/execution-primitives'


def build():
    DEST.mkdir(parents=True, exist_ok=True)
    source = UPSTREAM / 'windows-mcp/src/windows_mcp/uia/patterns.py'
    code = source.read_text(encoding='utf-8')
    classes = {'InvokePattern', 'ValuePattern', 'SelectionItemPattern',
               'TogglePattern', 'ExpandCollapsePattern', 'ScrollPattern'}
    selected = []
    omitted = {'SelectionContainer', 'SetToggleState'}
    for node in ast.parse(code).body:
        if not isinstance(node, ast.ClassDef) or node.name not in classes:
            continue
        lines = code.splitlines()
        methods = []
        for method in node.body:
            if not isinstance(method, ast.FunctionDef) or method.name in omitted:
                continue
            start = min([method.lineno, *[decorator.lineno for decorator in method.decorator_list]]) - 1
            methods.append('\n'.join(lines[start:method.end_lineno]))
        selected.append('class ' + node.name + ':\n' + '\n\n'.join(methods))
    if len(selected) != len(classes):
        raise ValueError('The pinned source does not contain the reviewed pattern classes.')
    header = '''"""Windows-MCP UIA pattern subset. Author: yinkaisheng.
Original UIAutomation library: Apache-2.0; Windows-MCP changes: MIT.
See source-manifest.json and licenses/. Selected class methods are intact except
HRESULT success normalization (comtypes can return None) and a zero default wait.
SelectionContainer (unvendored Control dependency) and SetToggleState (may issue
multiple Toggle calls) are omitted. No framework/server is imported.
"""
from __future__ import annotations
import time
from typing import List, TYPE_CHECKING
S_OK = 0
OPERATION_WAIT_TIME = 0

'''
    output = header + '\n\n'.join(selected) + '\n'
    output = output.replace(' == S_OK', ' in (None, S_OK)')
    (DEST / 'windows_mcp_patterns.py').write_text(output, encoding='utf-8')
    (BASE / 'jarvis/upstream_windows_patterns.py').write_text(output, encoding='utf-8')
    licenses = DEST / 'licenses'
    licenses.mkdir(exist_ok=True)
    for name, path in {'UFO-MIT.txt': 'ufo/LICENSE', 'Windows-MCP-MIT.txt': 'windows-mcp/LICENSE.md',
                       'CUA-MIT.txt': 'cua/LICENSE.md', 'Open-Computer-Use-MIT.txt': 'open-computer-use/LICENSE',
                       'Agent-S-Apache-2.0.txt': 'agent-s/LICENSE',
                       'UIAutomation-Apache-2.0.txt': 'agent-s/LICENSE'}.items():
        shutil.copyfile(UPSTREAM / path, licenses / name)
    shutil.copyfile(UPSTREAM / 'cua/libs/cua-driver/rust/THIRD_PARTY_NOTICES.md',
                    licenses / 'CUA-Driver-THIRD-PARTY-NOTICES.md')
    inventory = json.loads((DEST / 'source-inventory.json').read_text(encoding='utf-8'))
    source_paths = {
        'ufo': ['ufo/automator/ui_control/controller.py'],
        'windows-mcp': ['src/windows_mcp/uia/patterns.py'],
        'cua': ['libs/cua-driver/rust/crates/platform-windows/src/tools/page_bookmark.rs'],
        'open-computer-use': ['apps/OpenComputerUseWindows/native_actions.go'],
        'agent-s': ['gui_agents/s1/aci/WindowsOSACI.py']}
    rows = []
    for repo in inventory['repositories']:
        rows.append({key: repo[key] for key in ('priority', 'name', 'url', 'revision', 'source_files', 'symbol_count')})
        rows[-1].update({'reviewed_sources': source_paths[repo['name']],
                         'mode': 'vendored pattern classes' if repo['name'] == 'windows-mcp' else 'reviewed Python adaptation/port'})
        rows[-1]['reviewed_source_hashes'] = {row['path']: row['sha256'] for row in repo['files']
                                           if row['path'] in source_paths[repo['name']]}
    (DEST / 'source-manifest.json').write_text(json.dumps({'repositories': rows,
        'runtime': 'jarvis.execution_adapters inside existing owned jarvis.ui_worker',
        'modifications': ['No swallowed action errors or retry after input.', 'Fresh identity/focus/read-only/password admission.',
                          'Windows-MCP subset copied without Python 3.14 MCP server dependencies; no telemetry.',
                          'Windows-MCP SelectionContainer and multi-toggle SetToggleState are omitted.',
                          'Cua/OCU primitives ported from Rust/Go; full SDKs are not installed.',
                          'Agent-S ordered accessible-target adaptation uses Jarvis role-aware native patterns; earlier centre mouse click removed on 2026-10-08; no exec of generated scripts.',
                          'All original-framework non-Windows/model/server/build code remains source inventory, not enabled runtime.']}, indent=2) + '\n', encoding='utf-8')
    print('Vendored six UIA pattern classes and six license notices.')


if __name__ == '__main__':
    build()
