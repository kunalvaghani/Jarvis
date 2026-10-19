"""Independent failure reproductions. Synthetic UIA and lease files; no GUI or GPU work."""
import json
from types import SimpleNamespace

import pytest


class Element:
    def __init__(self, name='Public status', private=False, role='Text', unknown=False):
        self.element_info = SimpleNamespace(control_type=role, name=name,
            element=SimpleNamespace() if unknown else SimpleNamespace(CurrentIsPassword=private))

    def get_toggle_state(self):
        return 1


@pytest.mark.parametrize('role', ['Text', 'CheckBox', 'RadioButton'])
def test_private_state_elements_are_excluded(role):
    from jarvis.demonstration import window_state
    private = Element('SYNTHETIC_PRIVATE_CANARY', True, role)
    public = Element('Public status')
    window = SimpleNamespace(descendants=lambda: [private, public], window_text=lambda: 'Disposable fixture')
    result = window_state(window)
    assert 'SYNTHETIC_PRIVATE_CANARY' not in json.dumps(result)
    assert result['texts'] == ['Public status']


def test_unknown_state_privacy_is_excluded():
    from jarvis.demonstration import window_state
    unknown = Element('SYNTHETIC_UNKNOWN_CANARY', unknown=True)
    window = SimpleNamespace(descendants=lambda: [unknown], window_text=lambda: 'Disposable fixture')
    assert window_state(window)['texts'] == []


@pytest.mark.parametrize('body', ['{broken', '[]', 'null', '{"active":null,"pending":"broken"}',
                                  '{"active":{"pid":123},"pending":[]}'])
def test_unknown_gpu_lease_state_defers_training(monkeypatch, tmp_path, body):
    from scripts.training import train_azr_lora as trainer
    monkeypatch.setattr(trainer, 'BASE', tmp_path)
    state = tmp_path / '.jarvis-runtime/gpu/state.json'
    state.parent.mkdir(parents=True)
    state.write_text(body, encoding='utf-8')
    assert trainer.foreground_gpu_busy() is True


def test_unreadable_gpu_state_defers_training(monkeypatch, tmp_path):
    from pathlib import Path
    from scripts.training import train_azr_lora as trainer
    monkeypatch.setattr(trainer, 'BASE', tmp_path)
    def denied(*args, **kwargs):
        raise PermissionError('synthetic read denial')
    monkeypatch.setattr(Path, 'open', denied)
    assert trainer.foreground_gpu_busy() is True


def test_missing_gpu_state_is_idle(monkeypatch, tmp_path):
    from scripts.training import train_azr_lora as trainer
    monkeypatch.setattr(trainer, 'BASE', tmp_path)
    assert trainer.foreground_gpu_busy() is False


def test_training_defers_before_loading_model_or_creating_output(monkeypatch, tmp_path):
    import builtins
    from scripts.training import train_azr_lora as trainer
    monkeypatch.setattr(trainer, 'foreground_gpu_busy', lambda: True)
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        assert name not in {'torch', 'peft', 'transformers'}, 'training imported GPU dependencies before admission'
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded_import)
    output = tmp_path / 'training'
    assert trainer.main(['--dataset', str(tmp_path), '--out', str(output)]) == 3
    assert not output.exists()
