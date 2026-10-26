"""Built-in mask sounds, generated in code (pure)."""

from __future__ import annotations

import numpy as np

from bleeper.core.errors import InvalidInputError

PRESETS = ("beep", "tone", "noise")
_SINE_HZ = {"beep": 1000.0, "tone": 400.0}


def generate_preset(name: str, n_samples: int, sample_rate: int) -> np.ndarray:
    """Return a mono float64 mask of exactly `n_samples`."""
    if name in _SINE_HZ:
        t = np.arange(n_samples) / sample_rate
        return np.sin(2 * np.pi * _SINE_HZ[name] * t)
    if name == "noise":
        return np.random.default_rng(0).uniform(-1.0, 1.0, n_samples)
    raise InvalidInputError(f"unknown preset '{name}'. Choose one of: {', '.join(PRESETS)}.")
