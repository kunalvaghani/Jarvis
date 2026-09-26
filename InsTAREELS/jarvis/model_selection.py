"""Use configured models when installed, with explicit bounded local fallbacks."""
def installed_model(preferred, names, vision=False, allow_fallback=True):
    if preferred in names:
        return preferred
    candidates = ("qwen3-vl:4b", "qwen3-vl:2b") if vision else ("qwen3.5:4b", "qwen3:4b", "qwen2.5:3b")
    if allow_fallback:
        for candidate in candidates:
            if candidate in names:
                return candidate
    raise ValueError("Local model is missing: " + preferred + ". Run Setup Jarvis Brain.cmd to install it.")
