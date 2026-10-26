"""Fit, level-match, fade and apply masks to sample spans (pure)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from bleeper.core.errors import InvalidInputError
from bleeper.core.models import Span

_INT_SCALE = 2.0**31
_FADE_SECONDS = 0.010
_CONTEXT_SECONDS = 0.5
_SILENCE_RMS = 1e-4
_SILENCE_TARGET = 0.1
_PEAK_LIMIT = 0.99


def to_float(segment: np.ndarray) -> np.ndarray:
    if np.issubdtype(segment.dtype, np.integer):
        return segment.astype(np.float64) / _INT_SCALE
    return segment.astype(np.float64)


def from_float(segment: np.ndarray, dtype: np.dtype) -> np.ndarray:
    if np.issubdtype(dtype, np.integer):
        scaled = np.round(segment * _INT_SCALE)
        return np.clip(scaled, -_INT_SCALE, _INT_SCALE - 1).astype(dtype)
    return segment.astype(dtype)


def fit_to_length(mask: np.ndarray, n_samples: int) -> np.ndarray:
    """Loop a short mask or trim a long one to exactly `n_samples`."""
    if mask.size == 0:
        raise InvalidInputError("the mask sound is empty. Use a mask file that contains audio.")
    return np.resize(mask, n_samples)


def fade(mask: np.ndarray, sample_rate: int) -> np.ndarray:
    """Linear 10 ms fade in and out (half the span when it is shorter than 20 ms)."""
    length = min(round(_FADE_SECONDS * sample_rate), len(mask) // 2)
    faded = mask.copy()
    if length > 0:
        faded[:length] *= np.linspace(0.0, 1.0, length)
        faded[-length:] *= np.linspace(1.0, 0.0, length)
    return faded


def match_level(mask: np.ndarray, context: np.ndarray) -> np.ndarray:
    """Scale `mask` to the RMS of `context`, keeping the peak at or below 0.99 FS."""
    target = float(np.sqrt(np.mean(np.square(context)))) if context.size else 0.0
    if target < _SILENCE_RMS:
        target = _SILENCE_TARGET
    mask_rms = float(np.sqrt(np.mean(np.square(mask)))) if mask.size else 0.0
    if mask_rms == 0.0:
        return np.zeros_like(mask)
    gain = target / mask_rms
    peak = float(np.max(np.abs(mask)))
    gain = min(gain, _PEAK_LIMIT / peak)
    return mask * gain


def _context(samples: np.ndarray, span: Span, sample_rate: int) -> np.ndarray:
    width = round(_CONTEXT_SECONDS * sample_rate)
    before = samples[max(0, span.start - width) : span.start]
    after = samples[span.end : span.end + width]
    return to_float(np.concatenate([before, after]))


def apply_masks(
    samples: np.ndarray,
    sample_rate: int,
    spans: Sequence[Span],
    mask_for: Callable[[int], np.ndarray],
) -> np.ndarray:
    """Return a copy of `samples` (n, channels) with each span replaced by its mask."""
    out = samples.copy()
    for span in spans:
        mask = match_level(mask_for(span.end - span.start), _context(samples, span, sample_rate))
        mask = fade(mask, sample_rate)
        block = np.repeat(mask[:, None], samples.shape[1], axis=1)
        out[span.start : span.end] = from_float(block, samples.dtype)
    return out
