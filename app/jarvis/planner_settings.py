"""Typed optional planner configuration; no model/runtime installation side effects."""
import math


def settings(options, name):
    if not isinstance(options, dict):
        raise ValueError('Planner options must be an object.')
    if not isinstance(name, str) or name not in {'hermes', 'harness'}:
        raise ValueError('Unknown planner backend.')
    value = options.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(name + ' configuration must be an object.')
    if 'enabled' in value and type(value['enabled']) is not bool:
        raise ValueError(name + '.enabled must be boolean.')
    default, maximum = (120, 180) if name == 'hermes' else (180, 300)
    seconds = value.get('timeout_seconds', default)
    if type(seconds) not in {int, float} or not math.isfinite(seconds) or not 10 <= seconds <= maximum:
        raise ValueError(name + '.timeout_seconds must be finite and within 10–' + str(maximum) + ' seconds.')
    model = value.get('model')
    if model is not None and (not isinstance(model, str) or not model.strip() or len(model) > 256 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in model)):
        raise ValueError(name + '.model must be a bounded local model name.')
    return {**value, 'enabled': value.get('enabled', False), 'timeout_seconds': float(seconds)}
