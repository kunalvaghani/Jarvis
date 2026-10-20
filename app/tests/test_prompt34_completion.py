"""Safe local completion of Prompt 34: no installs or network operations."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import threading
import time
from unittest.mock import patch

import pytest

from jarvis import repair_authorization as auth
from tests.test_prompt34_dependency_repair import locked, approval_for, PLENTY, ONLINE


@pytest.mark.parametrize('suffix', [' --find-links=https://example.invalid/wheels',
                                    ' --index-url=https://example.invalid/simple',
                                    ' --trusted-host=example.invalid'])
def test_lock_cannot_smuggle_pip_options_after_a_hash(suffix):
    with pytest.raises(auth.RepairRefused):
        auth.locked_requirements('fixture==1 --hash=sha256:'+'a'*64+suffix)


@pytest.mark.parametrize('bad', [float('nan'),float('inf'),True,'tomorrow'])
def test_dependency_expiry_must_be_finite_and_numeric(tmp_path,bad):
    approval=replace(locked(tmp_path),expires=bad)
    with pytest.raises(auth.RepairRefused):
        auth.check_dependency_repair(tmp_path,approval,'.venv',disk_usage=lambda _:PLENTY)


@pytest.mark.parametrize('identifier',['../../outside','x/y','x\\y','', 'x'*65])
def test_dependency_approval_identifier_cannot_form_paths(tmp_path,identifier):
    with pytest.raises(auth.RepairRefused):
        auth.check_dependency_repair(tmp_path,replace(locked(tmp_path),approval_id=identifier),'.venv',disk_usage=lambda _:PLENTY)


def test_model_network_consent_must_be_boolean_true(tmp_path):
    with pytest.raises(auth.RepairRefused):
        auth.check_model_download(approval_for(network_allowed='false'),['qwen3.5:27b'],tmp_path,
            environment=ONLINE,disk_usage=lambda _:PLENTY,ram_total=1<<40,vram_total=1<<40)


def test_authorization_is_claimed_once_with_two_simultaneous_readers(tmp_path):
    approval=locked(tmp_path)
    path=tmp_path/auth.DEPENDENCY_FILE
    path.write_text(json.dumps(approval.__dict__))
    start=threading.Barrier(2)
    original=Path.read_text
    def read(candidate,*args,**kwargs):
        text=original(candidate,*args,**kwargs)
        if candidate==path:
            time.sleep(.2)  # Widen the old read/unlink race without blocking a lock's legitimate sole reader.
        return text
    def take():
        start.wait(timeout=3)
        return auth.take_dependency_repair(tmp_path)
    with patch.object(Path,'read_text',read),ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(lambda _:take(),range(2)))
    assert sum(value is not None for value in values)==1
    assert not path.exists()
