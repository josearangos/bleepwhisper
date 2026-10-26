"""Opt-in tests with a real Whisper model: `pytest -m whisper`."""

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import soundfile as sf

from bleeper.core import process_audio

pytestmark = pytest.mark.whisper
faster_whisper = pytest.importorskip("faster_whisper")


def require_cached(model: str) -> None:
    try:
        faster_whisper.download_model(model, local_files_only=True)
    except Exception:  # noqa: BLE001 - any failure means the model is not usable offline
        pytest.skip(f"Whisper model '{model}' is not cached")


def speech(path: Path, text: str, seconds: float | None = None) -> Path:
    """Synthesize speech with macOS `say`, convert to 16 kHz mono WAV, optionally pad."""
    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        pytest.skip("needs macOS `say` and ffmpeg to synthesize speech")
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-o", str(aiff), text], check=True)
    pad = ["-af", f"apad=whole_dur={seconds}"] if seconds else []
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(aiff),
            *pad,
            "-ar",
            "16000",
            "-ac",
            "1",
            str(path),
        ],
        check=True,
    )
    aiff.unlink()
    return path


def test_real_model_masks_spoken_word(tmp_path: Path) -> None:
    require_cached("tiny")
    src = speech(tmp_path / "speech.wav", "Hello there, this is a pineapple test.")
    words = tmp_path / "words.txt"
    words.write_text("pineapple\n", encoding="utf-8")
    out = tmp_path / "out.wav"
    result = process_audio(src, words, out, preset="beep", model="tiny", language="en")
    assert [e.word.lower().strip(".,") for e in result.report] == ["pineapple"]
    assert json.loads(result.report_path.read_text())[0]["start"] > 0
    assert sf.info(out).frames == sf.info(src).frames


def test_one_minute_under_one_minute_with_small(tmp_path: Path) -> None:
    require_cached("small")
    sentence = "The quick brown fox jumps over the lazy dog near the pineapple stand. "
    src = speech(tmp_path / "minute.wav", sentence * 12, seconds=60)
    duration = sf.info(src).duration
    words = tmp_path / "words.txt"
    words.write_text("pineapple\n", encoding="utf-8")
    started = time.perf_counter()
    result = process_audio(src, words, tmp_path / "out.wav", preset="beep", language="en")
    elapsed = time.perf_counter() - started
    print(f"\nprocessed {duration:.1f} s of audio in {elapsed:.1f} s with 'small'")
    assert result.report
    assert elapsed < 60
