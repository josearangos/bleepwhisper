"""Shared fixtures: synthetic audio, words files, fake transcribers and a UI job store."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from bleeper.core import ProcessingError
from bleeper.core.models import TranscribedWord, Transcription
from bleeper.core.transcribe import Transcriber
from bleeper.ui.jobs import JobStore
from bleeper.ui.worker import JobWorker

ToneFactory = Callable[..., Path]
WordsFactory = Callable[[list[str]], Path]
WaitFor = Callable[..., None]
WorkerFactory = Callable[[Transcriber], JobWorker]


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


class BlockingTranscriber(FakeTranscriber):
    """Signals `started` and waits for `release` before returning."""

    def __init__(self, words: list[TranscribedWord], language: str = "en") -> None:
        super().__init__(words, language)
        self.started = threading.Event()
        self.release = threading.Event()

    def transcribe(
        self, audio_path: Path, language: str | None, on_progress: Callable[[float], None]
    ) -> Transcription:
        self.started.set()
        self.release.wait(timeout=10)
        return super().transcribe(audio_path, language, on_progress)


class FailingTranscriber(FakeTranscriber):
    """Always raises like a failed faster-whisper run."""

    def __init__(self) -> None:
        super().__init__([])

    def transcribe(
        self, audio_path: Path, language: str | None, on_progress: Callable[[float], None]
    ) -> Transcription:
        self.calls.append((audio_path, language))
        raise ProcessingError("transcription failed (boom).")


def wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    """Poll `predicate` every 10 ms; fail the test if it is still false after `timeout`."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            pytest.fail(f"condition not met within {timeout} s")
        time.sleep(0.01)


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


@pytest.fixture
def blocking_transcriber() -> type[BlockingTranscriber]:
    return BlockingTranscriber


@pytest.fixture
def failing_transcriber() -> type[FailingTranscriber]:
    return FailingTranscriber


@pytest.fixture
def store(tmp_path: Path) -> JobStore:
    return JobStore(tmp_path / "data")


@pytest.fixture(name="wait_for")
def wait_for_fixture() -> WaitFor:
    return wait_for


@pytest.fixture
def make_worker(store: JobStore) -> Iterator[WorkerFactory]:
    """Start a worker on `store` with the given transcriber; stopped after the test."""
    workers: list[JobWorker] = []

    def factory(transcriber: Transcriber) -> JobWorker:
        worker = JobWorker(store, transcriber=transcriber)
        worker.start()
        workers.append(worker)
        return worker

    yield factory
    for worker in workers:
        release = getattr(worker.transcriber, "release", None)
        if release is not None:
            release.set()
        worker.join(timeout=5)
