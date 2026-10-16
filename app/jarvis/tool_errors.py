"""Dependency-free tool error types shared by toolkits and the adapters it registers."""


class ToolUnavailable(ValueError):
    """Required configuration is missing; nothing was attempted."""
