"""Background worker: one thread running queued jobs through bleeper.core."""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

from bleeper.core import BleeperError, Transcriber, process_audio
from bleeper.core.transcribe import WhisperTranscriber
from bleeper.ui.jobs import Job, JobStore, remove_inputs
from bleeper.ui.submit import MODEL, PADDING_MS

CUSTOM_PREFIX = "custom: "
log = logging.getLogger("bleeper.ui")


class JobWorker:
    """Runs jobs one at a time, in submission order, with one shared transcriber."""

    def __init__(self, store: JobStore, transcriber: Transcriber | None = None) -> None:
        self.store = store
        self.transcriber = transcriber or WhisperTranscriber(MODEL)
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="bleeper-worker")
        self._thread.start()

    def submit(self, job_id: str) -> None:
        self._queue.put(job_id)

    def join(self, timeout: float | None = None) -> None:
        """Stop after the queued jobs and wait for the thread (used by tests)."""
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        while (job_id := self._queue.get()) is not None:
            job = self.store.get(job_id)
            if job is None:
                continue  # deleted while queued
            try:
                self._run(job)
            except Exception:  # noqa: BLE001 - one bad job must never stop the worker
                log.warning("job %s failed", job_id)

    def _run(self, job: Job) -> None:
        job_dir = self.store.job_dir(job.id)
        output = job_dir / f"{Path(job.filename).stem}_masked.wav"
        custom = job.mask.startswith(CUSTOM_PREFIX)
        self.store.start(job.id)
        try:
            result = process_audio(
                job_dir / f"input{Path(job.filename).suffix.lower()}",
                job_dir / "words.txt",
                output,
                mask_path=job_dir / f"mask{Path(job.mask).suffix.lower()}" if custom else None,
                preset=None if custom else job.mask,
                model=MODEL,
                language=job.language_code,
                padding_ms=PADDING_MS,
                progress=lambda _stage, f: self.store.set_progress(job.id, round(f * 100)),
                transcriber=self.transcriber,
            )
            self.store.finish(
                job.id,
                self._relative(result.output_path),
                self._relative(result.report_path),
                len(result.report),
            )
        except BleeperError as exc:
            self.store.fail(job.id, str(exc))
            log.warning("job %s failed", job.id)
        except Exception as exc:
            self.store.fail(job.id, f"processing failed unexpectedly ({exc}).")
            log.warning("job %s failed", job.id)
        finally:
            remove_inputs(job_dir)

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.store.data_dir).as_posix()
