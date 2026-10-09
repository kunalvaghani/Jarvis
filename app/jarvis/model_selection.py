"""Use configured models when installed, with explicit bounded local fallbacks."""
def required_models(config):
    required = set()
    if config.get('brain',{}).get('coding_backend')=='codex':
        required.add(config['brain'].get('codex_model','jarvis-codex-qwen3.5:9b'))
    if config.get('brain',{}).get('coding_backend')=='claude-code':
        required.add(config['brain'].get('claude_code_model','jarvis-claude-qwen3.5:9b'))
    for section, keys in (("brain", ("planner", "coder", "decision", "screen_model")),
                          ("knowledge", ("model", "screen_model"))):
        options = config.get(section, {})
        if options.get("enabled"):
            required.update(options[key] for key in keys if options.get(key))
    hermes = config.get("brain", {}).get("hermes", {})
    if config.get("brain", {}).get("enabled") and hermes.get("enabled") and hermes.get("model"):
        required.add(hermes["model"])
    from .command_cleanup import settings
    cleanup = settings(config.get('command_cleanup'))
    if cleanup['enabled']:
        required.add(cleanup['model'])
    from .context_selector import settings as context_settings
    selector = context_settings(config.get('context_selector'))
    if selector['enabled']:
        required.add(selector['model'])
    from .realtime import settings as realtime_settings
    realtime = realtime_settings(config.get('realtime'))
    if realtime['enabled'] and realtime['model_enabled']:
        required.add(realtime['model'])
    return required


def installed_model(preferred, names, vision=False, allow_fallback=True):
    if preferred in names:
        return preferred
    candidates = ("qwen3.5:9b", "qwen3.5:4b", "qwen3-vl:4b", "qwen3-vl:2b") if vision else ("qwen3.5:9b", "qwen3.5:4b", "qwen3:4b", "qwen2.5:3b")
    if allow_fallback:
        for candidate in candidates:
            if candidate in names:
                return candidate
    raise ValueError("Local model is missing: " + preferred + ". Run launchers/Setup Jarvis Brain.cmd to install it.")
