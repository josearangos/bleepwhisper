from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from bleeper.core import ProcessingError, pipeline
from bleeper.core.models import TranscribedWord
from bleeper.ui import worker as worker_module
from bleeper.ui.jobs import Job, JobStatus, JobStore, now
from bleeper.ui.submit import create_job
from bleeper.ui.worker import JobWorker

DAMN = [TranscribedWord(" damn", 2.0, 2.5)]


def submit(
    store: JobStore,
    worker: JobWorker,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    name: str = "clip.wav",
) -> Job:
    job = create_job(
        store,
        make_tone(name, seconds=5.0),
        words_file(["damn"]),
        language="Auto",
        preset="Classic beep",
        custom_mask=None,
    )
    worker.submit(job.id)
    return job


def test_job_runs_to_done(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    worker = make_worker(fake_transcriber(DAMN))
    job = submit(store, worker, make_tone, words_file)
    seen: list[int] = []

    def finished() -> bool:
        current = store.get(job.id)
        assert current is not None
        seen.append(current.progress)
        return current.status == JobStatus.DONE

    wait_for(finished)
    done = store.get(job.id)
    assert done is not None
    assert done.progress == 100
    assert done.masked_count == 1
    assert done.finished_at is not None
    assert done.error is None
    assert done.output_file == f"jobs/{job.id}/clip_masked.wav"
    assert done.report_file == f"jobs/{job.id}/clip_masked.json"
    assert (store.data_dir / done.output_file).is_file()
    assert (store.data_dir / done.report_file).is_file()
    job_dir = store.job_dir(job.id)
    assert not (job_dir / "input.wav").exists()
    assert not (job_dir / "words.txt").exists()
    assert seen == sorted(seen)


def test_second_job_queued_while_first_runs(
    store: JobStore,
    make_worker: Callable,
    blocking_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    fake = blocking_transcriber(DAMN)
    worker = make_worker(fake)
    a = submit(store, worker, make_tone, words_file, "a.wav")
    b = submit(store, worker, make_tone, words_file, "b.wav")
    assert fake.started.wait(5)

    assert store.get(a.id).status == JobStatus.RUNNING  # type: ignore[union-attr]
    queued = store.get(b.id)
    assert queued is not None
    assert queued.status == JobStatus.QUEUED
    assert queued.progress == 0
    fake.release.set()
    for job in (a, b):
        wait_for(lambda job=job: store.get(job.id).status == JobStatus.DONE)  # type: ignore[union-attr]


def test_fifo_order(
    store: JobStore,
    make_worker: Callable,
    blocking_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    fake = blocking_transcriber(DAMN)
    worker = make_worker(fake)
    jobs = [submit(store, worker, make_tone, words_file, f"{name}.wav") for name in "abc"]
    starts: dict[str, str] = {}
    original_start = store.start

    def record_start(job_id: str) -> None:
        starts[job_id] = now()
        original_start(job_id)

    store.start = record_start  # type: ignore[method-assign]
    fake.release.set()
    wait_for(lambda: all(store.get(j.id).status == JobStatus.DONE for j in jobs))  # type: ignore[union-attr]

    order = [Path(path).parent.name for path, _ in fake.calls]
    assert order == [job.id for job in jobs]
    a, b = (store.get(job.id) for job in jobs[:2])
    assert a is not None and b is not None and a.finished_at is not None
    assert b.created_at <= starts[b.id]
    assert a.finished_at <= starts[b.id]


def test_single_transcriber_instance(
    monkeypatch: pytest.MonkeyPatch,
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    def forbidden(*_args: object) -> None:
        raise AssertionError("the worker must not build another transcriber")

    monkeypatch.setattr(worker_module, "WhisperTranscriber", forbidden)
    monkeypatch.setattr(pipeline, "WhisperTranscriber", forbidden)
    fake = fake_transcriber(DAMN)
    worker = make_worker(fake)
    jobs = [submit(store, worker, make_tone, words_file, f"{name}.wav") for name in "xyz"]
    wait_for(lambda: all(store.get(j.id).status == JobStatus.DONE for j in jobs))  # type: ignore[union-attr]
    assert worker.transcriber is fake
    assert len(fake.calls) == 3


class FailOnce:
    """Raises `error` on the first call, then behaves like `fallback`."""

    def __init__(self, error: Exception, fallback: object) -> None:
        self.error = error
        self.fallback = fallback
        self.calls = 0

    def transcribe(self, *args: Any) -> object:  # noqa: ANN401
        self.calls += 1
        if self.calls == 1:
            raise self.error
        return self.fallback.transcribe(*args)  # type: ignore[attr-defined]


def test_failed_job_does_not_stop_worker(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    error = ProcessingError("transcription failed (boom).")
    worker = make_worker(FailOnce(error, fake_transcriber(DAMN)))
    a = submit(store, worker, make_tone, words_file, "a.wav")
    b = submit(store, worker, make_tone, words_file, "b.wav")
    wait_for(lambda: store.get(b.id).status == JobStatus.DONE)  # type: ignore[union-attr]

    failed = store.get(a.id)
    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.error == "transcription failed (boom)."
    assert failed.finished_at is not None
    assert failed.output_file is None
    assert sorted(p.name for p in store.job_dir(a.id).iterdir()) == []


def test_failing_transcriber_fixture(
    store: JobStore,
    make_worker: Callable,
    failing_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    worker = make_worker(failing_transcriber())
    job = submit(store, worker, make_tone, words_file)
    wait_for(lambda: store.get(job.id).status == JobStatus.FAILED)  # type: ignore[union-attr]
    assert store.get(job.id).error == "transcription failed (boom)."  # type: ignore[union-attr]


def test_unexpected_exception_message(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    worker = make_worker(FailOnce(RuntimeError("x"), fake_transcriber(DAMN)))
    job = submit(store, worker, make_tone, words_file)
    wait_for(lambda: store.get(job.id).status == JobStatus.FAILED)  # type: ignore[union-attr]
    assert store.get(job.id).error == "processing failed unexpectedly (x)."  # type: ignore[union-attr]


def test_deleted_queued_job_never_runs(
    store: JobStore,
    make_worker: Callable,
    blocking_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    fake = blocking_transcriber(DAMN)
    worker = make_worker(fake)
    a = submit(store, worker, make_tone, words_file, "a.wav")
    assert fake.started.wait(5)
    b = submit(store, worker, make_tone, words_file, "b.wav")
    store.delete(b.id)
    fake.release.set()
    wait_for(lambda: store.get(a.id).status == JobStatus.DONE)  # type: ignore[union-attr]
    worker.join(timeout=5)

    assert len(fake.calls) == 1
    assert store.get(b.id) is None
    assert not store.job_dir(b.id).exists()
