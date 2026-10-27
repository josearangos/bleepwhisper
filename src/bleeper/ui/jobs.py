"""In-memory job model and store, mirrored to jobs.json."""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

INTERRUPTED = "Interrupted: the UI stopped before this job finished. Submit it again."
CORRUPT_NOTICE = (
    "The saved jobs list could not be read and was reset. "
    "The old file was kept as jobs.json.corrupt."
)
INPUT_PATTERNS = ("input.*", "words.txt", "mask.*")


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    id: str  # 12-character hex string from uuid4
    filename: str
    language: str
    language_code: str | None
    mask: str  # beep/tone/noise, or `custom: <file name>`
    status: JobStatus
    progress: int  # 0–100, never decreases
    created_at: str  # ISO 8601 local time with offset
    finished_at: str | None = None
    error: str | None = None
    masked_count: int | None = None
    output_file: str | None = None  # relative to the data dir
    report_file: str | None = None  # relative to the data dir

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: data[k] for k in fields} | {"status": JobStatus(data["status"])})


class JobBusyError(Exception):
    """The job is running and cannot be deleted yet."""


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def remove_inputs(job_dir: Path) -> None:
    """Delete the job's input copies, keeping its results."""
    for pattern in INPUT_PATTERNS:
        for path in job_dir.glob(pattern):
            path.unlink(missing_ok=True)


class JobStore:
    """Thread-safe jobs by id, mirrored to jobs.json on every status change.

    Methods targeting a deleted id are no-ops returning None.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self.notice: str | None = None

    @property
    def jobs_file(self) -> Path:
        return self.data_dir / "jobs.json"

    def load(self) -> None:
        """Read jobs.json, mark unfinished jobs as interrupted and remove leftover inputs."""
        jobs: list[Job] = []
        try:
            data = json.loads(self.jobs_file.read_text(encoding="utf-8"))
            jobs = [Job.from_dict(item) for item in data["jobs"]]
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            os.replace(self.jobs_file, self.jobs_file.with_name("jobs.json.corrupt"))
            jobs = []
            self.notice = CORRUPT_NOTICE
        with self._lock:
            # The file is newest first; insert oldest first so ties keep their order.
            self._jobs = {job.id: job for job in reversed(jobs)}
            for job in self._jobs.values():
                if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                    job.status, job.error, job.finished_at = JobStatus.FAILED, INTERRUPTED, now()
                remove_inputs(self.job_dir(job.id))
            self._save()

    def _save(self) -> None:
        """Write jobs.json atomically; the caller holds the lock."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "jobs": [job.to_dict() for job in self._newest_first()]}
        fd, name = tempfile.mkstemp(dir=self.data_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
            os.replace(name, self.jobs_file)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = dataclasses.replace(job)
            self._save()

    def delete(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if job.status == JobStatus.RUNNING:
                raise JobBusyError("This job can be deleted once it finishes.")
            del self._jobs[job_id]
            shutil.rmtree(self.job_dir(job_id), ignore_errors=True)
            self._save()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dataclasses.replace(job) if job else None

    def list(self) -> list[Job]:
        with self._lock:
            return [dataclasses.replace(job) for job in self._newest_first()]

    def _newest_first(self) -> list[Job]:
        # Later insertion breaks ties between jobs created in the same second.
        jobs = list(reversed(self._jobs.values()))
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def job_dir(self, job_id: str) -> Path:
        return self.data_dir / "jobs" / job_id

    def start(self, job_id: str) -> None:
        self._update(job_id, status=JobStatus.RUNNING)

    def set_progress(self, job_id: str, percent: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.progress = max(job.progress, min(100, percent))

    def finish(self, job_id: str, output_file: str, report_file: str, masked_count: int) -> None:
        self._update(
            job_id,
            status=JobStatus.DONE,
            progress=100,
            finished_at=now(),
            output_file=output_file,
            report_file=report_file,
            masked_count=masked_count,
        )

    def fail(self, job_id: str, message: str) -> None:
        self._update(job_id, status=JobStatus.FAILED, finished_at=now(), error=message)

    def _update(self, job_id: str, **changes: Any) -> None:  # noqa: ANN401
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for name, value in changes.items():
                setattr(job, name, value)
            self._save()
