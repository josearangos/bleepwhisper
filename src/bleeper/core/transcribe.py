"""Transcriber protocol and the faster-whisper implementation."""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from faster_whisper import WhisperModel

from bleeper.core.errors import InvalidInputError, ProcessingError
from bleeper.core.models import TranscribedWord, Transcription


class Transcriber(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        language: str | None,
        on_progress: Callable[[float], None],
    ) -> Transcription: ...


@functools.lru_cache(maxsize=4)
def load_model(name: str) -> Any:  # noqa: ANN401 - faster-whisper model object
    """Load a cached model offline; download it only when it is not cached yet."""
    options = {"device": "cpu", "compute_type": "int8"}
    try:
        return WhisperModel(name, **options, local_files_only=True)
    except Exception:  # noqa: BLE001 - not cached (or not loadable offline): try downloading
        pass
    if os.environ.get("HF_HUB_OFFLINE", "").lower() in {"1", "true", "yes", "on"}:
        baked = os.environ.get("BLEEPER_MODEL", "its build-time model")
        raise ProcessingError(
            f"Whisper model '{name}' is not available offline (HF_HUB_OFFLINE is set). In Docker "
            f"this image contains '{baked}'; rebuild with: docker compose build --build-arg "
            f"WHISPER_MODEL={name}. Natively, unset HF_HUB_OFFLINE once so it can be downloaded."
        )
    try:
        return WhisperModel(name, **options, local_files_only=False)
    except Exception as exc:
        raise ProcessingError(
            f"cannot load Whisper model '{name}' ({exc}). Check the model name, or connect to "
            "the internet once so it can be downloaded."
        ) from exc


class WhisperTranscriber:
    """faster-whisper on CPU (int8) with word timestamps; holds no per-call state."""

    def __init__(self, model: str = "small") -> None:
        self.model = model

    def transcribe(
        self,
        audio_path: Path,
        language: str | None,
        on_progress: Callable[[float], None],
    ) -> Transcription:
        model = load_model(self.model)
        try:
            segments, info = model.transcribe(
                str(audio_path), language=language, word_timestamps=True
            )
            words: list[TranscribedWord] = []
            for segment in segments:
                words.extend(TranscribedWord(w.word, w.start, w.end) for w in segment.words or [])
                if info.duration > 0:
                    on_progress(min(1.0, segment.end / info.duration))
        except ValueError as exc:
            if language is not None and "language" in str(exc):
                raise InvalidInputError(
                    f"unknown language code '{language}'. Use a code such as 'en' or 'es', or "
                    "omit --lang to auto-detect."
                ) from None
            raise ProcessingError(f"transcription failed ({exc}).") from exc
        return Transcription(words, language or info.language)
