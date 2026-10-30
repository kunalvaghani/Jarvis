"""Upgrade v2 flags: shipped off, and anything malformed reads as off (a bad config can only switch things off)."""
import json
from pathlib import Path
import warnings

import pytest

from jarvis import flags
from jarvis.config_contract import ConfigurationWarning, validate_root
from jarvis.control import settings as control_settings

APP = Path(__file__).resolve().parents[1]
SHIPPED = json.loads((APP / 'config' / 'config.json').read_text(encoding='utf-8'))


def test_shipped_config_has_every_v2_flag_off():
    for (section, key), default in flags.FLAGS.items():
        assert SHIPPED[section][key] == default, f'{section}.{key}'
        assert default in (False, 'off')
    assert set(flags.summary(SHIPPED).values()) == {False, 'off'}


@pytest.mark.parametrize('value', [None, 'yes', 1, 'true', [], {}, 'True'])
def test_malformed_on_off_values_read_as_off(value):
    assert flags.enabled({'telemetry': {'timing_ledger': value}}, 'telemetry', 'timing_ledger') is False


@pytest.mark.parametrize('config', [None, {}, {'recipes': None}, {'recipes': []}, {'recipes': {'replay': 'ACT'}},
                                    {'recipes': {'replay': True}}, {'recipes': {'replay': 'auto'}}])
def test_malformed_modes_read_as_off(config):
    assert flags.mode(config, 'recipes', 'replay') == 'off'
    assert not flags.at_least(config, 'recipes', 'replay', 'shadow')


def test_modes_are_ordered():
    config = {'fast_path': {'system1': 'suggest'}}
    assert flags.at_least(config, 'fast_path', 'system1', 'shadow')
    assert flags.at_least(config, 'fast_path', 'system1', 'suggest')
    assert not flags.at_least(config, 'fast_path', 'system1', 'act')
    assert flags.enabled({'telemetry': {'timing_ledger': True}}, 'telemetry', 'timing_ledger')


def test_unknown_flags_and_wrong_accessors_are_programming_errors():
    with pytest.raises(KeyError):
        flags.enabled({}, 'telemetry', 'nope')
    with pytest.raises(KeyError):
        flags.enabled({}, 'recipes', 'replay')
    with pytest.raises(KeyError):
        flags.mode({}, 'telemetry', 'timing_ledger')
    with pytest.raises(ValueError):
        flags.at_least({}, 'recipes', 'replay', 'max')


def test_brain_section_carries_no_v2_flags():
    # The brain section is sent to the brain worker with every request; flags there would change that payload.
    assert not any(section == 'brain' for section, _ in flags.FLAGS)
    assert not {'system1', 'plan_cache'} & set(SHIPPED['brain'])


def test_new_sections_raise_no_unknown_field_warning():
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConfigurationWarning)
        validate_root({**SHIPPED})
        validate_root(flags.defaults())


def test_control_defaults_unchanged_by_the_new_control_flags():
    plain = control_settings.load(APP, {})
    flagged = control_settings.load(APP, {'control': flags.defaults()['control']})
    for name in ('allowed_roots', 'allowed_apps', 'test_profile', 'personal_profile', 'downloads', 'vision_models',
                 'ollama_url', 'headless'):
        assert getattr(plain, name) == getattr(flagged, name)
    assert dict(flagged.extra) == flags.defaults()['control']
