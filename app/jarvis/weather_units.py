"""Explicit Open-Meteo temperature normalization; never mutate provider payloads."""
import math


def normalize(data):
    if not isinstance(data, dict):
        raise ValueError('Weather response must be an object.')
    result = data
    conversions = []
    for section in ('current', 'hourly', 'daily'):
        values, units = data.get(section), data.get(section+'_units', {})
        if not isinstance(values, dict) or not isinstance(units, dict):
            continue
        for key in ('temperature_2m', 'temperature_2m_max', 'temperature_2m_min', 'apparent_temperature'):
            if key not in values:
                continue
            unit = units.get(key, '°C')
            if unit in ('°C', 'C', 'celsius'):
                continue
            if unit not in ('°F', 'F', 'fahrenheit'):
                raise ValueError('Unsupported weather temperature unit.')
            def convert(value):
                return (value-32)*5/9 if type(value) in (int,float) and math.isfinite(value) else None
            original = values[key]
            converted = [convert(v) for v in original] if isinstance(original,list) else convert(original)
            if result is data:
                result = dict(data)
            result[section] = {**result[section], key:converted}
            result[section+'_units'] = {**result.get(section+'_units', {}), key:'°C'}
            conversions.append({'field':section+'.'+key, 'from':unit, 'to':'°C'})
    if conversions:
        result['unit_conversions'] = conversions
    return result
