---

description: "Task list for Bleeper Web UI — Background Masking Jobs in the Browser"
---

# Tasks: Bleeper Web UI — Background Masking Jobs in the Browser

**Input**: Design documents from `/specs/002-gradio-web-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (ui.md,
core-additions.md, jobs-store-schema.json), quickstart.md

**Tests**: INCLUDED. The constitution (Principle V) requires pytest for every module, and the spec's
acceptance criteria must be proven by tests. Within each story, write tests first and confirm they
fail before implementing. No test may need the network or a real Whisper model.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Paths are relative to the repository root (single project, `src/` layout)

**Ground rules for every task**: no audio logic in `src/bleeper/ui/` (decode, inspect, generate or
mask audio only through `bleeper.core` public names); only `src/bleeper/ui/app.py` imports Gradio at
module level (`__main__.py` imports it lazily inside `main()`); full type hints; `ruff format` and
`ruff check` clean.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, entry points and package skeleton

- [ ] T001 Update `pyproject.toml`: change `"soundfile"` to `"soundfile>=0.12.1"`; add `[project.optional-dependencies] ui = ["gradio>=6,<7"]`; add `"gradio>=6,<7"` to the `dev` extra; add console script `bleeper-ui = "bleeper.ui.__main__:main"` under `[project.scripts]` (keep `bleeper = "bleeper.cli:main"`)
- [ ] T002 Create the package skeleton: `src/bleeper/ui/__init__.py` containing only the docstring `"""Local Gradio web UI for Bleeper (thin layer over bleeper.core)."""`, and empty placeholder modules `src/bleeper/ui/jobs.py`, `src/bleeper/ui/submit.py`, `src/bleeper/ui/worker.py`, `src/bleeper/ui/app.py`, `src/bleeper/ui/__main__.py`, each with a one-line module docstring
- [ ] T003 Reinstall and verify tooling: `uv pip install -e ".[dev,ui]"`, then `python -c "import gradio; print(gradio.__version__)"` prints 6.x, and `ruff check .` plus `pytest` still pass on the existing suite

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core additions, shared job types, option mappings and test fixtures used by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first)

- [ ] T004 [P] Write `tests/unit/test_probe_audio.py`: `probe_audio` on a 2.5 s 16 kHz stereo WAV from `make_tone` returns `AudioInfo(duration≈2.5, sample_rate=16000, channels=2)`; on an MP3 created with ffmpeg from a 3 s WAV returns duration ≈ 3.0 (skip with `pytest.mark.skipif(shutil.which("ffmpeg") is None, ...)`); a `.ogg`/`.txt` path raises `InvalidInputError` mentioning ".wav or .mp3"; a `.wav` with random bytes raises `InvalidInputError` containing "not a valid audio file"; a missing path raises `InvalidInputError` containing "not found"
- [ ] T005 [P] Write `tests/unit/test_preset_preview.py`: for each of `beep`, `tone`, `noise`, `preset_preview(name)` returns a 1-D float64 array of exactly `44100` samples; `preset_preview(name, seconds=0.5, sample_rate=16000)` has 8000 samples; peak `abs` ≤ 0.5 + 1e-9; first and last samples are 0.0 (fade); `preset_preview("nope")` raises `InvalidInputError`

### Implementation

- [ ] T006 [P] In `src/bleeper/core/audio_io.py` add `@dataclass(frozen=True) class AudioInfo: duration: float; sample_rate: int; channels: int` and `def probe_audio(path: str | Path) -> AudioInfo` per contracts/core-additions.md: reuse the same "not found" and "unsupported audio format … Use a .wav or .mp3 file." checks as `load_audio` (extract them into a private `_check_audio_path(path: Path) -> None` used by both, keeping `load_audio`'s messages byte-identical), then `sf.info(str(path))`; on `sf.LibsndfileError`/`RuntimeError` raise `InvalidInputError(f"cannot read '{path.name}': not a valid audio file. Check that the file is not corrupt.")`; header read only, never a full decode
- [ ] T007 [P] In `src/bleeper/core/presets.py` add `def preset_preview(name: str, seconds: float = 1.0, sample_rate: int = 44100) -> np.ndarray`: `n = round(seconds * sample_rate)`; `samples = generate_preset(name, n, sample_rate)`; scale to peak 0.5 (`0.5 * samples / max(abs(samples).max(), 1e-12)`); return `bleeper.core.masking.fade(samples, sample_rate)`; pure, no I/O
- [ ] T008 Re-export `AudioInfo`, `probe_audio`, `preset_preview` and `load_words` (from `bleeper.core.words`) in `src/bleeper/core/__init__.py`, adding them to `__all__` in sorted order (depends on T006, T007)
- [ ] T009 [P] Implement option mappings in `src/bleeper/ui/submit.py`: `LANGUAGES: dict[str, str | None] = {"Auto": None, "Spanish": "es", "English": "en", "Portuguese": "pt", "French": "fr", "German": "de", "Italian": "it"}` (insertion order = dropdown order, `"Auto"` default); `MASKS: dict[str, str] = {"Classic beep": "beep", "Low tone": "tone", "Noise burst": "noise"}` (default `"Classic beep"`); constants `MAX_BYTES = 100 * 1024 * 1024`, `MAX_SECONDS = 1800.0`, `MODEL = "small"`, `PADDING_MS = 80`
- [ ] T010 [P] Implement the in-memory job model in `src/bleeper/ui/jobs.py` per data-model.md: `class JobStatus(str, Enum)` with `QUEUED="queued"`, `RUNNING="running"`, `DONE="done"`, `FAILED="failed"`; `@dataclass class Job` with fields `id: str` ("12-character hex string from uuid4"), `filename: str`, `language: str`, `language_code: str | None`, `mask: str` ("`beep`/`tone`/`noise`, or `custom: <file name>`"), `status: JobStatus`, `progress: int` ("0–100, never decreases"), `created_at: str` (ISO 8601 local time with offset), `finished_at: str | None = None`, `error: str | None = None`, `masked_count: int | None = None`, `output_file: str | None = None`, `report_file: str | None = None` (both "relative to the data dir"), plus `to_dict()`/`from_dict()`; `class JobBusyError(Exception)`; `class JobStore(data_dir: Path)` holding `dict[str, Job]` under a `threading.Lock` with methods `add(job)`, `get(id) -> Job | None` (returns a copy), `list() -> list[Job]` (copies, newest first by `created_at`), `job_dir(id) -> Path` (`data_dir / "jobs" / id`), `start(id)` (→ running), `set_progress(id, percent)` (stores `max(current, min(100, percent))`), `finish(id, output_file, report_file, masked_count)` (→ done, progress 100, `finished_at` now), `fail(id, message)` (→ failed, `finished_at` now); every method that targets a deleted id is a no-op returning `None`. Persistence and `delete` are added in US5
- [ ] T011 Extend `tests/conftest.py` (keep existing fixtures unchanged): `BlockingTranscriber(FakeTranscriber)` whose `transcribe` sets `self.started: threading.Event` then waits on `self.release: threading.Event` (timeout 10 s) before returning; `FailingTranscriber` whose `transcribe` raises `ProcessingError("transcription failed (boom).")`; a `store(tmp_path)` fixture returning `JobStore(tmp_path / "data")`; a `wait_for(predicate, timeout=5.0)` helper polling every 10 ms and failing the test on timeout

**Checkpoint**: Core additions tested; shared job types and fixtures ready

---

## Phase 3: User Story 1 - Submit a masking job and download the result (Priority: P1) 🎯 MVP

**Goal**: Launch the UI, submit audio + language + words file + preset, see the job progress in the table, select it and play/download the masked WAV and JSON report, identical to the CLI.

**Independent Test**: Submit one synthetic WAV with a fake transcriber that reports a forbidden word; the job ends `done` with `masked_count == 1`; the details panel lists a playable WAV and both downloads; the WAV and JSON bytes equal those produced by `bleeper.cli.main()` for the same inputs.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [ ] T012 [P] [US1] Write `tests/unit/test_ui_submit.py::test_create_job_happy_path`: `create_job(store, audio=<wav>, words=<txt>, language="Spanish", preset="Classic beep", custom_mask=None)` returns a `Job` with `status == "queued"`, `progress == 0`, `filename == "<wav basename>"`, `language_code == "es"`, `mask == "beep"`, a 12-hex-char `id`, and copies `jobs/<id>/input.wav` and `jobs/<id>/words.txt` into the store's data dir; the original upload files are untouched
- [ ] T013 [P] [US1] Write `tests/unit/test_ui_worker.py::test_job_runs_to_done`: with `JobWorker(store, transcriber=FakeTranscriber([TranscribedWord("damn", 2.0, 2.5)]))`, a submitted job ends `done` (use `wait_for`), `progress == 100`, `masked_count == 1`, `finished_at` set, `output_file == "jobs/<id>/<stem>_masked.wav"`, `report_file == "jobs/<id>/<stem>_masked.json"`, both files exist, and `input.wav`/`words.txt` no longer exist; progress values observed via polling never decrease
- [ ] T014 [P] [US1] Write `tests/integration/test_ui_parity.py`: monkeypatch `bleeper.core.pipeline.WhisperTranscriber` to return a `FakeTranscriber` with fixed words; run `bleeper.cli.main([in, "--words", w, "--preset", "beep", "--lang", "es", "-o", cli_out])`; run the same inputs through `create_job` + `JobWorker` with the same `FakeTranscriber`; assert the WAV bytes and the JSON bytes are identical (`read_bytes()`), and that the fake recorded `language == "es"` in both runs. Also add a no-match case where the UI output equals the decoded input samples
- [ ] T015 [P] [US1] Write `tests/integration/test_ui_app.py::test_build_app_and_happy_flow`: `build_app(store, worker)` returns a `gr.Blocks` without launching; calling the submit handler with valid files returns a status string starting with `"✅ Job "` and the table rows include the new job; after the worker finishes, `render_table(store)` shows status `done`, progress `100%` and masked count `1`; `render_details(store, job_id)` for the done job returns the absolute WAV path for the player and both download paths

### Implementation for User Story 1

- [ ] T016 [US1] Implement `create_job(store: JobStore, audio: str | Path | None, words: str | Path | None, language: str, preset: str, custom_mask: str | Path | None) -> Job` in `src/bleeper/ui/submit.py` (happy path for now; full validation comes in US3): new `id = uuid.uuid4().hex[:12]`; copy audio to `store.job_dir(id) / f"input{suffix.lower()}"` and words to `words.txt` with `shutil.copyfile`; `mask = MASKS[preset]`; `created_at = datetime.now().astimezone().isoformat(timespec="seconds")`; `store.add(Job(...status=QUEUED, progress=0))`; return the job. If copying fails, remove the job dir and re-raise
- [ ] T017 [US1] Implement `JobWorker(store: JobStore, transcriber: Transcriber | None = None)` in `src/bleeper/ui/worker.py`: `self.transcriber = transcriber or WhisperTranscriber(MODEL)` (one instance for the worker's lifetime); `queue.Queue[str]`; `start()` launches one `threading.Thread(daemon=True, name="bleeper-worker")`; `submit(job_id)` puts the id on the queue. Loop: `get` → skip if `store.get(id)` is `None` → `store.start(id)` → `process_audio(job_dir/input<ext>, job_dir/"words.txt", job_dir/f"{Path(job.filename).stem}_masked.wav", preset=job.mask or mask_path=…, model=MODEL, language=job.language_code, padding_ms=PADDING_MS, progress=lambda _s, f: store.set_progress(id, round(f * 100)), transcriber=self.transcriber)`, leaving `report_path` at its default (research R6) → `store.finish(id, relative output, relative report, len(result.report))`; finally delete `input.*`, `words.txt` and `mask.*` in the job dir (`missing_ok=True`). Exceptions are handled in US3; for now let `BleeperError` call `store.fail(id, str(exc))`
- [ ] T018 [US1] Implement `render_table(store: JobStore) -> list[list[str]]` and `TABLE_HEADERS = ["ID", "File", "Language", "Mask", "Status", "Progress", "Masked", "Created", "Finished", "Error"]` in `src/bleeper/ui/app.py` per contracts/ui.md: progress as `f"{p}%"`, masked count only for `done`, times formatted `YYYY-MM-DD HH:MM:SS`, empty strings for missing values; an empty store renders one row with the hint "No jobs yet. Submit an audio file above." in the File column
- [ ] T019 [US1] Implement `render_details(store: JobStore, job_id: str | None) -> DetailsView` in `src/bleeper/ui/app.py` (`DetailsView` is a small frozen dataclass: `summary_md: str`, `audio_path: str | None`, `wav_path: str | None`, `json_path: str | None`, `can_delete: bool`, `signature: tuple[str | None, str | None]` = `(id, status)`): no selection → "Select a job in the table to see its result."; `done` → absolute paths under the data dir plus "N masked words" in the summary; `queued`/`running` → status and progress summary
- [ ] T020 [US1] Implement `build_app(store: JobStore, worker: JobWorker) -> gr.Blocks` in `src/bleeper/ui/app.py`: theme with system fonts only (`gr.themes.Default(font=["ui-sans-serif", "system-ui", "sans-serif"], font_mono=["ui-monospace", "monospace"])`); `delete_cache=(3600, 3600)`; form with `gr.File(label="Audio", file_types=[".wav", ".mp3"])`, `gr.Dropdown(list(LANGUAGES), value="Auto", label="Language")`, `gr.File(label="Forbidden words", file_types=[".txt"])`, `gr.Radio(list(MASKS), value="Classic beep", label="Mask")`, `gr.Button("Mask audio", variant="primary")` and a status `gr.Markdown`; `gr.Dataframe(headers=TABLE_HEADERS, interactive=False)`; details panel: `gr.Markdown`, `gr.Audio(type="filepath", interactive=False)`, `gr.DownloadButton("Download audio")`, `gr.DownloadButton("Download report")`; `gr.State` for the selected id and the last rendered signature. Events: submit → `create_job` + `worker.submit` → status `"✅ Job <id> queued: <filename> (<N> forbidden words, mask: <mask>)."` (N = `len(load_words(words))`) and a refreshed table; `Dataframe.select` → selected id from `evt.index[0]` row's ID column → render details; `gr.Timer(2.0).tick` → table always, details panel outputs only when the signature changed, otherwise `gr.skip()`; `demo.load` → render the table. Handlers never block on processing
- [ ] T021 [US1] Implement `main(argv: list[str] | None = None) -> int` in `src/bleeper/ui/__main__.py` per contracts/ui.md: argparse `--port` (int, default 7860), `--data-dir` (default `os.environ.get("BLEEPER_UI_DATA", "~/.bleeper/ui")`, `expanduser`, created with `mkdir(parents=True, exist_ok=True)`); set `os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")` before importing Gradio; on `ImportError` print `error: the web UI needs Gradio. Install it with: pip install "bleeper[ui]"` to stderr and return 1; build store + worker (`worker.start()`) + app; print `Bleeper UI running at http://127.0.0.1:<port>`; `demo.launch(server_name="127.0.0.1", server_port=port, share=False, max_file_size="110mb", show_api=False)`; on `OSError` for a busy port print an error asking for a different `--port` and return 1; end with `if __name__ == "__main__": raise SystemExit(main())`

**Checkpoint**: One job end to end in the browser, output identical to the CLI (MVP)

---

## Phase 4: User Story 2 - Queue several jobs while the UI stays responsive (Priority: P1)

**Goal**: Jobs submitted back to back run one at a time in FIFO order; the form and the table stay usable while a job runs; the model is loaded once.

**Independent Test**: With `BlockingTranscriber`, submit A then B: A is `running` and B `queued`; a third submit returns in < 1 s; after release, A finishes before B starts; both end `done`; one transcriber instance served every job.

### Tests for User Story 2 ⚠️ (write first, ensure they fail)

- [ ] T022 [P] [US2] Add to `tests/unit/test_ui_worker.py`: `test_second_job_queued_while_first_runs` (submit A and B with `BlockingTranscriber`; after `started` is set, `store.get(A).status == "running"` and `store.get(B).status == "queued"` with progress 0; release; both end `done`); `test_fifo_order` (record the order of `transcriber.calls` for jobs A, B, C and assert it matches submission order, and that B's `created_at` ≤ its start time and A's `finished_at` ≤ B's start); `test_single_transcriber_instance` (three jobs → the same fake object has 3 calls, and the worker never constructs another transcriber: monkeypatch `bleeper.ui.worker.WhisperTranscriber` to raise if called when one was injected)
- [ ] T023 [P] [US2] Add to `tests/integration/test_ui_app.py::test_submit_is_non_blocking`: with a job blocked in `BlockingTranscriber`, calling the submit handler for a second job returns within 1.0 s (`time.perf_counter`) and the table shows the second job as `queued`

### Implementation for User Story 2

- [ ] T024 [US2] Make the worker loop in `src/bleeper/ui/worker.py` robust for queues: wrap each job in `try/except Exception` so the thread never dies (log only `job <id> failed` at WARNING via `logging.getLogger("bleeper.ui")`, never audio or transcript content); add `join(timeout: float | None = None)` for tests (puts a sentinel `None` on the queue and joins the thread); confirm `WhisperTranscriber` is only constructed when no transcriber is injected
- [ ] T025 [US2] In `src/bleeper/ui/app.py`, make the submit handler and the timer tick handler take the store's lock only through `JobStore` methods (no long work inside handlers), and render the status column so `queued` jobs show `0%`; set `concurrency_limit=None` on the submit, select, delete and tick events so a slow event never queues behind another

**Checkpoint**: Multiple jobs queue and run in order while the UI stays responsive

---

## Phase 5: User Story 3 - Clear validation and error reporting (Priority: P2)

**Goal**: Invalid inputs are rejected on submit with the contract messages and no job; processing failures turn the job `failed` with a readable message.

**Independent Test**: Every row of the "Submit result" table in contracts/ui.md produces its message and leaves `store.list()` unchanged; a job whose transcriber raises ends `failed` with that message and the next job still runs.

### Tests for User Story 3 ⚠️ (write first, ensure they fail)

- [ ] T026 [P] [US3] Add to `tests/unit/test_ui_submit.py` one test per validation rule, each asserting `InvalidInputError` with the exact message from contracts/ui.md and `store.list() == []` and no `jobs/` subdirectory created: no audio (`"Please upload an audio file (.wav or .mp3)."`); `.ogg` audio (`"Unsupported audio format '.ogg'. Use a .wav or .mp3 file."`); size over the limit (monkeypatch `bleeper.ui.submit.MAX_BYTES` to 1000 and assert the message contains `"the limit is 100 MB"` and the actual size; also a file exactly at the limit is accepted); unreadable WAV (core `probe_audio` message); zero-length WAV (`"contains no audio"`); duration over the limit (monkeypatch `MAX_SECONDS` to 1.0 with a 2 s tone; message contains `"0:02 long; the limit is 30:00"`, formatted against the real 30:00 limit text); no words file (`"Please upload a forbidden words file (.txt, one word or phrase per line)."`); words file with only blank lines and `# comments` (core message containing `"no forbidden words found"`); non-UTF-8 words file (core message containing `"must be UTF-8"`); unreadable custom mask (message starting `"Custom mask: "`)
- [ ] T027 [P] [US3] Add to `tests/unit/test_ui_worker.py`: `test_failed_job_does_not_stop_worker` (job A with `FailingTranscriber` → `failed`, `error == "transcription failed (boom)."`, `finished_at` set, input copies removed; job B with a `FakeTranscriber` submitted afterwards → `done`; use a transcriber wrapper that fails only on the first call); `test_unexpected_exception_message` (a transcriber raising `RuntimeError("x")` → `failed` with the `ProcessingError` message from the core, `"processing failed unexpectedly (x)."`)
- [ ] T028 [P] [US3] Add to `tests/integration/test_ui_app.py`: the submit handler with no audio returns a status starting with `"❌ "`, and the table is unchanged; `render_table` shows the error text in the Error column for a failed job; `render_details` for a failed job shows the error in `summary_md` with `can_delete == True` (delete itself is US5)

### Implementation for User Story 3

- [ ] T029 [US3] Add `validate_submission(audio, words, custom_mask) -> int` to `src/bleeper/ui/submit.py`, called first by `create_job` before any directory is created, enforcing in order: audio present; suffix in `{".wav", ".mp3"}`; `stat().st_size <= MAX_BYTES` (message `f"'{name}' is {size / 1024**2:.1f} MB; the limit is 100 MB. Trim or compress the file and try again."`); `probe_audio(audio)` (propagate its `InvalidInputError`); `duration > 0` (`f"'{name}' contains no audio. Check the file."`); `duration <= MAX_SECONDS` (`f"'{name}' is {m}:{s:02d} long; the limit is 30:00. Split the file and try again."`); words present; `len(load_words(words))` (re-raise core errors with the temp path replaced by the uploaded file's basename); custom mask, if given, `probe_audio` with errors re-raised as `InvalidInputError("Custom mask: " + message)`. Return the entry count for the confirmation message
- [ ] T030 [US3] In `src/bleeper/ui/worker.py`, set failure messages: `BleeperError` → `str(exc)`; any other `Exception` → `"processing failed unexpectedly (<exc>)."`, matching the core's wording; keep the `finally` cleanup of input copies on every path
- [ ] T031 [US3] In `src/bleeper/ui/app.py`, catch `InvalidInputError` in the submit handler and return `f"❌ {exc}"` with an unchanged table (no `worker.submit`); show failed jobs' `error` in the table's Error column and in the details summary

**Checkpoint**: All invalid inputs are rejected clearly; failures are visible and isolated

---

## Phase 6: User Story 4 - Choose and preview the mask sound (Priority: P2)

**Goal**: Each preset has a ~1 s preview player; an uploaded custom mask overrides the preset and is recorded as `custom: <file name>`.

**Independent Test**: The app shows three preview players fed by `preset_preview`; a job with a custom mask records `mask == "custom: quack.wav"` and its output equals the CLI run with `--mask quack.wav`.

### Tests for User Story 4 ⚠️ (write first, ensure they fail)

- [ ] T032 [P] [US4] Add to `tests/unit/test_ui_submit.py::test_custom_mask_overrides_preset`: `create_job(..., preset="Low tone", custom_mask=<quack.wav>)` → `job.mask == "custom: quack.wav"` and `jobs/<id>/mask.wav` exists; without a custom mask `job.mask == "tone"`
- [ ] T033 [P] [US4] Add to `tests/integration/test_ui_parity.py::test_custom_mask_parity`: CLI with `--mask quack.wav` and the UI with the same custom mask produce identical WAV and JSON bytes; after the job, `mask.wav` is removed from the job dir
- [ ] T034 [P] [US4] Add to `tests/integration/test_ui_app.py::test_preset_previews`: `preview_values()` returns three `(44100, ndarray)` tuples in `MASKS` order, each 44100 samples long, produced via `bleeper.core.preset_preview` (assert with a monkeypatched spy)

### Implementation for User Story 4

- [ ] T035 [US4] In `src/bleeper/ui/submit.py::create_job`, when `custom_mask` is set: copy it to `jobs/<id>/mask{suffix.lower()}` and set `mask = f"custom: {Path(custom_mask).name}"`; in `src/bleeper/ui/worker.py`, when `job.mask` starts with `"custom: "`, pass `mask_path=<that copy>` and `preset=None`, otherwise `preset=job.mask` and `mask_path=None`
- [ ] T036 [US4] In `src/bleeper/ui/app.py`, add `preview_values() -> list[tuple[int, np.ndarray]]` calling `preset_preview(code)` for each `MASKS` value, and render one `gr.Audio(value=..., label=f"Preview: {label}", interactive=False)` per preset next to the mask radio; add `gr.File(label="Custom mask (optional, overrides the preset)", file_types=[".wav", ".mp3"])` and pass it to the submit handler

**Checkpoint**: Presets are previewable; custom masks work and match the CLI

---

## Phase 7: User Story 5 - Keep and tidy the jobs list (Priority: P3)

**Goal**: The jobs list survives page refreshes and restarts (persisted to `jobs.json`, interrupted jobs marked failed); jobs can be deleted except while running.

**Independent Test**: Save and reload a store: all jobs return, and queued/running ones are `failed` with the "Interrupted" message; deleting done/failed/queued jobs removes them and their directories; deleting a running job raises `JobBusyError`.

### Tests for User Story 5 ⚠️ (write first, ensure they fail)

- [ ] T037 [P] [US5] Add to `tests/unit/test_ui_jobs.py`: `test_persist_round_trip` (add jobs in all four statuses, create a new `JobStore` on the same dir and `load()`; done and failed jobs are equal field by field); `test_jobs_json_matches_schema` (`jobs.json` has `{"version": 1, "jobs": [...]}`, newest first, and every job has exactly the 13 keys of contracts/jobs-store-schema.json, `id` matching `^[0-9a-f]{12}$`, `status` in the enum); `test_recovery_marks_interrupted` (queued/running → `failed`, `error == "Interrupted: the UI stopped before this job finished. Submit it again."`, `finished_at` set; leftover `input.*`/`words.txt`/`mask.*` deleted, results kept); `test_missing_file_starts_empty`; `test_corrupt_file` (garbage `jobs.json` → empty store, file renamed to `jobs.json.corrupt`, `store.notice` set); `test_atomic_write` (no `*.tmp` left in the data dir after writes); `test_progress_not_persisted` (`set_progress` doesn't rewrite `jobs.json`: compare mtime_ns)
- [ ] T038 [P] [US5] Add to `tests/unit/test_ui_jobs.py`: `test_delete_done_and_failed` (job removed from `list()`, `jobs/<id>/` gone, `jobs.json` updated); `test_delete_running_refused` (`JobBusyError`, job and files kept); add to `tests/unit/test_ui_worker.py::test_deleted_queued_job_never_runs` (with A blocked, submit B, delete B, release A; B never reaches the transcriber and doesn't reappear)
- [ ] T039 [P] [US5] Add to `tests/integration/test_ui_app.py`: the delete handler for a done job returns the cleared panel ("Select a job in the table to see its result.") and a table without the job; for a running job it returns the note "This job can be deleted once it finishes." and keeps the job; `render_details` for a running job has `can_delete == False`; a done job whose WAV was removed shows "The result files for this job are no longer available." with `can_delete == True`; `build_app` on a store with `notice` set renders the notice above the table

### Implementation for User Story 5

- [ ] T040 [US5] In `src/bleeper/ui/jobs.py` add persistence: `_save()` (called with the lock held) writes `{"version": 1, "jobs": [job.to_dict() for job in newest-first]}` to `data_dir / "jobs.json"` atomically (`tempfile.mkstemp(dir=data_dir, suffix=".tmp")`, `json.dump(..., indent=2, ensure_ascii=False)`, `os.replace`, unlink the temp file on error); call it from `add`, `start`, `finish`, `fail` and `delete`, but not from `set_progress`. Add `load()`: missing file → empty; `json.JSONDecodeError`/`KeyError`/`ValueError` → rename to `jobs.json.corrupt` (replacing an older one), empty store, `self.notice = "The saved jobs list could not be read and was reset. The old file was kept as jobs.json.corrupt."`; then recovery per data-model.md (queued/running → failed with the Interrupted message and `finished_at` now; delete `input.*`, `words.txt`, `mask.*` in every job dir) and save once
- [ ] T041 [US5] In `src/bleeper/ui/jobs.py` add `delete(id) -> None`: raise `JobBusyError("This job can be deleted once it finishes.")` if running; otherwise remove it from the dict, `shutil.rmtree(job_dir, ignore_errors=True)` and save; deleting an unknown id is a no-op
- [ ] T042 [US5] In `src/bleeper/ui/app.py` add a "Delete job" `gr.Button` to the details panel, interactive only when `DetailsView.can_delete`; its handler calls `store.delete(selected_id)`, and on success clears the selection, renders the empty panel and refreshes the table; on `JobBusyError` shows its message in the panel summary. In `render_details`, report "The result files for this job are no longer available." when a done job's files are missing (and return `None` paths). Show `store.notice` once in a `gr.Markdown` above the table when set
- [ ] T043 [US5] In `src/bleeper/ui/__main__.py`, call `store.load()` before starting the worker, so recovered jobs are listed on the first page load

**Checkpoint**: All user stories are functional; the list survives refreshes and restarts

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docs, guards and final validation across stories

- [ ] T044 [P] Add a "Web UI" section to `README.md`: install with `pip install -e ".[ui]"`, launch with `bleeper-ui` / `python -m bleeper.ui`, the `--port`/`--data-dir`/`BLEEPER_UI_DATA` options, limits (100 MB, 30 min), the data dir layout, and the note that output is identical to the CLI with the `small` model and 80 ms padding
- [ ] T045 [P] Add `tests/unit/test_ui_boundaries.py`: `bleeper.ui.jobs`, `bleeper.ui.submit` and `bleeper.ui.worker` don't import `gradio` (run `python -c` in a subprocess and check `"gradio" not in sys.modules`); `bleeper.core` and `bleeper.cli` don't import `gradio`; no module in `src/bleeper/ui/` imports `soundfile`, `numpy.fft` or `subprocess`, or calls `ffmpeg` (AST scan of `import` statements; `numpy` is allowed only in `app.py`, for the preview type)
- [ ] T046 [P] Add `tests/integration/test_ui_main.py`: `main(["--help"])` exits 0 and lists `--port` and `--data-dir`; with `gradio` hidden (`monkeypatch.setitem(sys.modules, "gradio", None)`), `main([])` returns 1 and prints the install hint; `BLEEPER_UI_DATA` is honored (monkeypatch `launch` to a no-op and assert the data dir is created)
- [ ] T047 Run the quality gates: `ruff format --check .`, `ruff check .`, and `pytest` (default run, offline, no model); fix any failures
- [ ] T048 Run the manual end-to-end check in `specs/002-gradio-web-ui/quickstart.md` section 3 (real model): two jobs queued/running, playback not interrupted by refreshes, `cmp` against the CLI output, page refresh, restart recovery, delete, no leftover input copies. Record the results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories
- **US1 (Phase 3)**: Depends on Foundational; the MVP
- **US2 (Phase 4)**: Depends on US1's worker (T017) and app (T020)
- **US3 (Phase 5)**: Depends on US1's `create_job` (T016), worker (T017) and app (T020); independent of US2
- **US4 (Phase 6)**: Depends on US1 (T016, T017, T020); independent of US2/US3
- **US5 (Phase 7)**: Depends on Foundational `JobStore` (T010) and US1's app (T020); independent of US2–US4
- **Polish (Phase 8)**: After all desired stories

### Within Each User Story

- Tests first; confirm they fail
- `submit.py` → `worker.py` → `app.py` → `__main__.py`
- Story checkpoint before moving on

### Parallel Opportunities

- T004 ∥ T005 (test files); T006 ∥ T007 ∥ T009 ∥ T010 (different files)
- All tests marked [P] within a story can be written in parallel
- After US1, the US3, US4 and US5 phases can proceed in parallel (they touch the same files, so
  merge in order: `submit.py`, `worker.py`, `app.py`)
- T044 ∥ T045 ∥ T046

---

## Parallel Example: User Story 1

```bash
# Write all US1 tests together:
Task: "test_create_job_happy_path in tests/unit/test_ui_submit.py"
Task: "test_job_runs_to_done in tests/unit/test_ui_worker.py"
Task: "CLI/UI byte parity in tests/integration/test_ui_parity.py"
Task: "build_app smoke + happy flow in tests/integration/test_ui_app.py"
```

## Parallel Example: Foundational

```bash
Task: "probe_audio + AudioInfo in src/bleeper/core/audio_io.py"
Task: "preset_preview in src/bleeper/core/presets.py"
Task: "LANGUAGES/MASKS mappings in src/bleeper/ui/submit.py"
Task: "JobStatus/Job/JobStore in src/bleeper/ui/jobs.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational
2. Phase 3 (US1): one job end to end, identical to the CLI
3. **STOP and VALIDATE**: run the US1 tests and submit one real file in the browser

### Incremental Delivery

1. Setup + Foundational → core additions tested
2. US1 → MVP (single job, results, parity)
3. US2 → queueing and responsiveness (completes the P1 acceptance criteria)
4. US3 → validation and failure reporting
5. US4 → previews and custom masks
6. US5 → persistence, restart recovery and delete (completes "refreshing keeps the list")
7. Polish → docs, boundary tests, quickstart

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- The page-refresh survival in US5 scenario 1 already holds after US1, because the store is
  server-side and `demo.load` renders it; US5 adds restart survival and delete
- Never log transcripts or audio content; only job ids, statuses and error messages
- Commit after each task or logical group
