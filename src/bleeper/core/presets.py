"""Built-in mask sounds, generated in code (pure)."""

from __future__ import annotations

import numpy as np

from bleeper.core.errors import InvalidInputError
from bleeper.core.masking import fade

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


def preset_preview(name: str, seconds: float = 1.0, sample_rate: int = 44100) -> np.ndarray:
    """The preset at a 0.5 peak with the core's fade, for preview players."""
    samples = generate_preset(name, round(seconds * sample_rate), sample_rate)
    samples = 0.5 * samples / max(float(np.abs(samples).max()), 1e-12)
    return fade(samples, sample_rate)
