"""Song-friendly masking styles that transform spans in place (pure)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from bleeper.core.errors import InvalidInputError
from bleeper.core.masking import from_float, to_float
from bleeper.core.models import Span

SONG_STYLES = ("vocal-dropout", "reverse", "dip")

_FADE_SECONDS = 0.010
_LOW_PASS_START_HZ = 100.0
_LOW_PASS_END_HZ = 200.0
_STEREO_THRESHOLD = 1e-3
_PREVIEW_PEAK = 0.5


def crossfade_edges(original: np.ndarray, processed: np.ndarray, sample_rate: int) -> np.ndarray:
    """Linear 10 ms crossfade original -> processed at the start and back at the end."""
    n = len(original)
    length = min(round(_FADE_SECONDS * sample_rate), n // 2)
    out = processed.copy()
    if length > 0:
        ramp = np.linspace(0.0, 1.0, length)
        shape = (length,) + (1,) * (out.ndim - 1)
        ramp = ramp.reshape(shape)
        out[:length] = original[:length] * (1.0 - ramp) + processed[:length] * ramp
        out[-length:] = processed[-length:] * (1.0 - ramp) + original[-length:] * ramp
    return out


def _low_band(mid: np.ndarray, sample_rate: int) -> np.ndarray:
    """Zero-phase low-pass: gain 1 below 100 Hz, 0 above 200 Hz, raised cosine between."""
    spectrum = np.fft.rfft(mid)
    freqs = np.fft.rfftfreq(len(mid), 1.0 / sample_rate)
    gain = np.zeros_like(freqs)
    gain[freqs <= _LOW_PASS_START_HZ] = 1.0
    band = (freqs > _LOW_PASS_START_HZ) & (freqs < _LOW_PASS_END_HZ)
    gain[band] = 0.5 * (1.0 + np.cos(np.pi * (freqs[band] - _LOW_PASS_START_HZ) / 100.0))
    return np.fft.irfft(spectrum * gain, n=len(mid))


def has_usable_stereo(samples: np.ndarray) -> bool:
    """True when the file has two channels whose side signal is not negligible."""
    if samples.ndim < 2 or samples.shape[1] < 2:
        return False
    x = to_float(samples)
    side_rms = float(np.sqrt(np.mean(np.square((x[:, 0] - x[:, 1]) / 2))))
    mid_rms = float(np.sqrt(np.mean(np.square((x[:, 0] + x[:, 1]) / 2))))
    if side_rms == 0.0 and mid_rms == 0.0:
        return False
    return side_rms >= _STEREO_THRESHOLD * mid_rms


def apply_style(
    block: np.ndarray, sample_rate: int, style: str, dip_db: float | None = None
) -> np.ndarray:
    """Transform one float block (n, channels) with the named style."""
    if style == "vocal-dropout":
        if block.shape[1] < 2:
            raise InvalidInputError("vocal-dropout needs stereo audio.")
        left, right = block[:, 0], block[:, 1]
        low = _low_band((left + right) / 2, sample_rate)
        side = (left - right) / 2
        out = block.copy()
        out[:, 0] = low + side
        out[:, 1] = low - side
        return out
    if style == "reverse":
        return block[::-1].copy()
    if style == "dip":
        gain = 0.0 if dip_db is None else 10 ** (-dip_db / 20)
        return block * gain
    raise InvalidInputError(f"unknown style '{style}'. Choose one of: {', '.join(SONG_STYLES)}.")


def apply_styles(
    samples: np.ndarray,
    sample_rate: int,
    spans: Sequence[Span],
    style: str,
    dip_db: float | None = None,
) -> np.ndarray:
    """Return a copy of `samples` with each span transformed in place by `style`."""
    out = samples.copy()
    for span in spans:
        block = to_float(samples[span.start : span.end])
        processed = crossfade_edges(
            block, apply_style(block, sample_rate, style, dip_db), sample_rate
        )
        out[span.start : span.end] = from_float(processed, samples.dtype)
    return out


def style_preview(style: str, seconds: float = 2.0, sample_rate: int = 44100) -> np.ndarray:
    """A synthetic stereo clip with `style` applied to its middle second."""
    n = round(seconds * sample_rate)
    t = np.arange(n) / sample_rate
    voice = 0.3 * np.sin(2 * np.pi * 600 * t + 3 * np.sin(2 * np.pi * 5 * t))
    bass = 0.3 * np.sin(2 * np.pi * 60 * t)
    left = voice + bass + 0.2 * np.sin(2 * np.pi * 330 * t)
    right = voice + bass + 0.2 * np.sin(2 * np.pi * 495 * t)
    clip = np.stack([left, right], axis=1)
    out = apply_styles(clip, sample_rate, [Span(n // 4, 3 * n // 4, ("preview",))], style)
    peak = float(np.max(np.abs(out)))
    return out * (_PREVIEW_PEAK / peak) if peak > 0 else out
