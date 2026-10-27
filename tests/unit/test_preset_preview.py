import numpy as np
import pytest

from bleeper.core import PRESETS, InvalidInputError, preset_preview


@pytest.mark.parametrize("name", PRESETS)
def test_default_length_level_and_fades(name: str) -> None:
    samples = preset_preview(name)
    assert samples.dtype == np.float64
    assert samples.shape == (44100,)
    assert np.max(np.abs(samples)) <= 0.5 + 1e-9
    assert samples[0] == 0.0
    assert samples[-1] == 0.0


@pytest.mark.parametrize("name", PRESETS)
def test_custom_duration_and_rate(name: str) -> None:
    assert preset_preview(name, seconds=0.5, sample_rate=16000).shape == (8000,)


def test_unknown_preset() -> None:
    with pytest.raises(InvalidInputError, match="nope"):
        preset_preview("nope")
