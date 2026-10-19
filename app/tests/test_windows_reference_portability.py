"""Pinned reference integrity must survive Git text checkout conversion."""
from pathlib import Path
import subprocess

import pytest

from jarvis import windows_commands

BASE = Path(__file__).resolve().parents[1]
PIN = '36fbf3ce925080f7f54afa87eaf1d9b88414142d'


@pytest.mark.parametrize('newline', [b'\n', b'\r\n'])
def test_git_reference_accepts_lf_and_crlf(monkeypatch, tmp_path, newline):
    for name in ('catalog.json', 'Jarvis_Windows_11_Commands.json'):
        raw = subprocess.run(['git', 'show', PIN + ':app/integrations/windows-command-reference/' + name],
                             cwd=BASE, capture_output=True, check=True).stdout
        (tmp_path / name).write_bytes(raw.replace(b'\r\n', b'\n').replace(b'\n', newline))
    monkeypatch.setattr(windows_commands, 'ROOT', tmp_path)
    assert len(windows_commands.catalog()) == 493


def test_git_reference_still_rejects_content_tampering(monkeypatch, tmp_path):
    for name in ('catalog.json', 'Jarvis_Windows_11_Commands.json'):
        raw = subprocess.run(['git', 'show', PIN + ':app/integrations/windows-command-reference/' + name],
                             cwd=BASE, capture_output=True, check=True).stdout
        (tmp_path / name).write_bytes(raw)
    catalog = tmp_path / 'catalog.json'
    catalog.write_bytes(catalog.read_bytes() + b' ')
    monkeypatch.setattr(windows_commands, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='reference changed'):
        windows_commands.catalog()
