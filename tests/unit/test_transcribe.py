from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from bleeper.core import transcribe
from bleeper.core.errors import InvalidInputError, ProcessingError
from bleeper.core.models import TranscribedWord
from bleeper.core.transcribe import WhisperTranscriber


@dataclass
class StubWord:
    word: str
    start: float
    end: float


@dataclass
class StubSegment:
    end: float
    words: list[StubWord]


@dataclass
class StubInfo:
    duration: float
    language: str


@dataclass
class StubModel:
    calls: list[dict[str, object]] = field(default_factory=list)

    def transcribe(self, path: str, **kwargs: object) -> tuple[Iterator[StubSegment], StubInfo]:
        self.calls.append({"path": path, **kwargs})
        if kwargs.get("language") == "xx":
            raise ValueError("'xx' is not a valid language code")
        segments = [
            StubSegment(2.0, [StubWord(" Hello", 0.5, 1.0), StubWord(" world", 1.2, 2.0)]),
            StubSegment(4.0, [StubWord(" heck", 3.0, 3.5)]),
        ]
        return iter(segments), StubInfo(duration=4.0, language="es")


@pytest.fixture
def loader(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, object]]]:
    calls: list[dict[str, object]] = []
    model = StubModel()

    def create(name: str, **kwargs: object) -> StubModel:
        calls.append({"name": name, **kwargs})
        return model

    transcribe.load_model.cache_clear()
    monkeypatch.setattr(transcribe, "WhisperModel", create)
    yield calls
    transcribe.load_model.cache_clear()


def test_maps_segments_to_words_and_reports_progress(loader: list[dict[str, object]]) -> None:
    progress: list[float] = []
    result = WhisperTranscriber("tiny").transcribe(Path("a.wav"), "en", progress.append)
    assert result.words == [
        TranscribedWord(" Hello", 0.5, 1.0),
        TranscribedWord(" world", 1.2, 2.0),
        TranscribedWord(" heck", 3.0, 3.5),
    ]
    assert result.language == "en"
    assert progress == [0.5, 1.0]
    assert loader == [
        {"name": "tiny", "device": "cpu", "compute_type": "int8", "local_files_only": True}
    ]


def test_passes_word_timestamps_and_language(loader: list[dict[str, object]]) -> None:
    model = transcribe.load_model("tiny")
    WhisperTranscriber("tiny").transcribe(Path("a.wav"), None, lambda f: None)
    assert model.calls[-1] == {"path": "a.wav", "language": None, "word_timestamps": True}


def test_detected_language_is_used_when_none_requested(loader: list[dict[str, object]]) -> None:
    result = WhisperTranscriber("tiny").transcribe(Path("a.wav"), None, lambda f: None)
    assert result.language == "es"


def test_model_is_cached_per_name(loader: list[dict[str, object]]) -> None:
    WhisperTranscriber("tiny").transcribe(Path("a.wav"), None, lambda f: None)
    WhisperTranscriber("tiny").transcribe(Path("b.wav"), None, lambda f: None)
    assert len(loader) == 1


def test_downloads_only_when_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def create(name: str, **kwargs: object) -> StubModel:
        calls.append(bool(kwargs["local_files_only"]))
        if kwargs["local_files_only"]:
            raise OSError("not cached")
        return StubModel()

    transcribe.load_model.cache_clear()
    monkeypatch.setattr(transcribe, "WhisperModel", create)
    transcribe.load_model("small")
    transcribe.load_model.cache_clear()
    assert calls == [True, False]


def test_load_failure_raises_processing_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def create(name: str, **kwargs: object) -> StubModel:
        raise OSError("no network")

    transcribe.load_model.cache_clear()
    monkeypatch.setattr(transcribe, "WhisperModel", create)
    with pytest.raises(ProcessingError, match="small"):
        WhisperTranscriber("small").transcribe(Path("a.wav"), None, lambda f: None)
    transcribe.load_model.cache_clear()


def test_invalid_language_raises_invalid_input(loader: list[dict[str, object]]) -> None:
    with pytest.raises(InvalidInputError, match="xx"):
        WhisperTranscriber("tiny").transcribe(Path("a.wav"), "xx", lambda f: None)


def test_offline_missing_model_explains_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def create(name: str, **kwargs: object) -> StubModel:
        calls.append(bool(kwargs["local_files_only"]))
        raise OSError("not cached")

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("BLEEPER_MODEL", "small")
    transcribe.load_model.cache_clear()
    monkeypatch.setattr(transcribe, "WhisperModel", create)
    with pytest.raises(ProcessingError) as info:
        transcribe.load_model("tiny")
    transcribe.load_model.cache_clear()
    message = str(info.value)
    assert "'tiny'" in message
    assert "not available offline" in message
    assert "'small'" in message
    assert "--build-arg WHISPER_MODEL=tiny" in message
    assert calls == [True]
