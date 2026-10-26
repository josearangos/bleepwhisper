"""Reusable Bleeper core: mask forbidden words in audio files."""

from bleeper.core.errors import BleeperError, InvalidInputError, ProcessingError
from bleeper.core.models import (
    ProcessResult,
    ProgressCallback,
    ReportEntry,
    TranscribedWord,
    Transcription,
)
from bleeper.core.pipeline import process_audio
from bleeper.core.presets import PRESETS
from bleeper.core.transcribe import Transcriber

__all__ = [
    "PRESETS",
    "BleeperError",
    "InvalidInputError",
    "ProcessResult",
    "ProcessingError",
    "ProgressCallback",
    "ReportEntry",
    "TranscribedWord",
    "Transcriber",
    "Transcription",
    "process_audio",
]
