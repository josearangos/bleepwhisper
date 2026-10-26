# Data Model: Bleeper Web UI

The UI adds jobs, a store and a worker around the unchanged core types (`ProcessResult`,
`ReportEntry`, `InvalidInputError`, `ProcessingError`; see
[../001-cli-word-masking/data-model.md](../001-cli-word-masking/data-model.md)).

## JobStatus

`queued` → `running` → `done` | `failed`

| From | To | Trigger |
|------|----|---------|
| (new) | `queued` | Submit passes validation; job files copied; id put on the queue |
| `queued` | `running` | Worker takes the id off the queue |
| `running` | `done` | `process_audio` returns |
| `running` | `failed` | `process_audio` raises `BleeperError` (its message) or any other exception (generic message) |
| `queued` / `running` | `failed` | Start-up recovery: "Interrupted: the UI stopped before this job finished. Submit it again." |
| `queued` / `done` / `failed` | (deleted) | User deletes the job; a queued id is skipped by the worker |
| `running` | (deleted) | **Not allowed**: `JobStore.delete` raises `JobBusyError` |

`done` and `failed` are final; there is no retry or cancel.

## Job

| Field | Type | Rules |
|-------|------|-------|
| `id` | `str` | 12-character hex string from `uuid4`, unique, used as the directory name |
| `filename` | `str` | Original basename of the uploaded audio (shown in the table) |
| `language` | `str` | Display label (`Auto`, `Spanish`, …); the code is derived via the mapping |
| `language_code` | `str \| None` | `None` for Auto, otherwise `es`/`en`/`pt`/`fr`/`de`/`it` |
| `mask` | `str` | `beep`/`tone`/`noise`, or `custom: <file name>` |
| `status` | `JobStatus` | See the transitions above |
| `progress` | `int` | 0–100, never decreases; `round(fraction * 100)` from the core callback; 100 when `done` |
| `created_at` | `str` | ISO 8601 local time with offset, set at submit |
| `finished_at` | `str \| None` | Set on `done`/`failed` |
| `error` | `str \| None` | Readable message for `failed` jobs only |
| `masked_count` | `int \| None` | `len(result.report)` for `done` jobs |
| `output_file` | `str \| None` | Path of the masked WAV relative to the data dir, for `done` jobs |
| `report_file` | `str \| None` | Path of the JSON report relative to the data dir, for `done` jobs |

Input file locations aren't stored: they are always `jobs/<id>/input<ext>`, `jobs/<id>/words.txt`
and optionally `jobs/<id>/mask<ext>`, and they are deleted when the job finishes.

## Submission (transient, not persisted)

The form values, validated before a job exists.

| Field | Rule (violation → `InvalidInputError`, no job created) |
|-------|-------------------------------------------------------|
| `audio` | Required; `.wav`/`.mp3`; size ≤ 100 MB; `probe_audio` succeeds; 0 < duration ≤ 1800 s |
| `words` | Required; `load_words` succeeds (UTF-8, at least one usable entry) |
| `language` | One of the 7 labels |
| `preset` | One of the 3 labels; ignored when `custom_mask` is set |
| `custom_mask` | Optional; `.wav`/`.mp3`; `probe_audio` succeeds |

The checks run in that order and the first failure is reported. Messages say what is wrong and how
to fix it (see [contracts/ui.md](contracts/ui.md)).

## JobStore

- Holds `dict[id, Job]` guarded by a `threading.Lock`, plus the data directory path.
- `create(submission) -> Job`, `get(id)`, `list() -> list[Job]` (newest first),
  `start(id)`, `set_progress(id, percent)` (in memory only, max with the current value),
  `finish(id, result)`, `fail(id, message)`, `delete(id)`.
- Writes `jobs.json` atomically after create, start, finish, fail and delete.
- `load()` at start-up: reads `jobs.json`, applies recovery (above), deletes leftover input copies,
  and handles a missing (→ empty) or corrupt (→ renamed, empty, `notice` set) file.

## jobs.json

See [contracts/jobs-store-schema.json](contracts/jobs-store-schema.json):
`{"version": 1, "jobs": [<Job>, ...]}`, newest first.

## JobWorker

- Owns a `queue.Queue[str]`, a single daemon thread, the `JobStore` and one `Transcriber`
  (default `WhisperTranscriber("small")`, injectable for tests).
- `submit(job_id)` puts the id on the queue. The loop: `get` → skip if deleted → `start` →
  `process_audio(...)` → `finish`/`fail` → delete the input copies (`finally`) → next.
- An exception in one job never ends the loop (FR-015).

## Data directory layout

```text
~/.bleeper/ui/                 # or --data-dir / BLEEPER_UI_DATA
├── jobs.json
└── jobs/
    └── 3f9c2a1b7d4e/
        ├── input.mp3            # deleted when the job finishes
        ├── words.txt            # deleted when the job finishes
        ├── mask.wav             # optional; deleted when the job finishes
        ├── interview_masked.wav # result (done jobs)
        └── interview_masked.json
```
