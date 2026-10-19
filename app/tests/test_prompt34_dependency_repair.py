"""Prompt 34 repairs: readiness is read-only; installs and downloads need explicit bounded authorization.

Every command and network call is intercepted. Nothing is installed or downloaded and no real process starts.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import Mock, patch

import pytest

from jarvis import launcher
from jarvis.model_recovery import ModelRecovery
from jarvis.repair_authorization import (OFFLINE_FLAGS, DependencyRepair, ModelDownload, RepairRefused, RepairRequired,
                                         check_model_download, locked_requirements, take_dependency_repair,
                                         take_model_download)

ONLINE = dict.fromkeys(OFFLINE_FLAGS, '0')
PLENTY = shutil._ntuple_diskusage(1 << 41, 0, 1 << 41)
HASH = 'sha256:' + 'b' * 64


def fixture(tmp_path, brain=False, venv=True, model=True):
    python = tmp_path / '.venv/Scripts/python.exe'
    if venv:
        python.parent.mkdir(parents=True)
        python.write_text('old environment')
    if model:
        (tmp_path / 'models/fixture').mkdir(parents=True)
        (tmp_path / 'models/fixture/model.bin').touch()
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/runtime_manifest.json').write_text(json.dumps(
        {'main_imports': ['json'], 'brain_imports': ['json'], 'f5_imports': ['json']}))
    (tmp_path / '.jarvis-runtime').mkdir()
    return {'model_path': 'models/fixture', 'speech': {'enabled': False}, 'brain': {'enabled': brain}}


def run_prepare(tmp_path, config, results, authorization=None):
    commands = []
    def intercepted(args, log, timeout=1800):
        args = [str(a) for a in args]
        commands.append(args)
        if '-m' in args and 'venv' in args:  # a staged environment appears only through the intercepted command
            Path(args[-1], 'Scripts').mkdir(parents=True)
            Path(args[-1], 'Scripts/python.exe').write_text('new environment')
        return results(args)
    with patch.object(launcher, 'BASE', tmp_path), patch.object(launcher, 'RUNTIME', tmp_path / '.jarvis-runtime'), \
            patch.object(launcher, 'runtime_command', side_effect=intercepted), patch.object(launcher, 'record') as record, \
            patch('shutil.disk_usage', return_value=PLENTY):
        try:
            outcome = launcher.prepare_runtime(config, authorization)
        except ValueError as error:
            outcome = error
    return outcome, commands, record


def no_package_or_network(commands):
    return not any(('pip' in c and 'install' in c) or 'scripts.models.download_model' in c or 'scripts.setup.setup_brain' in c
                   or 'scripts.setup.setup_voice' in c or ('-m' in c and 'venv' in c) for c in commands)


# ---- P34-001: readiness is read-only -------------------------------------------------------------------------------

def test_failed_import_reports_repair_required_and_starts_nothing(tmp_path):
    config = fixture(tmp_path)
    outcome, commands, _ = run_prepare(tmp_path, config, lambda args: 1)
    assert isinstance(outcome, RepairRequired) and outcome.missing == ['.venv dependencies']
    assert 'Nothing was installed or downloaded' in str(outcome)
    assert len(commands) == 1 and commands[0][1] == '-c' and no_package_or_network(commands)


@pytest.mark.parametrize('case', ['missing environment', 'missing whisper model', 'brain imports fail', 'laya missing'])
def test_every_absent_dependency_is_reported_not_installed(tmp_path, case):
    config = fixture(tmp_path, brain=case in ('brain imports fail', 'laya missing'), venv=case != 'missing environment',
                     model=case != 'missing whisper model')
    if case == 'brain imports fail':
        (tmp_path / '.venv-brain/Scripts').mkdir(parents=True)
        (tmp_path / '.venv-brain/Scripts/python.exe').touch()
    if case == 'laya missing':
        (tmp_path / '.venv-brain/Scripts').mkdir(parents=True)
        (tmp_path / '.venv-brain/Scripts/python.exe').touch()
    fails_brain = case == 'brain imports fail'
    outcome, commands, _ = run_prepare(tmp_path, config, lambda args: 1 if fails_brain and '.venv-brain' in args[0] else 0)
    assert isinstance(outcome, RepairRequired), case
    assert no_package_or_network(commands), case
    assert all(c[1] == '-c' for c in commands), case  # only read-only import checks ran


def test_installed_runtime_runs_one_import_check(tmp_path):
    config = fixture(tmp_path)
    outcome, commands, _ = run_prepare(tmp_path, config, lambda args: 0)
    assert outcome == tmp_path / '.venv/Scripts/pythonw.exe' and len(commands) == 1


def locked(tmp_path, text=None):
    lock = tmp_path / 'requirements/runtime.lock'
    lock.parent.mkdir(exist_ok=True)
    lock.write_text(text or 'json-fixture==1.0 \\\n    --hash=sha256:' + 'c' * 64 + '\n')
    wheels = tmp_path / 'wheelhouse'
    wheels.mkdir(exist_ok=True)
    (wheels / 'json_fixture-1.0-py3-none-any.whl').write_bytes(b'x' * 100)
    return DependencyRepair('.venv', 'requirements/runtime.lock', hashlib.sha256(lock.read_bytes()).hexdigest(),
                            str(wheels), 1000, time.time() + 60, 'abc123')


def test_authorized_repair_stages_from_the_locked_wheelhouse_and_keeps_the_old_environment(tmp_path):
    config = fixture(tmp_path)
    approval = locked(tmp_path)
    checks = iter([1])  # first import check fails; staged commands succeed
    outcome, commands, _ = run_prepare(tmp_path, config, lambda args: next(checks, 0), approval)
    assert outcome == tmp_path / '.venv/Scripts/pythonw.exe'
    install = next(c for c in commands if 'pip' in c)
    assert '--isolated' not in install and '--no-index' in install and '--require-hashes' in install
    assert install[install.index('--find-links') + 1] == str((tmp_path / 'wheelhouse').resolve())
    assert install[0].endswith('.venv.staging-abc123\\Scripts\\python.exe') or '.venv.staging-abc123' in install[0]
    assert (tmp_path / '.venv/Scripts/python.exe').read_text() == 'new environment'
    assert (tmp_path / '.venv.previous-abc123/Scripts/python.exe').read_text() == 'old environment'


def test_failed_staging_leaves_the_working_environment_untouched(tmp_path):
    config = fixture(tmp_path)
    approval = locked(tmp_path)
    outcome, commands, _ = run_prepare(tmp_path, config, lambda args: 1 if ('pip' in args or args[1] == '-c') else 0, approval)
    assert isinstance(outcome, ValueError) and not isinstance(outcome, RepairRequired)
    assert (tmp_path / '.venv/Scripts/python.exe').read_text() == 'old environment'
    assert (tmp_path / '.venv.staging-abc123').exists()  # partial staging kept for inspection, nothing deleted


@pytest.mark.parametrize('problem', ['unhashed lock', 'unpinned lock', 'lock changed', 'expired', 'over budget',
                                     'other environment', 'wheelhouse missing'])
def test_unbounded_or_stale_authorization_is_refused_before_any_command(tmp_path, problem):
    config = fixture(tmp_path)
    approval = locked(tmp_path, {'unhashed lock': 'json-fixture==1.0\n',
                                 'unpinned lock': 'json-fixture>=1.0 --hash=sha256:' + 'c' * 64 + '\n'}.get(problem))
    if problem == 'lock changed':
        (tmp_path / 'requirements/runtime.lock').write_text('json-fixture==2.0 --hash=sha256:' + 'd' * 64 + '\n')
    changes = {'expired': {'expires': time.time() - 1}, 'over budget': {'max_bytes': 10},
               'other environment': {'environment': '.venv-brain'}, 'wheelhouse missing': {'wheelhouse': str(tmp_path / 'none')}}
    approval = DependencyRepair(**{**approval.__dict__, **changes.get(problem, {})})
    outcome, commands, _ = run_prepare(tmp_path, config, lambda args: 1, approval)
    assert isinstance(outcome, RepairRefused), problem
    assert len(commands) == 1 and no_package_or_network(commands), problem
    assert (tmp_path / '.venv/Scripts/python.exe').read_text() == 'old environment'


def test_current_requirements_are_not_an_approved_locked_artifact_set():
    with pytest.raises(RepairRefused):
        locked_requirements(Path(launcher.BASE, 'requirements/runtime.txt').read_text(encoding='utf-8'))


def test_authorization_files_are_single_use(tmp_path):
    (tmp_path / 'dependency-repair-authorization.json').write_text(json.dumps(locked(tmp_path).__dict__))
    assert take_dependency_repair(tmp_path) is not None
    assert take_dependency_repair(tmp_path) is None
    (tmp_path / 'model-download-authorization.json').write_text('{"unexpected": 1}')
    with pytest.raises(RepairRefused):
        take_model_download(tmp_path)
    assert not (tmp_path / 'model-download-authorization.json').exists()


def test_authorization_is_not_spent_when_more_than_one_thing_is_missing(tmp_path):
    config = fixture(tmp_path, model=False)
    (tmp_path / '.jarvis-runtime/dependency-repair-authorization.json').write_text(json.dumps(locked(tmp_path).__dict__))
    outcome, commands, _ = run_prepare(tmp_path, config, lambda args: 1)
    assert isinstance(outcome, RepairRequired) and len(outcome.missing) == 2 and no_package_or_network(commands)
    assert (tmp_path / '.jarvis-runtime/dependency-repair-authorization.json').exists()


def test_launcher_waits_on_repair_required_without_repeating_repairs(tmp_path):
    runtime = tmp_path / '.jarvis-runtime'
    runtime.mkdir()
    calls = []
    def prepare(config):
        calls.append(1)
        (runtime / 'stop').touch()
        raise RepairRequired(['.venv dependencies'])
    lock = Mock()
    with patch.object(launcher, 'RUNTIME', runtime), patch.object(launcher, 'singleton', return_value=lock), \
            patch.object(launcher, 'preflight', return_value={}), patch('jarvis.docker_runtime.start_background', return_value=None), \
            patch.object(launcher, 'prepare_runtime', side_effect=prepare), patch.object(launcher, 'record') as record, \
            patch('jarvis.launcher.time.sleep'), patch('jarvis.launcher.subprocess.Popen') as launch:
        launcher.run()
    assert calls == [1] and launch.call_count == 0
    assert any('Nothing was installed or downloaded' in call.args[1] for call in record.call_args_list)


# ---- P34-002: missing models are diagnosed, not downloaded ------------------------------------------------------------

def recovery_for(tmp_path, installed, closing=lambda: False):
    (tmp_path / '.jarvis-runtime').mkdir(exist_ok=True)
    config = {'brain': {'enabled': True, 'planner': 'qwen3.5:27b', 'coder': 'qwen3.5:9b'}}
    recovery = ModelRecovery(tmp_path, config, Mock(), closing)
    recovery.client = Mock()
    recovery.client.get.return_value.json.return_value = {'models': [{'name': name} for name in installed]}
    recovery.last_check = -1e9
    return recovery


def approval_for(model='qwen3.5:27b', **changes):
    values = dict(model=model, revision=HASH, source='ollama', max_bytes=20 * 1024 ** 3, ram_bytes=1, vram_bytes=0,
                  network_allowed=True, expires=time.time() + 60, approval_id='m1')
    values.update(changes)
    return ModelDownload(**values)


def test_missing_model_defaults_to_diagnosis_and_installed_fallback(tmp_path):
    recovery = recovery_for(tmp_path, ['qwen3.5:9b'])
    assert recovery.healthy() is False and recovery.missing == ['qwen3.5:27b']
    with patch('jarvis.model_recovery.subprocess.Popen') as launch, patch('shutil.disk_usage', return_value=PLENTY), \
            patch.dict(os.environ, ONLINE):
        recovery.repair()
        recovery.thread.join(5)
    assert launch.call_count == 0
    message = recovery.report.call_args.args[1]
    assert 'qwen3.5:27b -> using installed qwen3.5:9b' in message and 'Nothing was downloaded' in message


def test_configured_tag_with_ample_resources_is_not_download_consent(tmp_path):
    recovery = recovery_for(tmp_path, [])
    recovery.healthy()
    with patch('jarvis.model_recovery.subprocess.Popen') as launch, patch('shutil.disk_usage', return_value=PLENTY), \
            patch.dict(os.environ, ONLINE):
        recovery.repair()
        recovery.thread.join(5)
        recovery.download()
    assert launch.call_count == 0
    assert 'no installed compatible model' in recovery.report.call_args_list[0].args[1]


def test_approved_download_launches_exactly_the_approved_model(tmp_path):
    recovery = recovery_for(tmp_path, ['qwen3.5:9b'])
    recovery.healthy()
    process = Mock()
    process.poll.return_value = 0
    process.returncode = 0
    (tmp_path / '.jarvis-runtime/model-download-authorization.json').write_text(json.dumps(approval_for().__dict__))
    with patch('jarvis.model_recovery.subprocess.Popen', return_value=process) as launch, \
            patch('shutil.disk_usage', return_value=PLENTY), patch.dict(os.environ, ONLINE):
        recovery.repair()
        recovery.thread.join(5)
    assert launch.call_count == 1
    command = launch.call_args.args[0]
    assert command[command.index('--model') + 1] == 'qwen3.5:27b' and command[command.index('--revision') + 1] == HASH
    assert command[command.index('--max-bytes') + 1] == str(20 * 1024 ** 3)
    assert not (tmp_path / '.jarvis-runtime/model-download-authorization.json').exists()


@pytest.mark.parametrize('changes,environment,disk,ram,vram,reason', [
    ({'expires': 1}, {}, PLENTY, 1 << 40, None, 'expired'),
    ({'model': 'qwen3.5:9b'}, {}, PLENTY, 1 << 40, None, 'not a missing model (no substitution)'),
    ({'revision': 'latest'}, {}, PLENTY, 1 << 40, None, 'tag is not a revision'),
    ({'source': 'example-mirror'}, {}, PLENTY, 1 << 40, None, 'unknown source'),
    ({'network_allowed': False}, {}, PLENTY, 1 << 40, None, 'network not permitted'),
    ({}, {'HF_HUB_OFFLINE': '1'}, PLENTY, 1 << 40, None, 'offline policy'),
    ({}, {'JARVIS_OFFLINE': 'true'}, PLENTY, 1 << 40, None, 'offline policy'),
    ({'max_bytes': 0}, {}, PLENTY, 1 << 40, None, 'unknown byte budget'),
    ({'ram_bytes': None}, {}, PLENTY, 1 << 40, None, 'unknown RAM budget'),
    ({}, {}, shutil._ntuple_diskusage(100, 99, 1), 1 << 40, None, 'one byte free'),
    ({'ram_bytes': 1 << 40}, {}, PLENTY, 1 << 30, None, 'RAM below budget'),
    ({'vram_bytes': 1 << 30}, {}, PLENTY, 1 << 40, 'unknown', 'VRAM unknown'),
    ({'vram_bytes': 1 << 34}, {}, PLENTY, 1 << 40, 1 << 33, 'VRAM below budget'),
])
def test_final_executor_rejects_unknown_or_insufficient_bounds(tmp_path, changes, environment, disk, ram, vram, reason):
    arguments = dict(environment={**ONLINE, **environment}, disk_usage=lambda path: disk, ram_total=ram,
                     vram_total=None if vram == 'unknown' else vram)
    with patch('jarvis.gpu_scheduler.memory', return_value=None):  # unmeasurable GPU
        check_model_download(approval_for(), ['qwen3.5:27b'], tmp_path, **{**arguments, 'environment': ONLINE,
                                                                          'disk_usage': lambda path: PLENTY, 'ram_total': 1 << 40})  # control: valid bounds pass
        with pytest.raises(RepairRefused):
            check_model_download(approval_for(**changes), ['qwen3.5:27b'], tmp_path, **arguments)


def test_refused_download_is_reported_and_launches_nothing(tmp_path):
    recovery = recovery_for(tmp_path, [])
    recovery.healthy()
    with patch('jarvis.model_recovery.subprocess.Popen') as launch, \
            patch('shutil.disk_usage', return_value=shutil._ntuple_diskusage(100, 99, 1)), patch.dict(os.environ, ONLINE):
        recovery.download(approval_for())
    assert launch.call_count == 0 and 'disk space' in recovery.report.call_args.args[1]


def test_shutdown_prevents_even_an_approved_download(tmp_path):
    recovery = recovery_for(tmp_path, [], closing=lambda: True)
    recovery.missing = ['qwen3.5:27b']
    with patch('jarvis.model_recovery.subprocess.Popen') as launch:
        assert recovery.repair() is False
        recovery.download(approval_for())
    launch.assert_not_called()


# ---- approved pull executor (scripts/setup/setup_brain.approved_pull) --------------------------------------------------

def registry(body):
    raw = json.dumps(body).encode()
    response = Mock(content=raw, status_code=200)
    response.json.return_value = body
    response.raise_for_status.return_value = None
    return response, 'sha256:' + hashlib.sha256(raw).hexdigest()


def pull_session(installed_digest):
    session = Mock()
    stream = Mock()
    stream.iter_lines.return_value = [json.dumps({'status': 'success'}).encode()]
    session.post.return_value.__enter__ = Mock(return_value=stream)
    session.post.return_value.__exit__ = Mock(return_value=False)
    session.get.return_value.json.return_value = {'models': [{'name': 'qwen3.5:27b', 'digest': installed_digest}]}
    return session


def test_approved_pull_checks_revision_and_budget_before_pulling():
    sys.path.insert(0, str(launcher.BASE))
    from scripts.setup.setup_brain import approved_pull
    response, digest = registry({'config': {'size': 10}, 'layers': [{'size': 1000}]})
    session = pull_session(digest.removeprefix('sha256:'))
    with patch('requests.get', return_value=response):
        approved_pull(session, 'http://127.0.0.1:11434', 'qwen3.5:27b', digest, 2000)
        assert session.post.call_count == 1
        for revision, budget, why in ((HASH, 2000, 'revision differs'), (digest, 500, 'over budget')):
            session = pull_session(digest)
            with pytest.raises(SystemExit):
                approved_pull(session, 'http://127.0.0.1:11434', 'qwen3.5:27b', revision, budget)
            assert session.post.call_count == 0, why
        session = pull_session('f' * 64)
        with pytest.raises(SystemExit):
            approved_pull(session, 'http://127.0.0.1:11434', 'qwen3.5:27b', digest, 2000)  # installed digest differs
