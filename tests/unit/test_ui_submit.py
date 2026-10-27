import re
from collections.abc import Callable
from pathlib import Path

import pytest

from bleeper.core import InvalidInputError
from bleeper.ui import submit
from bleeper.ui.jobs import JobStatus, JobStore
from bleeper.ui.submit import create_job


def test_create_job_happy_path(
    store: JobStore, make_tone: Callable[..., Path], words_file: Callable[..., Path]
) -> None:
    audio = make_tone("Interview.WAV", seconds=1.0)
    words = words_file(["damn"])
    audio_bytes, words_bytes = audio.read_bytes(), words.read_bytes()

    job = create_job(
        store, audio, words, language="Spanish", preset="Classic beep", custom_mask=None
    )

    assert job.status == JobStatus.QUEUED
    assert job.progress == 0
    assert job.filename == "Interview.WAV"
    assert job.language == "Spanish"
    assert job.language_code == "es"
    assert job.mask == "beep"
    assert re.fullmatch(r"[0-9a-f]{12}", job.id)
    assert store.get(job.id) == job
    job_dir = store.data_dir / "jobs" / job.id
    assert (job_dir / "input.wav").read_bytes() == audio_bytes
    assert (job_dir / "words.txt").read_bytes() == words_bytes
    assert audio.read_bytes() == audio_bytes
    assert words.read_bytes() == words_bytes


def rejected(store: JobStore, message: str, **inputs: object) -> str:
    """Submit with defaults overridden by `inputs`; assert it fails and leaves no trace."""
    args = {"language": "Auto", "preset": "Classic beep", "custom_mask": None} | inputs
    with pytest.raises(InvalidInputError) as info:
        create_job(store, **args)  # type: ignore[arg-type]
    assert message in str(info.value)
    assert store.list() == []
    assert not (store.data_dir / "jobs").exists()
    return str(info.value)


@pytest.fixture
def valid(make_tone: Callable[..., Path], words_file: Callable[..., Path]) -> dict[str, Path]:
    return {"audio": make_tone("talk.wav", seconds=2.0), "words": words_file(["damn"])}


def test_no_audio(store: JobStore, valid: dict[str, Path]) -> None:
    assert (
        rejected(store, "", audio=None, words=valid["words"])
        == "Please upload an audio file (.wav or .mp3)."
    )


def test_wrong_audio_type(store: JobStore, valid: dict[str, Path], tmp_path: Path) -> None:
    ogg = tmp_path / "song.ogg"
    ogg.write_bytes(b"OggS")
    assert (
        rejected(store, "", audio=ogg, words=valid["words"])
        == "Unsupported audio format '.ogg'. Use a .wav or .mp3 file."
    )


def test_too_large(
    monkeypatch: pytest.MonkeyPatch, store: JobStore, valid: dict[str, Path]
) -> None:
    monkeypatch.setattr(submit, "MAX_BYTES", 1000)
    size = valid["audio"].stat().st_size / 1024**2
    message = rejected(store, "the limit is 100 MB", **valid)
    assert message == (
        f"'talk.wav' is {size:.1f} MB; the limit is 100 MB. Trim or compress the file and try "
        "again."
    )


def test_exactly_at_size_limit_is_accepted(
    monkeypatch: pytest.MonkeyPatch, store: JobStore, valid: dict[str, Path]
) -> None:
    monkeypatch.setattr(submit, "MAX_BYTES", valid["audio"].stat().st_size)
    create_job(store, language="Auto", preset="Classic beep", custom_mask=None, **valid)
    assert len(store.list()) == 1


def test_unreadable_audio(store: JobStore, valid: dict[str, Path], tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio at all" * 64)
    rejected(
        store, "cannot read 'bad.wav': not a valid audio file", audio=bad, words=valid["words"]
    )


def test_zero_length_audio(
    store: JobStore, valid: dict[str, Path], make_tone: Callable[..., Path]
) -> None:
    empty = make_tone("empty.wav", seconds=0.0)
    assert (
        rejected(store, "", audio=empty, words=valid["words"])
        == "'empty.wav' contains no audio. Check the file."
    )


def test_too_long(monkeypatch: pytest.MonkeyPatch, store: JobStore, valid: dict[str, Path]) -> None:
    monkeypatch.setattr(submit, "MAX_SECONDS", 1.0)
    assert (
        rejected(store, "0:02 long; the limit is 30:00", **valid)
        == "'talk.wav' is 0:02 long; the limit is 30:00. Split the file and try again."
    )


def test_no_words(store: JobStore, valid: dict[str, Path]) -> None:
    assert (
        rejected(store, "", audio=valid["audio"], words=None)
        == "Please upload a forbidden words file (.txt, one word or phrase per line)."
    )


def test_words_only_blanks_and_comments(
    store: JobStore, valid: dict[str, Path], words_file: Callable[..., Path]
) -> None:
    words = words_file(["", "# a comment", "   "], name="list.txt")
    message = rejected(store, "no forbidden words found", audio=valid["audio"], words=words)
    assert "list.txt" in message
    assert str(words.parent) not in message


def test_words_not_utf8(store: JobStore, valid: dict[str, Path], tmp_path: Path) -> None:
    words = tmp_path / "latin1.txt"
    words.write_bytes("groser\xeda\n".encode("latin-1"))
    rejected(store, "must be UTF-8", audio=valid["audio"], words=words)


def test_unreadable_custom_mask(store: JobStore, valid: dict[str, Path], tmp_path: Path) -> None:
    mask = tmp_path / "quack.wav"
    mask.write_bytes(b"garbage" * 100)
    message = rejected(store, "", custom_mask=mask, **valid)
    assert message.startswith("Custom mask: ")
    assert "quack.wav" in message


def test_custom_mask_overrides_preset(
    store: JobStore, valid: dict[str, Path], make_tone: Callable[..., Path]
) -> None:
    quack = make_tone("quack.wav", seconds=0.3, freq=700.0)
    job = create_job(store, language="Auto", preset="Low tone", custom_mask=quack, **valid)
    assert job.mask == "custom: quack.wav"
    assert (store.job_dir(job.id) / "mask.wav").read_bytes() == quack.read_bytes()

    plain = create_job(store, language="Auto", preset="Low tone", custom_mask=None, **valid)
    assert plain.mask == "tone"
    assert not list(store.job_dir(plain.id).glob("mask.*"))
