"""Claude's repair verification for P32-001, P32-002, P33-001, P33-002 and P33-003 (complements Codex's tests)."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

BASE = Path(__file__).resolve().parents[1]


# ---- P32-001: termination authority only for the launched process tree ----------------------------------------------
@pytest.mark.skipif(os.name != 'nt', reason='BLOCKED: native Windows ownership test')
def test_P32_001_real_descendant_is_accepted_and_only_it_is_terminated(tmp_path):
    from jarvis.harness_process import OwnedJob, hidden_spawn
    from jarvis.launcher import OwnedApplication
    marker = tmp_path / 'grandchild.pid'
    # Like the Windows venv redirector: the launched process starts the real interpreter as its child.
    script = ('import subprocess,sys,time;from pathlib import Path;'
              'c=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
              'Path(sys.argv[1]).write_text(str(c.pid));time.sleep(30)')
    job = OwnedJob()
    try:
        child = hidden_spawn(job, subprocess.Popen)([sys.executable, '-c', script, str(marker)],
                                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        until = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < until:
            time.sleep(.02)
        grandchild = int(marker.read_text())
        owner = OwnedApplication(child)
        owner.attach(grandchild)
        assert owner.handle and owner.owned[0] == grandchild
        owner.terminate()
        import psutil
        until = time.monotonic() + 5
        def alive(pid):
            try:
                return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                return False
        while alive(grandchild) and time.monotonic() < until:
            time.sleep(.05)
        assert not alive(grandchild)
        owner.close()
    finally:
        job.close()


@pytest.mark.skipif(os.name != 'nt', reason='BLOCKED: native Windows ownership test')
@pytest.mark.parametrize('pid', [0, -5, 'abc', 4, 2 ** 31 - 1])
def test_P32_001_invalid_system_or_dead_pids_are_refused(pid):
    from jarvis.launcher import OwnedApplication
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
    try:
        owner = OwnedApplication(child)
        with pytest.raises(ValueError):
            owner.attach(pid)
        assert owner.handle is None
    finally:
        child.kill()
        child.wait(5)


# ---- P32-002: repair log privacy ------------------------------------------------------------------------------------
def test_P32_002_secrets_are_screened_before_truncation_and_on_read(tmp_path):
    from jarvis.recovery import record, safe_message
    long_prefix = 'x ' * 600
    for message in (long_prefix + 'token=SYNTHETIC_LATE_CANARY_0123456789',
                    'line one\napi_key\n=\nSYNTHETIC_MULTILINE_CANARY_0123456789',
                    'fetch https://user:SYNTHETIC_URL_CANARY@host.example/x?key=SYNTHETIC_QUERY_CANARY',
                    'Authorization: Bearer SYNTHETIC_BEARER_CANARY_0123456789'):
        record(tmp_path, message)
    text = (tmp_path / '.jarvis-runtime/repairs.jsonl').read_text(encoding='utf-8')
    assert 'SYNTHETIC' not in text and all(len(json.loads(r)['message']) <= 300 for r in text.splitlines())
    assert safe_message('Ollama was stopped and fixed. No previous actions were replayed.') == \
        'Ollama was stopped and fixed. No previous actions were replayed.'  # useful diagnostics survive
    assert 'safe_message(json.loads(line)["message"])' in (BASE / 'main.py').read_text(encoding='utf-8')


def test_P32_002_bootstrap_records_only_the_exception_category(tmp_path):
    import jarvis_bootstrap
    with patch.object(jarvis_bootstrap, 'BASE', tmp_path), patch.object(jarvis_bootstrap, 'restore_entrypoints'), \
         patch.object(jarvis_bootstrap.runpy, 'run_module', side_effect=RuntimeError('failed api_key=SYNTHETIC_BOOT_CANARY')), \
         patch.object(sys, 'argv', ['jarvis_bootstrap.py']):
        jarvis_bootstrap.main()
    row = json.loads((tmp_path / '.jarvis-runtime/repairs.jsonl').read_text(encoding='utf-8').splitlines()[-1])
    assert row['message'] == 'Launcher could not recover (RuntimeError).'


# ---- P33-002 / P33-003: call contract -------------------------------------------------------------------------------
def test_P33_002_argument_schema_subset_is_strict():
    from jarvis.mcp_contract import ContractError, validate_schema_value
    schema = {'type': 'object', 'title': 'Arguments', 'required': ['count'], 'additionalProperties': False,
              'properties': {'count': {'type': 'integer', 'minimum': 0}, 'tags': {'type': 'array', 'maxItems': 2,
                                                                                    'items': {'type': 'string'}}}}
    assert validate_schema_value(schema, {'count': 2, 'tags': ['a']})
    for bad in ({'count': '2'}, {'count': True}, {'count': -1}, {}, {'count': 1, 'extra': 1}, {'count': 1, 'tags': [1]},
                {'count': 1, 'tags': ['a', 'b', 'c']}):
        with pytest.raises(ContractError):
            validate_schema_value(schema, bad)
    for unsupported in ({'anyOf': [{'type': 'string'}]}, {'$ref': '#/x'}, {'type': 'string', 'pattern': '.*'}):
        with pytest.raises(ContractError, match='Unsupported'):
            validate_schema_value(unsupported, 'x')


def test_P33_003_result_envelopes_are_strict():
    from jarvis.mcp_contract import ContractError, validate_result
    good = {'content': [{'type': 'text', 'text': 'ok'}], 'structuredContent': {'result': 1}, 'isError': False}
    assert validate_result(good, {'type': 'object', 'required': ['result'], 'properties': {'result': {'type': 'integer'}}})
    for bad in ('text', {'content': 'x'}, {'content': [{'type': 'text'}]}, {'content': [], 'isError': 'false'},
                {'content': [{'type': 'video', 'data': ''}]}, {'content': [], 'structuredContent': []}):
        with pytest.raises(ContractError):
            validate_result(bad)
    with pytest.raises(ContractError):
        validate_result({'content': [], 'structuredContent': {'result': 'one'}},
                        {'type': 'object', 'properties': {'result': {'type': 'integer'}}})
    with pytest.raises(ContractError, match='no structuredContent'):
        validate_result({'content': []}, {'type': 'object'})


# ---- P33-001: approved generated identity enforced at the call ------------------------------------------------------
def generated_entry(tmp_path):
    from jarvis import mcp_synthesis
    folder = tmp_path / 'gen' / 'gen-x' / 'abc'
    folder.mkdir(parents=True)
    (folder / 'server.py').write_text('print(1)\n', encoding='utf-8')
    (folder / 'spec.json').write_text('{"name": "x"}', encoding='utf-8')
    code = hashlib.sha256('print(1)\n'.encode()).hexdigest()
    spec = hashlib.sha256((folder / 'spec.json').read_bytes()).hexdigest()
    image = 'sha256:' + 'a' * 64
    entry = {'command': 'docker', 'args': ['--mount', 'type=bind,src=' + str(folder / 'server.py') + ',dst=/server.py,readonly',
                                           image], 'trusted': True, 'enabled': True, 'allow_tools': ['x'], 'timeout_seconds': 5,
             'status': 'provisional', 'code_sha256': code, 'spec_sha256': spec, 'schema_sha256': 's' * 64, 'image_id': image}
    mcp_synthesis.save_registry(tmp_path, {'version': 1, 'servers': {'gen-x': entry}, 'history': []})
    return folder, image


@pytest.mark.parametrize('drift', ['code', 'spec', 'image', 'missing_pin'])
def test_P33_001_drift_disables_the_generated_server_before_approval(tmp_path, drift):
    from jarvis import mcp_synthesis
    folder, image = generated_entry(tmp_path)
    if drift == 'code':
        (folder / 'server.py').write_text('print(2)\n', encoding='utf-8')
    elif drift == 'spec':
        (folder / 'spec.json').write_text('{"name": "y"}', encoding='utf-8')
    elif drift == 'missing_pin':
        registry = mcp_synthesis.load_registry(tmp_path)
        del registry['servers']['gen-x']['schema_sha256']
        mcp_synthesis.save_registry(tmp_path, registry)
    status = {'available': True, 'image_id': image if drift != 'image' else 'sha256:' + 'b' * 64}
    config = mcp_synthesis.configurations(tmp_path)['gen-x']
    with patch.object(mcp_synthesis, 'image_status', return_value=status):
        with pytest.raises(ValueError, match='disabled pending revalidation'):
            mcp_synthesis.verified_execution_config(tmp_path, 'gen-x', config)
    assert mcp_synthesis.load_registry(tmp_path)['servers']['gen-x']['status'] == 'drifted'
    assert 'gen-x' not in mcp_synthesis.configurations(tmp_path)  # no longer offered to the bridge


def test_P33_001_execution_mounts_a_private_copy_of_the_verified_bytes(tmp_path):
    from jarvis import mcp_synthesis
    folder, image = generated_entry(tmp_path)
    config = mcp_synthesis.configurations(tmp_path)['gen-x']
    with patch.object(mcp_synthesis, 'image_status', return_value={'available': True, 'image_id': image}):
        verified, private = mcp_synthesis.verified_execution_config(tmp_path, 'gen-x', config)
    (folder / 'server.py').write_text('print("tampered after verification")\n', encoding='utf-8')
    mounted = mcp_synthesis.mounted_source(verified)
    assert mounted.parent == private.resolve() and mounted.read_text(encoding='utf-8') == 'print(1)\n'
    assert mcp_synthesis.mounted_source(config) == folder / 'server.py'
