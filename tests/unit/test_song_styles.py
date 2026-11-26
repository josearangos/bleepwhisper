import numpy as np
import pytest
from conftest import make_song

from bleeper.core import InvalidInputError, style_preview
from bleeper.core.models import Span
from bleeper.core.song_styles import (
    SONG_STYLES,
    apply_style,
    apply_styles,
    crossfade_edges,
    has_usable_stereo,
)

SR = 16000
FADE = round(0.010 * SR)


def level(x: np.ndarray, freq: float) -> float:
    """Magnitude of `freq` in a 1-D signal (rectangular window, whole-cycle friendly)."""
    t = np.arange(len(x)) / SR
    return abs(np.mean(x * np.exp(-2j * np.pi * freq * t))) * 2


def db(a: float, b: float) -> float:
    return 20 * np.log10(max(a, 1e-12) / max(b, 1e-12))


def interior(x: np.ndarray) -> np.ndarray:
    return x[FADE:-FADE]


def test_crossfade_edges_endpoints_and_middle() -> None:
    original, processed = np.zeros((1000, 2)), np.ones((1000, 2))
    out = crossfade_edges(original, processed, SR)
    assert out[0, 0] == 0.0 and out[-1, 0] == 0.0
    assert out[500, 0] == 1.0
    assert 0.0 < out[FADE // 2, 0] < 1.0


def test_crossfade_short_span_uses_half() -> None:
    out = crossfade_edges(np.zeros((100, 1)), np.ones((100, 1)), SR)
    assert out[0, 0] == 0.0 and out[-1, 0] == 0.0
    assert out[49, 0] == 1.0 and out[50, 0] == 1.0


def test_apply_styles_no_spans_is_identity() -> None:
    samples = (make_song() * 2**30).astype(np.int32)
    out = apply_styles(samples, SR, [], "dip")
    assert out.dtype == samples.dtype and np.array_equal(out, samples)


def test_unknown_style_raises() -> None:
    with pytest.raises(InvalidInputError, match="unknown style 'karaoke'"):
        apply_style(make_song(), SR, "karaoke")


def test_vocal_dropout_removes_center_keeps_music() -> None:
    song = make_song()
    out = apply_styles(song, SR, [Span(0, len(song), ("x",))], "vocal-dropout")
    assert out.shape == song.shape and out.dtype == song.dtype
    inner, ref = interior(out), interior(song)
    assert db(level(ref[:, 0], 1000), level(inner[:, 0], 1000)) >= 30
    assert abs(db(level(inner[:, 0], 60), level(ref[:, 0], 60))) <= 1
    # Hard-panned tones are half centre, half side: mid/side removal costs them 6 dB.
    assert db(level(ref[:, 0], 440), level(inner[:, 0], 440)) == pytest.approx(6.0, abs=0.5)
    assert db(level(ref[:, 1], 660), level(inner[:, 1], 660)) == pytest.approx(6.0, abs=0.5)


def test_vocal_dropout_keeps_pure_side_content() -> None:
    t = np.arange(SR * 2) / SR
    wide = 0.2 * np.sin(2 * np.pi * 800 * t)
    song = np.stack([wide, -wide], axis=1)
    out = apply_styles(song, SR, [Span(0, len(song), ("x",))], "vocal-dropout")
    assert abs(db(level(interior(out)[:, 0], 800), level(interior(song)[:, 0], 800))) <= 1


def test_has_usable_stereo() -> None:
    song = make_song()
    assert has_usable_stereo(song)
    assert not has_usable_stereo(song[:, :1])
    mono = np.repeat(song[:, :1], 2, axis=1)
    assert not has_usable_stereo(mono)
    noise = np.random.default_rng(0).standard_normal(len(song)) * 1e-4
    nearly = mono.copy()
    nearly[:, 0] += noise
    assert not has_usable_stereo(nearly)


def test_edges_are_smooth() -> None:
    song = make_song()
    span = Span(8000, 16000, ("x",))
    out = apply_styles(song, SR, [span], "vocal-dropout")
    baseline = np.max(np.abs(np.diff(song, axis=0)))
    for lo, hi in ((span.start - 2, span.start + FADE + 2), (span.end - FADE - 2, span.end + 2)):
        assert np.max(np.abs(np.diff(out[lo:hi], axis=0))) <= 1.5 * baseline


def test_reverse_plays_backwards() -> None:
    song = make_song()
    out = apply_styles(song, SR, [Span(0, len(song), ("x",))], "reverse")
    assert np.allclose(interior(out), interior(song[::-1]))
    assert out.shape == song.shape and out.dtype == song.dtype


def test_dip_default_mutes_and_db_attenuates() -> None:
    song = make_song()
    whole = [Span(0, len(song), ("x",))]
    muted = apply_styles(song, SR, whole, "dip")
    assert np.all(interior(muted) == 0.0)
    dipped = apply_styles(song, SR, whole, "dip", 20.0)
    rms = lambda x: float(np.sqrt(np.mean(np.square(x))))  # noqa: E731
    assert db(rms(interior(song)), rms(interior(dipped))) == pytest.approx(20.0, abs=0.1)
    assert dipped[0, 0] == song[0, 0]


@pytest.mark.parametrize("style", SONG_STYLES)
def test_style_preview(style: str) -> None:
    clip = style_preview(style, seconds=2.0, sample_rate=8000)
    assert clip.shape == (16000, 2) and np.all(np.isfinite(clip))
    assert np.max(np.abs(clip)) <= 1.0


def test_style_preview_unknown() -> None:
    with pytest.raises(InvalidInputError):
        style_preview("karaoke")
