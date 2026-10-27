import json
import re
from pathlib import Path

import pytest

from bleeper.ui.jobs import Job, JobBusyError, JobStatus, JobStore

INTERRUPTED = "Interrupted: the UI stopped before this job finished. Submit it again."
SCHEMA = Path(__file__).parents[2] / "specs/002-gradio-web-ui/contracts/jobs-store-schema.json"


def make_job(job_id: str, status: JobStatus, second: int = 0) -> Job:
    return Job(
        id=job_id,
        filename=f"{job_id}.wav",
        language="Spanish",
        language_code="es",
        mask="beep",
        status=status,
        progress=0,
        created_at=f"2026-10-26T10:00:{second:02d}-05:00",
    )


@pytest.fixture
def filled(store: JobStore) -> JobStore:
    """One job per status: queued (oldest) → running → done → failed (newest)."""
    for second, (job_id, status) in enumerate(
        [
            ("aaaaaaaaaaaa", JobStatus.QUEUED),
            ("bbbbbbbbbbbb", JobStatus.QUEUED),
            ("cccccccccccc", JobStatus.QUEUED),
            ("dddddddddddd", JobStatus.QUEUED),
        ]
    ):
        store.job_dir(job_id).mkdir(parents=True)
        store.add(make_job(job_id, status, second))
    store.start("bbbbbbbbbbbb")
    store.start("cccccccccccc")
    store.finish("cccccccccccc", "jobs/cccccccccccc/c_masked.wav", "jobs/cccccccccccc/c.json", 2)
    store.start("dddddddddddd")
    store.fail("dddddddddddd", "transcription failed (boom).")
    return store


def test_persist_round_trip(filled: JobStore) -> None:
    reloaded = JobStore(filled.data_dir)
    reloaded.load()
    assert [job.id for job in reloaded.list()] == [job.id for job in filled.list()]
    for job_id in ("cccccccccccc", "dddddddddddd"):
        assert reloaded.get(job_id) == filled.get(job_id)


def test_jobs_json_matches_schema(filled: JobStore) -> None:
    schema = json.loads(SCHEMA.read_text())["properties"]["jobs"]["items"]
    data = json.loads((filled.data_dir / "jobs.json").read_text())
    assert data["version"] == 1
    assert [job["id"] for job in data["jobs"]] == [job.id for job in filled.list()]
    for job in data["jobs"]:
        assert set(job) == set(schema["required"])
        assert re.fullmatch(schema["properties"]["id"]["pattern"], job["id"])
        assert job["status"] in schema["properties"]["status"]["enum"]
        assert re.fullmatch(schema["properties"]["mask"]["pattern"], job["mask"])


def test_recovery_marks_interrupted(filled: JobStore) -> None:
    for job_id in ("aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc"):
        job_dir = filled.job_dir(job_id)
        for name in ("input.mp3", "words.txt", "mask.wav"):
            (job_dir / name).write_text("x")
    result = filled.job_dir("cccccccccccc") / "c_masked.wav"
    result.write_text("result")

    reloaded = JobStore(filled.data_dir)
    reloaded.load()
    for job_id in ("aaaaaaaaaaaa", "bbbbbbbbbbbb"):
        job = reloaded.get(job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.error == INTERRUPTED
        assert job.finished_at is not None
    assert reloaded.get("cccccccccccc").status == JobStatus.DONE  # type: ignore[union-attr]
    for job_id in ("aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc"):
        assert not any(reloaded.job_dir(job_id).glob("input.*"))
        assert not (reloaded.job_dir(job_id) / "words.txt").exists()
        assert not any(reloaded.job_dir(job_id).glob("mask.*"))
    assert result.read_text() == "result"
    saved = json.loads((filled.data_dir / "jobs.json").read_text())
    assert {job["status"] for job in saved["jobs"]} == {"done", "failed"}


def test_missing_file_starts_empty(store: JobStore) -> None:
    store.load()
    assert store.list() == []
    assert store.notice is None


def test_corrupt_file(store: JobStore) -> None:
    store.data_dir.mkdir(parents=True)
    (store.data_dir / "jobs.json").write_text("{not json")
    (store.data_dir / "jobs.json.corrupt").write_text("older")
    store.load()
    assert store.list() == []
    assert (store.data_dir / "jobs.json.corrupt").read_text() == "{not json"
    assert store.notice == (
        "The saved jobs list could not be read and was reset. "
        "The old file was kept as jobs.json.corrupt."
    )


def test_atomic_write(filled: JobStore) -> None:
    assert not list(filled.data_dir.glob("*.tmp"))


def test_progress_not_persisted(filled: JobStore) -> None:
    jobs_json = filled.data_dir / "jobs.json"
    before = jobs_json.stat().st_mtime_ns
    filled.set_progress("bbbbbbbbbbbb", 40)
    assert filled.get("bbbbbbbbbbbb").progress == 40  # type: ignore[union-attr]
    assert jobs_json.stat().st_mtime_ns == before


def test_progress_never_decreases(filled: JobStore) -> None:
    filled.set_progress("bbbbbbbbbbbb", 60)
    filled.set_progress("bbbbbbbbbbbb", 30)
    filled.set_progress("bbbbbbbbbbbb", 250)
    assert filled.get("bbbbbbbbbbbb").progress == 100  # type: ignore[union-attr]


def test_deleted_id_is_a_no_op(filled: JobStore) -> None:
    filled.delete("aaaaaaaaaaaa")
    filled.start("aaaaaaaaaaaa")
    filled.set_progress("aaaaaaaaaaaa", 50)
    filled.fail("aaaaaaaaaaaa", "late")
    assert filled.get("aaaaaaaaaaaa") is None


def test_delete_done_and_failed(filled: JobStore) -> None:
    for job_id in ("cccccccccccc", "dddddddddddd", "aaaaaaaaaaaa"):
        filled.delete(job_id)
        assert filled.get(job_id) is None
        assert not filled.job_dir(job_id).exists()
    saved = json.loads((filled.data_dir / "jobs.json").read_text())
    assert [job["id"] for job in saved["jobs"]] == ["bbbbbbbbbbbb"]
    filled.delete("unknown00000")


def test_delete_running_refused(filled: JobStore) -> None:
    with pytest.raises(JobBusyError, match="This job can be deleted once it finishes."):
        filled.delete("bbbbbbbbbbbb")
    assert filled.get("bbbbbbbbbbbb") is not None
    assert filled.job_dir("bbbbbbbbbbbb").is_dir()
