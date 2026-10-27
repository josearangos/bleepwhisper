"""Gradio layout and event handlers (Gradio is imported only here and in theme.py)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import gradio as gr
import numpy as np

from bleeper.core import InvalidInputError, load_words, preset_preview
from bleeper.ui.jobs import Job, JobBusyError, JobStatus, JobStore
from bleeper.ui.submit import LANGUAGES, MASKS, create_job
from bleeper.ui.theme import WAVEFORM, color_status
from bleeper.ui.worker import JobWorker

TABLE_HEADERS = [
    "ID",
    "File",
    "Language",
    "Mask",
    "Status",
    "Progress",
    "Masked",
    "Created",
    "Finished",
    "Error",
]
EMPTY_HINT = "No jobs yet. Submit an audio file above."
NO_SELECTION = "Select a job in the table to see its result."
FILES_MISSING = "The result files for this job are no longer available."
RUNNING_NOTE = "This job can be deleted once it finishes."
PREVIEW_RATE = 44100
REFRESH_SECONDS = 2.0

Signature = tuple[str | None, str | None]


@dataclass(frozen=True)
class DetailsView:
    summary_md: str
    audio_path: str | None
    wav_path: str | None
    json_path: str | None
    can_delete: bool
    signature: Signature


def _clock(timestamp: str | None) -> str:
    if timestamp is None:
        return ""
    return datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _row(job: Job) -> list[str]:
    done = job.status == JobStatus.DONE
    return [
        job.id,
        job.filename,
        job.language,
        job.mask,
        job.status.value,
        f"{job.progress}%",
        str(job.masked_count) if done and job.masked_count is not None else "",
        _clock(job.created_at),
        _clock(job.finished_at),
        job.error or "",
    ]


def render_table(store: JobStore) -> list[list[str]]:
    rows = [_row(job) for job in store.list()]
    if not rows:
        rows = [["", EMPTY_HINT] + [""] * (len(TABLE_HEADERS) - 2)]
    return rows


def render_details(store: JobStore, job_id: str | None) -> DetailsView:
    job = store.get(job_id) if job_id else None
    if job is None:
        return DetailsView(NO_SELECTION, None, None, None, False, (None, None))
    signature = (job.id, job.status.value)
    title = f"**{job.filename}** · {job.status.value}"
    if job.status == JobStatus.DONE:
        wav = store.data_dir / (job.output_file or "")
        report = store.data_dir / (job.report_file or "")
        if not (job.output_file and job.report_file and wav.is_file() and report.is_file()):
            return DetailsView(f"{title}\n\n{FILES_MISSING}", None, None, None, True, signature)
        count = job.masked_count or 0
        summary = f"{title} · {count} masked word{'' if count == 1 else 's'}"
        wav_path, json_path = str(wav.resolve()), str(report.resolve())
        return DetailsView(summary, wav_path, wav_path, json_path, True, signature)
    if job.status == JobStatus.FAILED:
        return DetailsView(f"{title}\n\n{job.error or ''}", None, None, None, True, signature)
    summary = f"{title} · {job.progress}%"
    if job.status == JobStatus.RUNNING:
        return DetailsView(f"{summary}\n\n{RUNNING_NOTE}", None, None, None, False, signature)
    return DetailsView(summary, None, None, None, True, signature)


def _details_updates(view: DetailsView) -> tuple[Any, ...]:
    """Values for the panel outputs: summary, player, two downloads, delete button."""
    return (
        view.summary_md,
        gr.update(value=view.audio_path, visible=view.audio_path is not None),
        gr.update(value=view.wav_path, visible=view.wav_path is not None),
        gr.update(value=view.json_path, visible=view.json_path is not None),
        gr.update(interactive=view.can_delete, visible=view.signature[0] is not None),
    )


def preview_values() -> list[tuple[int, np.ndarray]]:
    return [
        (PREVIEW_RATE, preset_preview(code, sample_rate=PREVIEW_RATE)) for code in MASKS.values()
    ]


def submit_handler(
    store: JobStore,
    worker: JobWorker,
    audio: str | Path | None,
    language: str,
    words: str | Path | None,
    preset: str,
    custom_mask: str | Path | None,
) -> tuple[Any, ...]:
    """Validate and queue a job; returns status, table and the three upload fields."""
    try:
        job = create_job(store, audio, words, language, preset, custom_mask)
    except InvalidInputError as exc:
        return (f"❌ {exc}", gr.skip(), gr.skip(), gr.skip(), gr.skip())
    worker.submit(job.id)
    count = len(load_words(store.job_dir(job.id) / "words.txt"))
    for upload in (audio, words, custom_mask):
        if upload is not None:
            Path(upload).unlink(missing_ok=True)
    status = (
        f"✅ Job {job.id} queued: {job.filename} "
        f"({count} forbidden word{'' if count == 1 else 's'}, mask: {job.mask})."
    )
    return (status, render_table(store), None, None, None)


def on_select(store: JobStore, evt: gr.SelectData, current: str | None = None) -> str | None:
    """The clicked row's ID cell (never its position); the hint row keeps `current`."""
    row = evt.row_value or []
    job_id = str(row[0]) if row else ""
    return job_id if job_id and store.get(job_id) is not None else current


def select_handler(store: JobStore, current: str | None, evt: gr.SelectData) -> tuple[Any, ...]:
    job_id = on_select(store, evt, current)
    view = render_details(store, job_id)
    return (job_id, view.signature, *_details_updates(view))


def tick_handler(store: JobStore, job_id: str | None, signature: Signature) -> tuple[Any, ...]:
    """Refresh the table; re-render the panel only when the selected job's status changed."""
    view = render_details(store, job_id)
    if view.signature == tuple(signature or (None, None)):
        return (render_table(store), gr.skip(), *(gr.skip(),) * 5)
    return (render_table(store), view.signature, *_details_updates(view))


def delete_handler(store: JobStore, job_id: str | None) -> tuple[Any, ...]:
    """Delete the selected job; returns selection, signature, table and the panel outputs."""
    try:
        if job_id:
            store.delete(job_id)
    except JobBusyError as exc:
        view = dataclasses.replace(render_details(store, job_id), can_delete=False)
        view = dataclasses.replace(view, summary_md=f"{view.summary_md.split(chr(10))[0]}\n\n{exc}")
        return (job_id, view.signature, render_table(store), *_details_updates(view))
    view = render_details(store, None)
    return (None, view.signature, render_table(store), *_details_updates(view))


def build_app(store: JobStore, worker: JobWorker) -> gr.Blocks:
    with gr.Blocks(title="Bleeper", delete_cache=(600, 3600)) as demo:
        gr.Markdown("# Bleeper\nMask forbidden words in audio, locally and offline.")
        with gr.Row():
            with gr.Column():
                audio = gr.File(
                    label="Audio (.wav or .mp3, max 100 MB, 30 min)",
                    file_types=[".wav", ".mp3"],
                    type="filepath",
                )
                language = gr.Dropdown(list(LANGUAGES), value="Auto", label="Language")
                words = gr.File(label="Forbidden words", file_types=[".txt"], type="filepath")
            with gr.Column():
                preset = gr.Radio(list(MASKS), value="Classic beep", label="Mask")
                with gr.Row():
                    for label, value in zip(MASKS, preview_values(), strict=True):
                        gr.Audio(
                            value=value,
                            label=f"Preview: {label}",
                            interactive=False,
                            waveform_options=WAVEFORM,
                        )
                custom_mask = gr.File(
                    label="Custom mask (optional, overrides the preset)",
                    file_types=[".wav", ".mp3"],
                    type="filepath",
                )
        submit = gr.Button("Mask audio", variant="primary")
        status = gr.Markdown()

        gr.Markdown(store.notice or "", visible=bool(store.notice))
        table = gr.Dataframe(
            value=render_table(store),
            headers=TABLE_HEADERS,
            interactive=False,
            label="Jobs",
            wrap=True,
        )
        table.postprocess = color_status(table.postprocess, TABLE_HEADERS.index("Status"))
        table.value = table.postprocess(render_table(store)).model_dump()

        empty = render_details(store, None)
        selected = gr.State(None)
        signature = gr.State(empty.signature)
        with gr.Group():
            summary = gr.Markdown(empty.summary_md)
            player = gr.Audio(
                type="filepath",
                interactive=False,
                label="Masked audio",
                visible=False,
                waveform_options=WAVEFORM,
            )
            with gr.Row():
                wav_download = gr.DownloadButton("Download audio", visible=False)
                json_download = gr.DownloadButton("Download report", visible=False)
                delete = gr.Button("Delete job", variant="stop", visible=False)
        panel = [summary, player, wav_download, json_download, delete]

        submit.click(
            partial(submit_handler, store, worker),
            inputs=[audio, language, words, preset, custom_mask],
            outputs=[status, table, audio, words, custom_mask],
            concurrency_limit=None,
        )

        # A real function, not a partial: Gradio injects SelectData by reading type hints.
        def on_table_select(current: str | None, evt: gr.SelectData) -> tuple[Any, ...]:
            return select_handler(store, current, evt)

        table.select(
            on_table_select,
            inputs=[selected],
            outputs=[selected, signature, *panel],
            concurrency_limit=None,
        )
        delete.click(
            partial(delete_handler, store),
            inputs=[selected],
            outputs=[selected, signature, table, *panel],
            concurrency_limit=None,
        )
        gr.Timer(REFRESH_SECONDS).tick(
            partial(tick_handler, store),
            inputs=[selected, signature],
            outputs=[table, signature, *panel],
            concurrency_limit=None,
            show_progress="hidden",
        )
        demo.load(partial(render_table, store), outputs=[table], concurrency_limit=None)
    return demo
