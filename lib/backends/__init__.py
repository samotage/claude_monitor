"""Terminal backend factory and common utilities.

This module provides a factory function to get the configured terminal
backend, allowing the application to work with different terminal
multiplexers (tmux, WezTerm) using a common interface.

Usage:
    from lib.backends import get_backend

    backend = get_backend()  # Uses config setting
    backend = get_backend("tmux")  # Force specific backend

    if backend.is_available():
        sessions = backend.list_sessions()
"""

from typing import Optional

from lib.backends.base import SessionInfo, TerminalBackend

# Re-export for convenience
__all__ = [
    "get_backend",
    "reset_backend",
    "SessionInfo",
    "TerminalBackend",
]

# Cached backend instance
_backend_instance: Optional[TerminalBackend] = None
_cached_backend_name: Optional[str] = None


def get_backend(backend_name: Optional[str] = None) -> TerminalBackend:
    """Get the configured terminal backend.

    Args:
        backend_name: Override to use specific backend ("tmux" or "wezterm").
                     If None, reads from config (defaults to "tmux").

    Returns:
        Configured TerminalBackend instance.

    Raises:
        ValueError: If an unknown backend name is specified.
    """
    global _backend_instance, _cached_backend_name

    # Determine backend name
    if backend_name is None:
        try:
            from lib.config import load_config

            config = load_config()
            backend_name = config.get("terminal_backend", "tmux")
        except Exception:
            # Fall back to tmux if config loading fails
            backend_name = "tmux"

    # Return cached instance if same backend
    if _backend_instance is not None and _cached_backend_name == backend_name:
        return _backend_instance

    # Create new instance based on backend name
    if backend_name == "tmux":
        from lib.backends.tmux import TmuxBackend

        _backend_instance = TmuxBackend()
    elif backend_name == "wezterm":
        from lib.backends.wezterm import WezTermBackend

        _backend_instance = WezTermBackend()
    else:
        raise ValueError(f"Unknown terminal backend: {backend_name}")

    _cached_backend_name = backend_name
    return _backend_instance


def reset_backend() -> None:
    """Clear the cached backend instance.

    Call this if the configuration changes and you need to
    re-initialize the backend.
    """
    global _backend_instance, _cached_backend_name
    _backend_instance = None
    _cached_backend_name = None
