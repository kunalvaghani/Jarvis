"""Brain mode switch (Phase 0): default off, environment override, malformed values read as off."""
import pytest

from jarvis.neural import brain_mode


@pytest.mark.parametrize('config,environ,expected', [
    ({}, {}, 'off'),
    ({'neural': {'mode': 'shadow'}}, {}, 'shadow'),
    ({'neural': {'mode': 'act'}}, {}, 'on'),
    ({'neural': {'mode': 'suggest'}}, {}, 'shadow'),
    ({'neural': {'mode': 'ON'}}, {}, 'off'),  # Malformed config value.
    ({'neural': {'mode': 'act'}}, {'JARVIS_BRAIN_MODE': 'off'}, 'off'),  # One-step rollback.
    ({}, {'JARVIS_BRAIN_MODE': ' Shadow '}, 'shadow'),
    ({'neural': {'mode': 'shadow'}}, {'JARVIS_BRAIN_MODE': 'banana'}, 'shadow'),
])
def test_brain_mode(config, environ, expected):
    assert brain_mode(config, environ) == expected


def test_shipped_config_keeps_the_brain_off():
    import json
    from pathlib import Path
    config = json.loads((Path(__file__).resolve().parents[1] / 'config' / 'config.json').read_text(encoding='utf-8'))
    assert config['neural'] == {'mode': 'off'} and brain_mode(config, {}) == 'off'
