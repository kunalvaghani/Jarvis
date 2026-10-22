"""Discover local Piper voices from their language metadata, never filenames alone."""
import json


def kokoro_voices(directory):
    """Inspect existing style-vector keys without loading a synthesis model."""
    if not (directory / 'kokoro-v1.0.onnx').is_file() or not (directory / 'voices-v1.0.bin').is_file():
        return {}
    try:
        import numpy as np
        with np.load(directory / 'voices-v1.0.bin', allow_pickle=False) as bank:
            names = tuple(bank.keys())
        return {language: tuple(name for name in names if name.startswith(prefixes))
                for language, prefixes in {'en': ('af_', 'am_', 'bf_', 'bm_'), 'fr': ('ff_',)}.items()
                if any(name.startswith(prefixes) for name in names)}
    except (OSError, ValueError, TypeError):
        return {}


def piper_voices(directory):
    voices = {}
    for metadata in sorted(directory.glob('*.onnx.json')):
        model = metadata.with_suffix('')
        if not model.is_file():
            continue
        try:
            data = json.loads(metadata.read_text(encoding='utf-8'))
            language = data['language']['code'].split('_')[0].split('-')[0]
            if language in {'en', 'hi', 'gu', 'fr'}:
                voices.setdefault(language, model)
        except (ValueError, KeyError, TypeError, OSError, AttributeError):
            continue
    return voices
