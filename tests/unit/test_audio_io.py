import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from bleeper.core import audio_io
from bleeper.core.audio_io import AudioData, load_audio, load_mask, write_wav
from bleeper.core.errors import InvalidInputError, ProcessingError

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args], check=True)


@pytest.mark.parametrize(
    ("subtype", "dtype"), [("PCM_16", np.int32), ("PCM_24", np.int32), ("FLOAT", np.float32)]
)
def test_load_wav_keeps_lossless_dtype(
    make_tone: Callable[..., Path], tmp_path: Path, subtype: str, dtype: type
) -> None:
    path = make_tone(subtype=subtype, channels=2, seconds=1.0)
    audio, transcribe_path = load_audio(path, tmp_path / "tmp")
    assert audio.samples.dtype == dtype
    assert audio.samples.shape == (16000, 2)
    assert (audio.n_samples, audio.channels) == (16000, 2)
    assert (audio.sample_rate, audio.subtype) == (16000, subtype)
    assert transcribe_path == path


@pytest.mark.parametrize("subtype", ["PCM_16", "PCM_24", "FLOAT"])
def test_write_wav_round_trips_bit_identically(
    make_tone: Callable[..., Path], tmp_path: Path, subtype: str
) -> None:
    audio, _ = load_audio(make_tone(subtype=subtype, channels=2, seconds=1.0), tmp_path)
    out = tmp_path / "out" / "copy.wav"
    out.parent.mkdir()
    write_wav(out, audio)
    again, _ = load_audio(out, tmp_path)
    assert again.subtype == subtype and again.sample_rate == audio.sample_rate
    np.testing.assert_array_equal(again.samples, audio.samples)
    assert list(out.parent.iterdir()) == [out]


def test_write_wav_replaces_existing_file(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    out.write_bytes(b"old")
    write_wav(out, AudioData(np.zeros((10, 1), dtype=np.int32), 8000, "PCM_16"))
    assert sf.info(out).frames == 10
    assert list(tmp_path.iterdir()) == [out]


def test_write_wav_failure_leaves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out.wav"
    out.write_bytes(b"old")

    def broken_write(path: Path, *args: object, **kwargs: object) -> None:
        Path(path).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(audio_io.sf, "write", broken_write)
    with pytest.raises(ProcessingError):
        write_wav(out, AudioData(np.zeros((10, 1), dtype=np.int32), 8000, "PCM_16"))
    assert out.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [out]


@needs_ffmpeg
def test_mp3_is_decoded_to_pcm16_at_native_format(
    make_tone: Callable[..., Path], tmp_path: Path
) -> None:
    wav = make_tone(sr=22050, channels=2, seconds=1.0)
    mp3 = tmp_path / "input.mp3"
    ffmpeg("-i", str(wav), str(mp3))
    tmp_dir = tmp_path / "decode"
    tmp_dir.mkdir()
    audio, transcribe_path = load_audio(mp3, tmp_dir)
    assert (audio.sample_rate, audio.channels, audio.subtype) == (22050, 2, "PCM_16")
    assert audio.samples.dtype == np.int32
    assert abs(audio.n_samples - 22050) < 2000
    assert transcribe_path.parent == tmp_dir


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="nope.wav"):
        load_audio(tmp_path / "nope.wav", tmp_path)


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "audio.ogg"
    path.write_bytes(b"x")
    with pytest.raises(InvalidInputError, match="unsupported"):
        load_audio(path, tmp_path)


def test_corrupt_wav_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.wav"
    path.write_bytes(b"definitely not audio")
    with pytest.raises(InvalidInputError, match="bad.wav"):
        load_audio(path, tmp_path)


def test_mp3_without_ffmpeg_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "input.mp3"
    path.write_bytes(b"x")
    monkeypatch.setattr(audio_io.shutil, "which", lambda name: None)
    with pytest.raises(InvalidInputError, match="install ffmpeg"):
        load_audio(path, tmp_path)


def test_load_mask_returns_mono_float64(make_tone: Callable[..., Path], tmp_path: Path) -> None:
    path = make_tone("mask.wav", seconds=0.5, channels=1)
    mask = load_mask(path, 16000, tmp_path)
    assert mask.dtype == np.float64 and mask.shape == (8000,)
    expected, _ = sf.read(path, dtype="float64")
    np.testing.assert_allclose(mask, expected, atol=1e-6)


def test_load_mask_averages_stereo(tmp_path: Path) -> None:
    path = tmp_path / "mask.wav"
    sf.write(
        path, np.column_stack([np.full(100, 0.5), np.full(100, -0.25)]), 16000, subtype="FLOAT"
    )
    np.testing.assert_allclose(load_mask(path, 16000, tmp_path), np.full(100, 0.125))


@needs_ffmpeg
def test_load_mask_resamples_to_target_rate(make_tone: Callable[..., Path], tmp_path: Path) -> None:
    path = make_tone("mask.wav", seconds=1.0, sr=44100, channels=2)
    tmp_dir = tmp_path / "work"
    tmp_dir.mkdir()
    mask = load_mask(path, 16000, tmp_dir)
    assert mask.ndim == 1 and abs(len(mask) - 16000) <= 16
    assert list(tmp_dir.iterdir()) == []


def test_load_mask_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="missing.wav"):
        load_mask(tmp_path / "missing.wav", 16000, tmp_path)
