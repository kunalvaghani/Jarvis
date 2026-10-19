"""All install/download execution is intercepted; only disposable files are written."""
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import Mock,patch

import pytest

APP=next(p for p in Path(__file__).resolve().parents if (p/'main.py').is_file())
sys.path.insert(0,str(APP))
from jarvis import launcher
from jarvis.model_recovery import ModelRecovery


def prepared(tmp_path):
    python=tmp_path/'.venv/Scripts/python.exe';python.parent.mkdir(parents=True);python.touch()
    model=tmp_path/'models/fixture/model.bin';model.parent.mkdir(parents=True);model.touch()
    manifest=tmp_path/'config/runtime_manifest.json';manifest.parent.mkdir()
    manifest.write_text(json.dumps({'main_imports':['json'],'brain_imports':['json'],'f5_imports':['json']}))
    runtime=tmp_path/'.jarvis-runtime';runtime.mkdir()
    return runtime,{'model_path':'models/fixture','speech':{'enabled':False},'brain':{'enabled':False}}


def test_JRV_34_012_missing_dependency_does_not_auto_install_without_approval(tmp_path):
    runtime,config=prepared(tmp_path)
    commands=[]
    def intercepted(args,log,timeout=1800):
        commands.append([str(a) for a in args])
        return 1 if len(commands)==1 else 0  # missing import, subsequent commands would "succeed"
    with patch.object(launcher,'BASE',tmp_path),patch.object(launcher,'RUNTIME',runtime), \
         patch.object(launcher,'runtime_command',side_effect=intercepted), \
         patch.dict(os.environ,{'PIP_NO_INDEX':'1','HF_HUB_OFFLINE':'1'}):
        try: launcher.prepare_runtime(config)
        except ValueError: pass  # explicit repair-required refusal is acceptable
    (Path(__file__).parent/'unapproved-install-trace.json').write_text(json.dumps({
        'commands':[[arg.replace(str(tmp_path),'%FIXTURE%') for arg in args] for args in commands],
        'real_commands_executed':0,'approval_granted':False},indent=2))
    assert not any('pip' in args and 'install' in args for args in commands), 'ordinary repair attempted pip installation without approval'


def test_JRV_34_011_low_disk_missing_model_does_not_start_unapproved_download(tmp_path):
    runtime,config=prepared(tmp_path)
    recovery=ModelRecovery(tmp_path,config,Mock(),lambda:False)
    recovery.missing=['SYNTHETIC_MISSING_LARGE_MODEL']
    process=Mock();process.poll.return_value=0;process.returncode=0
    usage=shutil._ntuple_diskusage(100,99,1)
    with patch('jarvis.model_recovery.subprocess.Popen',return_value=process) as launch, \
         patch('shutil.disk_usage',return_value=usage), \
         patch.dict(os.environ,{'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}):
        recovery.repair()
        recovery.thread.join(5)
        assert not recovery.thread.is_alive()
    (Path(__file__).parent/'unapproved-model-trace.json').write_text(json.dumps({
        'launch_count':launch.call_count,'commands':[[str(a).replace(str(tmp_path),'%FIXTURE%') for a in call.args[0]] for call in launch.call_args_list],
        'mock_free_disk_bytes':1,'approval_granted':False,'real_processes_or_downloads':0},indent=2))
    assert launch.call_count==0,'model repair launched download setup without approval or a disk-budget gate'


def test_existing_runtime_needs_no_install_or_download(tmp_path):
    runtime,config=prepared(tmp_path)
    with patch.object(launcher,'BASE',tmp_path),patch.object(launcher,'RUNTIME',runtime), \
         patch.object(launcher,'runtime_command',return_value=0) as command:
        result=launcher.prepare_runtime(config)
    assert result==tmp_path/'.venv/Scripts/pythonw.exe'
    assert len(command.call_args_list)==1
    assert '-c' in command.call_args.args[0]


def test_deliberate_shutdown_prevents_model_repair_process(tmp_path):
    prepared(tmp_path)
    recovery=ModelRecovery(tmp_path,{},Mock(),lambda:True)
    with patch('jarvis.model_recovery.subprocess.Popen') as launch:
        assert recovery.repair() is False
        recovery.download()
    launch.assert_not_called()
