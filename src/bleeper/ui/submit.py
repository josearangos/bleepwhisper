"""Form option mappings, submission validation and job creation (no Gradio)."""

from __future__ import annotations

import math
import shutil
import uuid
from pathlib import Path

from bleeper.core import InvalidInputError, load_words, probe_audio
from bleeper.ui.jobs import Job, JobStatus, JobStore, now

LANGUAGES: dict[str, str | None] = {
    "Auto": None,
    "Spanish": "es",
    "English": "en",
    "Portuguese": "pt",
    "French": "fr",
    "German": "de",
    "Italian": "it",
}
MASKS: dict[str, str] = {"Classic beep": "beep", "Low tone": "tone", "Noise burst": "noise"}

MAX_BYTES = 100 * 1024 * 1024
MAX_SECONDS = 1800.0
MODEL = "small"
PADDING_MS = 80
AUDIO_SUFFIXES = {".wav", ".mp3"}


def create_job(
    store: JobStore,
    audio: str | Path | None,
    words: str | Path | None,
    language: str,
    preset: str,
    custom_mask: str | Path | None,
) -> Job:
    """Validate, copy the inputs into a new job directory and add a queued job to the store."""
    validate_submission(audio, words, custom_mask)
    audio, words = Path(str(audio)), Path(str(words))
    job_id = uuid.uuid4().hex[:12]
    job_dir = store.job_dir(job_id)
    try:
        job_dir.mkdir(parents=True)
        shutil.copyfile(audio, job_dir / f"input{audio.suffix.lower()}")
        shutil.copyfile(words, job_dir / "words.txt")
        if custom_mask is not None:
            custom_mask = Path(custom_mask)
            shutil.copyfile(custom_mask, job_dir / f"mask{custom_mask.suffix.lower()}")
    except BaseException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    job = Job(
        id=job_id,
        filename=audio.name,
        language=language,
        language_code=LANGUAGES[language],
        mask=MASKS[preset] if custom_mask is None else f"custom: {Path(custom_mask).name}",
        status=JobStatus.QUEUED,
        progress=0,
        created_at=now(),
    )
    store.add(job)
    return job


def _named(exc: InvalidInputError, path: Path) -> InvalidInputError:
    """The core's message with the upload's temp path replaced by its file name."""
    return InvalidInputError(str(exc).replace(str(path), path.name))


def validate_submission(
    audio: str | Path | None, words: str | Path | None, custom_mask: str | Path | None
) -> int:
    """Check the form in order; raise the first problem. Returns the forbidden-entry count."""
    if audio is None:
        raise InvalidInputError("Please upload an audio file (.wav or .mp3).")
    audio = Path(audio)
    name, suffix = audio.name, audio.suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise InvalidInputError(
            f"Unsupported audio format '{suffix or name}'. Use a .wav or .mp3 file."
        )
    size = audio.stat().st_size
    if size > MAX_BYTES:
        raise InvalidInputError(
            f"'{name}' is {size / 1024**2:.1f} MB; the limit is 100 MB. "
            "Trim or compress the file and try again."
        )
    try:
        duration = probe_audio(audio).duration
    except InvalidInputError as exc:
        raise _named(exc, audio) from None
    if duration <= 0:
        raise InvalidInputError(f"'{name}' contains no audio. Check the file.")
    if duration > MAX_SECONDS:
        minutes, seconds = divmod(math.ceil(duration), 60)
        raise InvalidInputError(
            f"'{name}' is {minutes}:{seconds:02d} long; the limit is 30:00. "
            "Split the file and try again."
        )
    if words is None:
        raise InvalidInputError(
            "Please upload a forbidden words file (.txt, one word or phrase per line)."
        )
    words = Path(words)
    try:
        count = len(load_words(words))
    except InvalidInputError as exc:
        raise _named(exc, words) from None
    if custom_mask is not None:
        custom_mask = Path(custom_mask)
        try:
            probe_audio(custom_mask)
        except InvalidInputError as exc:
            raise InvalidInputError(f"Custom mask: {_named(exc, custom_mask)}") from None
    return count
