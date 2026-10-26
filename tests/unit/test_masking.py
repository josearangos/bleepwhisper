import numpy as np
import pytest

from bleeper.core.errors import InvalidInputError
from bleeper.core.masking import apply_masks, fit_to_length, to_float
from bleeper.core.models import Span

SR = 16000
FADE = SR // 100  # 10 ms


def ones(n: int) -> np.ndarray:
    return np.ones(n)


def sine(seconds: float, amp: float, channels: int = 1, freq: float = 220.0) -> np.ndarray:
    t = np.arange(round(seconds * SR)) / SR
    return np.repeat((amp * np.sin(2 * np.pi * freq * t))[:, None], channels, axis=1)


def as_int32(x: np.ndarray) -> np.ndarray:
    return np.round(x * 2**31).astype(np.int32)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def db(a: float, b: float) -> float:
    return abs(20 * np.log10(a / b))


def span(start_s: float, end_s: float) -> Span:
    return Span(round(start_s * SR), round(end_s * SR), ("x",))


@pytest.mark.parametrize("dtype", ["int32", "float32"])
def test_outside_spans_bit_identical_and_input_untouched(dtype: str) -> None:
    audio = sine(3, 0.3, channels=2)
    samples = as_int32(audio) if dtype == "int32" else audio.astype(np.float32)
    original = samples.copy()
    s = span(1.0, 1.5)
    out = apply_masks(samples, SR, [s], ones)
    assert out is not samples
    assert out.dtype == samples.dtype
    np.testing.assert_array_equal(samples, original)
    np.testing.assert_array_equal(out[: s.start], original[: s.start])
    np.testing.assert_array_equal(out[s.end :], original[s.end :])
    assert not np.array_equal(out[s.start : s.end], original[s.start : s.end])


def test_level_matches_surrounding_rms() -> None:
    samples = sine(3, 0.3).astype(np.float32)
    s = span(1.0, 1.5)
    out = apply_masks(samples, SR, [s], ones)
    context = np.concatenate(
        [samples[s.start - SR // 2 : s.start], samples[s.end : s.end + SR // 2]]
    )
    interior = out[s.start + FADE : s.end - FADE]
    assert db(rms(interior), rms(context)) < 1


def test_context_is_clamped_at_audio_edges() -> None:
    samples = sine(2, 0.3).astype(np.float32)
    s = span(0.0, 0.4)
    out = apply_masks(samples, SR, [s], ones)
    interior = out[s.start + FADE : s.end - FADE]
    assert db(rms(interior), rms(samples[s.end : s.end + SR // 2])) < 1


def test_level_uses_original_audio_not_previous_masks() -> None:
    loud = sine(1.0, 0.8)
    quiet = sine(2.0, 0.05)
    samples = np.concatenate([loud, quiet]).astype(np.float32)
    first, second = span(1.0, 1.5), span(1.8, 2.3)
    out = apply_masks(samples, SR, [first, second], ones)
    interior = out[second.start + FADE : second.end - FADE]
    assert db(rms(interior), rms(sine(1, 0.05))) < 1


def test_silent_surroundings_use_minus_20_dbfs() -> None:
    samples = np.zeros((3 * SR, 1), dtype=np.float32)
    s = span(1.0, 1.5)
    out = apply_masks(samples, SR, [s], ones)
    assert rms(out[s.start + FADE : s.end - FADE]) == pytest.approx(0.1, rel=1e-3)


def test_peak_is_limited_below_full_scale() -> None:
    rng = np.random.default_rng(1)
    samples = (np.sign(rng.uniform(-1, 1, (3 * SR, 1))) * 0.95).astype(np.float32)
    s = span(1.0, 1.5)
    out = apply_masks(samples, SR, [s], lambda n: np.sin(np.arange(n) / 3.0))
    assert np.max(np.abs(out[s.start : s.end])) <= 0.99 + 1e-6


def test_peak_limit_for_integer_samples() -> None:
    samples = as_int32(np.full((3 * SR, 1), 0.98))
    s = span(1.0, 1.5)
    out = apply_masks(samples, SR, [s], lambda n: np.sin(np.arange(n) / 3.0))
    assert np.max(np.abs(to_float(out[s.start : s.end]))) <= 0.99 + 1e-6


def test_ten_ms_linear_fades() -> None:
    samples = np.zeros((3 * SR, 1), dtype=np.float64)
    s = span(1.0, 1.5)
    region = apply_masks(samples, SR, [s], ones)[s.start : s.end, 0]
    np.testing.assert_allclose(region[:FADE], 0.1 * np.linspace(0, 1, FADE))
    np.testing.assert_allclose(region[-FADE:], 0.1 * np.linspace(1, 0, FADE))
    assert region[0] == 0 and region[-1] == 0


def test_short_spans_use_half_span_fades() -> None:
    samples = np.zeros((SR, 1), dtype=np.float64)
    s = Span(1000, 1100, ("x",))
    region = apply_masks(samples, SR, [s], ones)[s.start : s.end, 0]
    np.testing.assert_allclose(region[:50], 0.1 * np.linspace(0, 1, 50))
    np.testing.assert_allclose(region[50:], 0.1 * np.linspace(1, 0, 50))


def test_same_mask_on_every_channel() -> None:
    samples = sine(3, 0.3, channels=3).astype(np.float32)
    s = span(1.0, 1.5)
    region = apply_masks(samples, SR, [s], lambda n: np.sin(np.arange(n) / 5.0))[s.start : s.end]
    np.testing.assert_array_equal(region[:, 0], region[:, 1])
    np.testing.assert_array_equal(region[:, 0], region[:, 2])


def test_fit_to_length_loops_short_mask() -> None:
    mask = np.arange(3200, dtype=np.float64)  # 200 ms
    fitted = fit_to_length(mask, 10560)
    assert fitted.shape == (10560,)
    np.testing.assert_array_equal(fitted[:3200], mask)
    np.testing.assert_array_equal(fitted[3200:6400], mask)
    np.testing.assert_array_equal(fitted[9600:], mask[:960])


def test_fit_to_length_trims_long_mask() -> None:
    mask = np.arange(32000, dtype=np.float64)  # 2 s
    np.testing.assert_array_equal(fit_to_length(mask, 10560), mask[:10560])


def test_fit_to_length_rejects_empty_mask() -> None:
    with pytest.raises(InvalidInputError, match="empty"):
        fit_to_length(np.zeros(0), 100)
