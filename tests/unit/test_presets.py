import numpy as np
import pytest

from bleeper.core.errors import InvalidInputError
from bleeper.core.presets import PRESETS, generate_preset

SR = 16000


def dominant_frequency(signal: np.ndarray, sr: int) -> float:
    spectrum = np.abs(np.fft.rfft(signal))
    return float(np.fft.rfftfreq(len(signal), 1 / sr)[np.argmax(spectrum)])


@pytest.mark.parametrize("name", PRESETS)
def test_returns_float64_mono_of_exact_length(name: str) -> None:
    mask = generate_preset(name, 1234, SR)
    assert mask.dtype == np.float64
    assert mask.shape == (1234,)
    assert np.max(np.abs(mask)) <= 1.0


@pytest.mark.parametrize(("name", "freq"), [("beep", 1000.0), ("tone", 400.0)])
def test_sine_presets_have_expected_frequency(name: str, freq: float) -> None:
    assert dominant_frequency(generate_preset(name, SR, SR), SR) == pytest.approx(freq, abs=1)


def test_noise_is_deterministic_and_not_periodic() -> None:
    first = generate_preset("noise", SR, SR)
    np.testing.assert_array_equal(first, generate_preset("noise", SR, SR))
    spectrum = np.abs(np.fft.rfft(first))
    assert spectrum.max() < 0.05 * spectrum.sum()


def test_unknown_preset_raises() -> None:
    with pytest.raises(InvalidInputError, match="quack"):
        generate_preset("quack", 10, SR)
