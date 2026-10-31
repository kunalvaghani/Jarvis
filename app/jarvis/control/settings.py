"""Control-layer settings: the optional "control" section of config/config.json, with ADR 0002 defaults."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from ..flags import summary

APP = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = Path(r'D:\Phython Project\TestCodes\jarvis-control-tests')
DEFAULT_APPS = ('notepad.exe', 'calculatorapp.exe', 'applicationframehost.exe', 'explorer.exe', 'mspaint.exe', 'chrome.exe')


@dataclass(frozen=True)
class ControlSettings:
    allowed_roots: Tuple[Path, ...] = (DEFAULT_ROOT,)
    allowed_apps: Tuple[str, ...] = DEFAULT_APPS
    test_profile: Path = APP / '.jarvis-runtime' / 'test-browser-profile'
    personal_profile: Path = APP / '.jarvis-runtime' / 'personal-browser-profile'
    downloads: Path = DEFAULT_ROOT / 'downloads'
    vision_models: Tuple[str, ...] = ('qwen3-vl:2b', 'qwen3-vl:4b')
    ollama_url: str = 'http://127.0.0.1:11434'
    headless: bool = False  # The user sees what Jarvis does.
    extra: Mapping[str, Any] = field(default_factory=dict)
    flags: Mapping[str, Any] = field(default_factory=dict)  # Effective upgrade v2 flags (jarvis/flags.py), all off by default.


def load(base: Optional[Path] = None, config: Optional[Mapping[str, Any]] = None) -> ControlSettings:
    base = Path(base) if base is not None else APP
    if config is None:
        try:
            config = json.loads((base / 'config' / 'config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            config = {}
    section = config.get('control', {}) if isinstance(config, Mapping) else {}
    section = section if isinstance(section, Mapping) else {}
    defaults = ControlSettings()

    def paths(key: str, default: Tuple[Path, ...]) -> Tuple[Path, ...]:
        value = section.get(key)
        return tuple(Path(str(v)) for v in value) if isinstance(value, list) and value else default

    roots = paths('allowed_roots', defaults.allowed_roots)
    apps = section.get('allowed_apps')
    models = section.get('vision_models')
    return ControlSettings(
        allowed_roots=roots,
        allowed_apps=tuple(str(a).lower() for a in apps) if isinstance(apps, list) and apps else defaults.allowed_apps,
        test_profile=Path(str(section.get('test_profile', base / '.jarvis-runtime' / 'test-browser-profile'))),
        personal_profile=Path(str(section.get('personal_profile', base / '.jarvis-runtime' / 'personal-browser-profile'))),
        downloads=Path(str(section.get('downloads', roots[0] / 'downloads'))),
        vision_models=tuple(str(m) for m in models) if isinstance(models, list) and models else defaults.vision_models,
        ollama_url=str(section.get('ollama_url', defaults.ollama_url)),
        headless=bool(section.get('headless', False)),
        extra={k: v for k, v in section.items() if k not in ControlSettings.__dataclass_fields__},
        flags=summary(config))
