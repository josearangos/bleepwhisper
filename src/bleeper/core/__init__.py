"""Reusable Bleeper core: mask forbidden words in audio files."""

from bleeper.core.audio_io import AudioInfo, probe_audio
from bleeper.core.errors import BleeperError, InvalidInputError, ProcessingError
from bleeper.core.models import (
    ProcessResult,
    ProgressCallback,
    ReportEntry,
    TranscribedWord,
    Transcription,
)
from bleeper.core.pipeline import process_audio
from bleeper.core.presets import PRESETS, preset_preview
from bleeper.core.song_styles import SONG_STYLES, style_preview
from bleeper.core.transcribe import Transcriber
from bleeper.core.words import load_words

__all__ = [
    "PRESETS",
    "SONG_STYLES",
    "AudioInfo",
    "BleeperError",
    "InvalidInputError",
    "ProcessResult",
    "ProcessingError",
    "ProgressCallback",
    "ReportEntry",
    "TranscribedWord",
    "Transcriber",
    "Transcription",
    "load_words",
    "preset_preview",
    "probe_audio",
    "process_audio",
    "style_preview",
]
