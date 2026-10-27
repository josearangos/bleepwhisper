"""Gradio layer: build the Blocks without launching and call the handlers directly."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gradio as gr
import numpy as np
import pytest

from bleeper.core.models import TranscribedWord
from bleeper.ui import app
from bleeper.ui.jobs import JobStatus, JobStore
from bleeper.ui.submit import MASKS, create_job

DAMN = [TranscribedWord(" damn", 2.0, 2.5)]


def select_event(row: list[str]) -> gr.SelectData:
    return gr.SelectData(None, {"index": [0, 0], "value": row[0], "row_value": row})


def test_build_app_and_happy_flow(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    worker = make_worker(fake_transcriber(DAMN))
    assert isinstance(app.build_app(store, worker), gr.Blocks)

    status, table, *uploads = app.submit_handler(
        store,
        worker,
        make_tone("talk.wav"),
        "Auto",
        words_file(["damn", "heck"]),
        "Classic beep",
        None,
    )

    assert status.startswith("✅ Job ")
    assert "talk.wav (2 forbidden words, mask: beep)" in status
    job_id = store.list()[0].id
    assert [row[0] for row in table] == [job_id]
    wait_for(lambda: store.get(job_id).status == JobStatus.DONE)  # type: ignore[union-attr]
    row = app.render_table(store)[0]
    headers = app.TABLE_HEADERS
    assert row[headers.index("Status")] == "done"
    assert row[headers.index("Progress")] == "100%"
    assert row[headers.index("Masked")] == "1"

    view = app.render_details(store, job_id)
    wav = store.job_dir(job_id) / "talk_masked.wav"
    assert view.audio_path == str(wav.resolve())
    assert view.wav_path == str(wav.resolve())
    assert view.json_path == str(wav.with_suffix(".json").resolve())
    assert "1 masked word" in view.summary_md
    assert view.signature == (job_id, "done")


def test_empty_table_and_panel(store: JobStore) -> None:
    rows = app.render_table(store)
    assert len(rows) == 1
    assert rows[0][0] == ""
    assert rows[0][1] == "No jobs yet. Submit an audio file above."
    view = app.render_details(store, None)
    assert view.summary_md == "Select a job in the table to see its result."
    assert view.audio_path is None
    assert not view.can_delete


def test_submit_deletes_uploads(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
) -> None:
    worker = make_worker(fake_transcriber(DAMN))
    audio, words = make_tone("a.wav"), words_file(["damn"])
    _, _, *uploads = app.submit_handler(store, worker, audio, "Auto", words, "Classic beep", None)
    assert uploads == [None, None, None]
    assert not audio.exists()
    assert not words.exists()

    audio, empty = make_tone("b.wav"), words_file(["# only a comment"], name="empty.txt")
    count = len(store.list())
    status, *_ = app.submit_handler(store, worker, audio, "Auto", empty, "Classic beep", None)
    assert status.startswith("❌ ")
    assert audio.exists()
    assert empty.exists()
    assert len(store.list()) == count


def test_select_uses_row_id_not_position(
    store: JobStore, make_tone: Callable[..., Path], words_file: Callable[..., Path]
) -> None:
    def new_job(name: str) -> str:
        return create_job(
            store, make_tone(name), words_file(["damn"]), "Auto", "Classic beep", None
        ).id

    a = new_job("a.wav")
    b = new_job("b.wav")
    rendered = {row[0]: row for row in app.render_table(store)}
    new_job("c.wav")

    assert app.on_select(store, select_event(rendered[a])) == a
    assert app.on_select(store, select_event(rendered[b])) == b
    hint = app.render_table(JobStore(store.data_dir / "other"))[0]
    assert app.on_select(store, select_event(hint), current=a) == a


def test_submit_is_non_blocking(
    store: JobStore,
    make_worker: Callable,
    blocking_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
) -> None:
    fake = blocking_transcriber(DAMN)
    worker = make_worker(fake)
    app.submit_handler(
        store, worker, make_tone("one.wav"), "Auto", words_file(["damn"]), "Classic beep", None
    )
    assert fake.started.wait(5)

    began = time.perf_counter()
    _, table, *_ = app.submit_handler(
        store, worker, make_tone("two.wav"), "Auto", words_file(["damn"]), "Low tone", None
    )
    assert time.perf_counter() - began < 1.0
    rows = {row[1]: row for row in table}
    assert rows["two.wav"][app.TABLE_HEADERS.index("Status")] == "queued"
    assert rows["two.wav"][app.TABLE_HEADERS.index("Progress")] == "0%"


def test_submit_without_audio_shows_error(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    words_file: Callable[..., Path],
) -> None:
    worker = make_worker(fake_transcriber(DAMN))
    before = app.render_table(store)
    status, table, *uploads = app.submit_handler(
        store, worker, None, "Auto", words_file(["damn"]), "Classic beep", None
    )
    assert status == "❌ Please upload an audio file (.wav or .mp3)."
    assert isinstance(table, type(gr.skip()))
    assert app.render_table(store) == before


def test_failed_job_in_table_and_panel(
    store: JobStore,
    make_worker: Callable,
    failing_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    worker = make_worker(failing_transcriber())
    app.submit_handler(
        store, worker, make_tone("x.wav"), "Auto", words_file(["damn"]), "Classic beep", None
    )
    job_id = store.list()[0].id
    wait_for(lambda: store.get(job_id).status == JobStatus.FAILED)  # type: ignore[union-attr]

    row = app.render_table(store)[0]
    assert row[app.TABLE_HEADERS.index("Error")] == "transcription failed (boom)."
    assert row[app.TABLE_HEADERS.index("Masked")] == ""
    view = app.render_details(store, job_id)
    assert "transcription failed (boom)." in view.summary_md
    assert view.can_delete
    assert view.audio_path is None


def test_preset_previews(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = app.preset_preview

    def spy(name: str, **kwargs: Any) -> np.ndarray:  # noqa: ANN401
        calls.append(name)
        return real(name, **kwargs)

    monkeypatch.setattr(app, "preset_preview", spy)
    values = app.preview_values()
    assert calls == list(MASKS.values())
    assert len(values) == 3
    for rate, samples in values:
        assert rate == 44100
        assert samples.shape == (44100,)


def test_delete_handler(
    store: JobStore,
    make_worker: Callable,
    blocking_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    fake = blocking_transcriber(DAMN)
    worker = make_worker(fake)
    app.submit_handler(
        store, worker, make_tone("run.wav"), "Auto", words_file(["damn"]), "Classic beep", None
    )
    assert fake.started.wait(5)
    running = store.list()[0].id
    view = app.render_details(store, running)
    assert not view.can_delete
    assert "This job can be deleted once it finishes." in view.summary_md

    selected, _, table, summary, *_ = app.delete_handler(store, running)
    assert selected == running
    assert "This job can be deleted once it finishes." in summary
    assert store.get(running) is not None

    fake.release.set()
    wait_for(lambda: store.get(running).status == JobStatus.DONE)  # type: ignore[union-attr]
    selected, signature, table, summary, *_ = app.delete_handler(store, running)
    assert selected is None
    assert signature == (None, None)
    assert summary == "Select a job in the table to see its result."
    assert running not in [row[0] for row in table]
    assert store.get(running) is None


def test_done_job_with_missing_files(
    store: JobStore,
    make_worker: Callable,
    fake_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    worker = make_worker(fake_transcriber(DAMN))
    app.submit_handler(
        store, worker, make_tone("gone.wav"), "Auto", words_file(["damn"]), "Classic beep", None
    )
    job_id = store.list()[0].id
    wait_for(lambda: store.get(job_id).status == JobStatus.DONE)  # type: ignore[union-attr]
    (store.job_dir(job_id) / "gone_masked.wav").unlink()

    view = app.render_details(store, job_id)
    assert "The result files for this job are no longer available." in view.summary_md
    assert view.can_delete
    assert (view.audio_path, view.wav_path, view.json_path) == (None, None, None)


def test_tick_skips_panel_until_status_changes(
    store: JobStore,
    make_worker: Callable,
    blocking_transcriber: type,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    wait_for: Callable[..., None],
) -> None:
    fake = blocking_transcriber(DAMN)
    worker = make_worker(fake)
    app.submit_handler(
        store, worker, make_tone("t.wav"), "Auto", words_file(["damn"]), "Classic beep", None
    )
    assert fake.started.wait(5)
    job_id = store.list()[0].id
    signature = (job_id, "running")
    _, new_signature, *panel = app.tick_handler(store, job_id, signature)
    skip = type(gr.skip())
    assert isinstance(new_signature, skip)
    assert all(isinstance(value, skip) for value in panel)

    fake.release.set()
    wait_for(lambda: store.get(job_id).status == JobStatus.DONE)  # type: ignore[union-attr]
    _, new_signature, summary, *_ = app.tick_handler(store, job_id, signature)
    assert new_signature == (job_id, "done")
    assert "1 masked word" in summary


def test_notice_rendered_above_table(store: JobStore, make_worker: Callable) -> None:
    store.notice = "The saved jobs list could not be read and was reset."
    demo = app.build_app(store, make_worker(object()))
    markdowns = [
        block.value
        for block in demo.blocks.values()
        if isinstance(block, gr.Markdown) and isinstance(block.value, str)
    ]
    assert store.notice in markdowns
