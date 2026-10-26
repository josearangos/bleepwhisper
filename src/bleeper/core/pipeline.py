"""`process_audio`: the end-to-end masking pipeline."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from bleeper.core.audio_io import AudioData, load_audio, load_mask, write_wav
from bleeper.core.errors import BleeperError, InvalidInputError, ProcessingError
from bleeper.core.masking import apply_masks, fit_to_length
from bleeper.core.matching import find_matches
from bleeper.core.models import ProcessResult, ProgressCallback, ReportEntry
from bleeper.core.presets import PRESETS, generate_preset
from bleeper.core.report import to_report, write_report
from bleeper.core.spans import build_spans
from bleeper.core.transcribe import Transcriber, WhisperTranscriber
from bleeper.core.words import load_words


def process_audio(
    input_path: str | Path,
    words_path: str | Path,
    output_path: str | Path,
    *,
    mask_path: str | Path | None = None,
    preset: str | None = None,
    model: str = "small",
    language: str | None = None,
    padding_ms: int = 80,
    report_path: str | Path | None = None,
    progress: ProgressCallback | None = None,
    transcriber: Transcriber | None = None,
) -> ProcessResult:
    """Mask every forbidden word in `input_path`; write a WAV and a JSON report."""
    input_path, words_path, output_path = Path(input_path), Path(words_path), Path(output_path)
    mask_path = Path(mask_path) if mask_path is not None else None
    report_path = Path(report_path) if report_path is not None else output_path.with_suffix(".json")
    _validate(input_path, words_path, output_path, report_path, mask_path, preset, padding_ms)
    transcriber = transcriber if transcriber is not None else WhisperTranscriber(model)
    report_progress = _Progress(progress)
    try:
        report_progress("loading", 0.0)
        entries = load_words(words_path)
        with tempfile.TemporaryDirectory(prefix="bleeper-") as tmp:
            audio, transcribe_path = load_audio(input_path, Path(tmp))
            custom = load_mask(mask_path, audio.sample_rate, Path(tmp)) if mask_path else None
            report_progress("transcribing", 0.05)
            transcription = transcriber.transcribe(
                transcribe_path,
                language,
                lambda f: report_progress("transcribing", min(0.85, 0.05 + 0.80 * f)),
            )
        report_progress("masking", 0.85)
        matches = find_matches(transcription.words, entries)
        spans = build_spans(matches, audio.sample_rate, audio.n_samples, padding_ms)
        samples = apply_masks(
            audio.samples, audio.sample_rate, spans, _mask_provider(custom, preset, audio)
        )
        report = to_report(spans, audio.sample_rate)
        report_progress("writing", 0.95)
        masked = AudioData(samples, audio.sample_rate, audio.subtype)
        _write_outputs(output_path, report_path, masked, report)
    except _CallbackError as exc:
        raise exc.original from None
    except BleeperError:
        raise
    except Exception as exc:
        raise ProcessingError(f"processing failed unexpectedly ({exc}).") from exc
    report_progress("done", 1.0)
    return ProcessResult(output_path, report_path, report, transcription.language)


class _CallbackError(Exception):
    """Carries an exception raised by the user's progress callback past error wrapping."""

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original


class _Progress:
    """Calls the optional callback with fractions clamped to [0, 1] that never go backwards."""

    def __init__(self, callback: ProgressCallback | None) -> None:
        self.callback = callback
        self.last = 0.0

    def __call__(self, stage: str, fraction: float) -> None:
        if self.callback is None:
            return
        self.last = max(self.last, min(1.0, max(0.0, fraction)))
        try:
            self.callback(stage, self.last)
        except Exception as exc:
            raise _CallbackError(exc) from exc


def _validate(
    input_path: Path,
    words_path: Path,
    output_path: Path,
    report_path: Path,
    mask_path: Path | None,
    preset: str | None,
    padding_ms: int,
) -> None:
    """Reject invalid options before any decoding or transcription."""
    if (mask_path is None) == (preset is None):
        raise InvalidInputError("pass exactly one of --mask or --preset.")
    if preset is not None and preset not in PRESETS:
        raise InvalidInputError(f"unknown preset '{preset}'. Choose one of: {', '.join(PRESETS)}.")
    if padding_ms < 0:
        raise InvalidInputError(f"padding must be 0 ms or more, got {padding_ms}.")
    for label, path in (
        ("input file", input_path),
        ("words file", words_path),
        ("mask file", mask_path),
    ):
        if path is not None and not path.is_file():
            raise InvalidInputError(f"{label} '{path}' not found. Check the path.")
    source, output, report = input_path.resolve(), output_path.resolve(), report_path.resolve()
    if output == source or report == source:
        raise InvalidInputError(
            "refusing to overwrite the input file. Choose a different output or report path."
        )
    if report == output:
        raise InvalidInputError("the report path must differ from the output path.")
    for label, path in (("output", output_path), ("report", report_path)):
        if not path.resolve().parent.is_dir():
            raise InvalidInputError(
                f"{label} directory '{path.parent}' does not exist. Create it first."
            )


def _mask_provider(
    custom: np.ndarray | None, preset: str | None, audio: AudioData
) -> Callable[[int], np.ndarray]:
    if custom is not None:
        return lambda n: fit_to_length(custom, n)
    return lambda n: generate_preset(str(preset), n, audio.sample_rate)


def _write_outputs(
    output_path: Path, report_path: Path, audio: AudioData, report: list[ReportEntry]
) -> None:
    """Write the WAV, then the report; remove the new WAV if the report cannot be written."""
    write_wav(output_path, audio)
    try:
        write_report(report_path, report)
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise
