"""Environment-backed settings shared by the CLI and the web UI (interface layer, not core).

Variables: BLEEPER_MODEL, BLEEPER_UI_HOST, BLEEPER_UI_PORT, BLEEPER_UI_MAX_UPLOAD_MB.
Empty strings count as unset. With nothing set, the defaults equal the behavior before these
variables existed. Values are read at call time.
"""

from __future__ import annotations

import os


class SettingsError(ValueError):
    """An environment variable holds an unusable value."""


def _text(name: str, default: str) -> str:
    return os.environ.get(name) or default


def _integer(name: str, default: int, low: int, high: int | None, accepted: str) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = low - 1
    if value < low or (high is not None and value > high):
        raise SettingsError(f"{name}={raw!r} is not valid; use {accepted}.")
    return value


def default_model() -> str:
    return _text("BLEEPER_MODEL", "small")


def ui_host() -> str:
    return _text("BLEEPER_UI_HOST", "127.0.0.1")


def ui_port() -> int:
    return _integer("BLEEPER_UI_PORT", 7860, 1, 65535, "an integer in 1–65535")


def max_upload_mb() -> int:
    return _integer("BLEEPER_UI_MAX_UPLOAD_MB", 100, 1, None, "an integer ≥ 1")
