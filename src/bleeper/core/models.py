"""Immutable value types shared across the core."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ProgressCallback = Callable[[str, float], None]


@dataclass(frozen=True)
class TranscribedWord:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Transcription:
    words: list[TranscribedWord]
    language: str


@dataclass(frozen=True)
class Match:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    words: tuple[str, ...]


@dataclass(frozen=True)
class ReportEntry:
    word: str
    start: float
    end: float

    def to_dict(self) -> dict[str, str | float]:
        return {"word": self.word, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class ProcessResult:
    output_path: Path
    report_path: Path
    report: list[ReportEntry]
    language: str
