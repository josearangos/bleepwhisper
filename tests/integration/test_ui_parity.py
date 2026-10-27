"""The UI worker must produce byte-identical output to the CLI for the same inputs."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from bleeper import cli
from bleeper.core import pipeline
from bleeper.core.models import TranscribedWord
from bleeper.ui.jobs import JobStatus, JobStore
from bleeper.ui.submit import create_job

DAMN = [TranscribedWord(" damn", 2.0, 2.5), TranscribedWord(" fine", 2.6, 3.0)]


def run_cli(monkeypatch: pytest.MonkeyPatch, fake: object, args: list[str], tmp_path: Path) -> Path:
    monkeypatch.setattr(pipeline, "WhisperTranscriber", lambda model: fake)
    out = tmp_path / "cli" / "out.wav"
    out.parent.mkdir()
    assert cli.main([*args, "-o", str(out)]) == 0
    return out


def run_ui(
    store: JobStore,
    make_worker: Callable,
    fake: object,
    wait_for: Callable[..., None],
    audio: Path,
    words: Path,
    language: str,
    preset: str,
    custom_mask: Path | None = None,
) -> Path:
    worker = make_worker(fake)
    job = create_job(store, audio, words, language, preset, custom_mask)
    worker.submit(job.id)
    wait_for(lambda: store.get(job.id).status == JobStatus.DONE)  # type: ignore[union-attr]
    done = store.get(job.id)
    assert done is not None and done.output_file is not None
    return store.data_dir / done.output_file


def test_wav_and_report_bytes_match_cli(
    monkeypatch: pytest.MonkeyPatch,
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
    tmp_path: Path,
) -> None:
    audio = make_tone("speech.wav", seconds=5.0, channels=2)
    words = words_file(["damn"])
    cli_fake, ui_fake = fake_transcriber(DAMN), fake_transcriber(DAMN)
    args = [str(audio), "--words", str(words), "--preset", "beep", "--lang", "es"]
    cli_out = run_cli(monkeypatch, cli_fake, args, tmp_path)
    ui_out = run_ui(store, make_worker, ui_fake, wait_for, audio, words, "Spanish", "Classic beep")

    assert ui_out.read_bytes() == cli_out.read_bytes()
    assert ui_out.with_suffix(".json").read_bytes() == cli_out.with_suffix(".json").read_bytes()
    assert cli_fake.calls[0][1] == "es"
    assert ui_fake.calls[0][1] == "es"


def test_no_match_output_equals_input(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    audio = make_tone("quiet.wav", seconds=3.0)
    words = words_file(["nothing"])
    fake = fake_transcriber(DAMN)
    ui_out = run_ui(store, make_worker, fake, wait_for, audio, words, "Auto", "Low tone")

    expected, expected_sr = sf.read(audio, dtype="int32")
    actual, actual_sr = sf.read(ui_out, dtype="int32")
    assert actual_sr == expected_sr
    np.testing.assert_array_equal(actual, expected)


def test_custom_mask_parity(
    monkeypatch: pytest.MonkeyPatch,
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
    tmp_path: Path,
) -> None:
    audio = make_tone("speech.wav", seconds=5.0, sr=22050)
    quack = make_tone("quack.wav", seconds=0.2, sr=16000, freq=660.0)
    words = words_file(["damn"])
    cli_fake, ui_fake = fake_transcriber(DAMN), fake_transcriber(DAMN)
    args = [str(audio), "--words", str(words), "--mask", str(quack)]
    cli_out = run_cli(monkeypatch, cli_fake, args, tmp_path)
    ui_out = run_ui(
        store, make_worker, ui_fake, wait_for, audio, words, "Auto", "Noise burst", quack
    )

    assert ui_out.read_bytes() == cli_out.read_bytes()
    assert ui_out.with_suffix(".json").read_bytes() == cli_out.with_suffix(".json").read_bytes()
    assert not list(ui_out.parent.glob("mask.*"))
