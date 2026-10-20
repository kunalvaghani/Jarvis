"""Mutation controls in the disposable baseline checkout; restore every source byte."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
TARGET = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-codex-v2-baseline/app')
assert TARGET.name == 'app' and TARGET.parent.name == 'Jarvis-codex-v2-baseline'
cases = [
 ('permission', 'jarvis/agent_events.py', "if name in denied or '*' in denied:", "if False and (name in denied or '*' in denied):",
  'tests/test_prompt36_observability.py::test_JRV_36_011_unavailable_telemetry_cannot_override_deny_policy'),
 ('false_tool_success', 'jarvis/skill_evolution.py', "verified = bool(outcome and outcome[-1].get('verification') == 'verified')", 'verified = True',
  'tests/test_prompt35_security.py::test_JRV_35_008_021_tool_success_cannot_override_independent_readback'),
 ('stale_selector', 'jarvis/ui_controls.py', 'if pending["handle"] != handle or pending["signature"] != snapshot["signature"]:', 'if pending["handle"] != handle:',
  'tests/test_ui_controls.py::UITests::test_changed_controls_invalidate_number'),
 ('disabled_verify', 'jarvis/dag_execution.py', 'if tool.verify(arguments, output) is not True:', 'if False:',
  'tests/test_hierarchical.py::DAGTests::test_read_retry_backoff_and_failure_propagation'),
 ('heldout_tamper', 'evolution_eval/gate.py', 'if changed:', 'if False and changed:',
  'tests/test_phase06_controlled_evolution.py::test_P06_gate_refuses_when_its_policy_or_heldout_data_are_tampered'),
 ('duplicate_write', 'jarvis/dag_execution.py', "elif old.get('status') != 'pending' and not self.tools[step.tool].read_only:",
  "elif False and old.get('status') != 'pending' and not self.tools[step.tool].read_only:",
  'tests/test_phase08_integration.py::test_P08_flow_E_cancellation_and_restart_resume_without_replaying_effects'),
]
saved = {}
rows = []
def sha(data): return hashlib.sha256(data).hexdigest()
def check(label, node):
    xml = OUT / ('mutation-' + label + '.xml')
    start = time.perf_counter()
    done = subprocess.run([sys.executable, '-B', '-m', 'pytest', node, '-q', '--junitxml=' + str(xml)],
        cwd=TARGET, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (OUT / ('mutation-' + label + '.txt')).write_bytes(done.stdout)
    tree = ET.parse(xml).getroot()
    failed = [c for c in tree.iter('testcase') if c.find('failure') is not None]
    errors = [c for c in tree.iter('testcase') if c.find('error') is not None]
    return {'returncode': done.returncode, 'assertion_failures': len(failed), 'errors': len(errors),
        'seconds': time.perf_counter() - start, 'xml': xml.name}
try:
    # Candidate mirror, never the live source. Test fixtures/imports remain explicit.
    for directory in ['jarvis', 'scripts', 'evolution_eval', 'tests']:
        for source in (APP / directory).rglob('*.py'):
            rel = source.relative_to(APP)
            target = TARGET / rel
            if target.exists() and target.read_bytes() == source.read_bytes(): continue
            saved[rel.as_posix()] = target.read_bytes() if target.exists() else None
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for name, path, before, after, node in cases:
        target = TARGET / path
        original = target.read_bytes()
        text = original.decode('utf-8')
        assert text.count(before) == 1, (name, text.count(before))
        control = check(name + '-control', node)
        assert control['returncode'] == 0, (name, control)
        try:
            target.write_bytes(text.replace(before, after, 1).encode('utf-8'))
            # Avoid import cache timestamp/size ambiguity, without deleting files.
            import os
            stamp = time.time() + 10
            os.utime(target, (stamp, stamp))
            mutant = check(name, node)
            killed = mutant['returncode'] == 1 and mutant['assertion_failures'] > 0 and mutant['errors'] == 0
            rows.append({'id': name, 'test': node, 'control': control, 'mutant': mutant, 'killed': killed,
                'candidate_sha256': sha(original), 'mutant_sha256': sha(target.read_bytes()),
                'scope': 'disposable checkout; synthetic/owned fixtures only'})
        finally:
            target.write_bytes(original)
            stamp = time.time() + 20
            os.utime(target, (stamp, stamp))
        assert target.read_bytes() == original
finally:
    for relative, content in saved.items():
        target = TARGET / relative
        if content is not None: target.write_bytes(content)
        # Added independent tests remain as documented test-only overlays; no deletion.
    (OUT / 'mutation-results.json').write_text(json.dumps({'mutants': rows,
        'tracked_original_bytes_restored': all((TARGET / p).read_bytes() == content for p, content in saved.items() if content is not None),
        'added_tests_retained_as_owned_overlay': True}, indent=2), encoding='utf-8')
print(json.dumps({'mutants': len(rows), 'killed': sum(r['killed'] for r in rows)}))
