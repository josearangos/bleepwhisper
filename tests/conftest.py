"""Shared fixtures: synthetic audio, words files and a fake transcriber."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from bleeper.core.models import TranscribedWord, Transcription

ToneFactory = Callable[..., Path]
WordsFactory = Callable[[list[str]], Path]


class FakeTranscriber:
    """Returns fixed words without loading a model; records every call."""

    def __init__(self, words: list[TranscribedWord], language: str = "en") -> None:
        self.words = words
        self.language = language
        self.calls: list[tuple[Path, str | None]] = []

    def transcribe(
        self, audio_path: Path, language: str | None, on_progress: Callable[[float], None]
    ) -> Transcription:
        self.calls.append((audio_path, language))
        on_progress(0.5)
        on_progress(1.0)
        return Transcription(list(self.words), language or self.language)


@pytest.fixture
def make_tone(tmp_path: Path) -> ToneFactory:
    def factory(
        name: str = "input.wav",
        seconds: float = 5.0,
        sr: int = 16000,
        channels: int = 1,
        subtype: str = "PCM_16",
        freq: float = 220.0,
        amp: float = 0.3,
    ) -> Path:
        t = np.arange(round(seconds * sr)) / sr
        mono = amp * np.sin(2 * np.pi * freq * t)
        data = np.repeat(mono[:, None], channels, axis=1)
        path = tmp_path / name
        sf.write(path, data, sr, subtype=subtype)
        return path

    return factory


@pytest.fixture
def words_file(tmp_path: Path) -> WordsFactory:
    def factory(lines: list[str], name: str = "words.txt") -> Path:
        path = tmp_path / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return factory


@pytest.fixture
def fake_transcriber() -> type[FakeTranscriber]:
    return FakeTranscriber
