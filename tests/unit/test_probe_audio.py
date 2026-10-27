import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from bleeper.core import AudioInfo, InvalidInputError, probe_audio


def test_wav_header(make_tone: Callable[..., Path]) -> None:
    info = probe_audio(make_tone("stereo.wav", seconds=2.5, channels=2))
    assert info == AudioInfo(duration=pytest.approx(2.5), sample_rate=16000, channels=2)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_mp3_duration(make_tone: Callable[..., Path], tmp_path: Path) -> None:
    wav = make_tone("three.wav", seconds=3.0)
    mp3 = tmp_path / "three.mp3"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(wav), str(mp3)], check=True
    )
    assert probe_audio(mp3).duration == pytest.approx(3.0, abs=0.1)


@pytest.mark.parametrize("name", ["clip.ogg", "notes.txt"])
def test_unsupported_extension(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"data")
    with pytest.raises(InvalidInputError, match=r"\.wav or \.mp3"):
        probe_audio(path)


def test_corrupt_wav(tmp_path: Path) -> None:
    path = tmp_path / "bad.wav"
    path.write_bytes(np.random.default_rng(0).bytes(4096))
    with pytest.raises(InvalidInputError, match="not a valid audio file"):
        probe_audio(path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="not found"):
        probe_audio(tmp_path / "missing.wav")
