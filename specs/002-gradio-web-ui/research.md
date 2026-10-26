# Phase 0 Research: Bleeper Web UI — Background Masking Jobs

All Technical Context unknowns are resolved below. Each entry: Decision / Rationale / Alternatives.

## R1. Gradio version and packaging

- **Decision**: Gradio 6 (`gradio>=6,<7`; 6.30.0 is current on PyPI, requires Python ≥ 3.10), added
  as an optional extra `bleeper[ui]` and to the `dev` extra so the default test run covers the UI.
  Console script `bleeper-ui = "bleeper.ui.__main__:main"`; `python -m bleeper.ui` runs the same
  `main()`.
- **Rationale**: The constitution allows Gradio for the UI feature only; an extra keeps the CLI
  install free of the web stack, and `bleeper.core`/`bleeper.cli` never import it.
- **Alternatives**: Making Gradio a hard dependency (bloats CLI installs); Gradio 5 (older, no
  reason to pin back).

## R2. Local-only and offline launch

- **Decision**: `launch(server_name="127.0.0.1", share=False, max_file_size=...)`; set
  `GRADIO_ANALYTICS_ENABLED=False` before importing Gradio; use a theme with system fonts only, so
  the browser makes no Google Fonts requests. `--port` (default 7860) and `--data-dir` flags.
- **Rationale**: Principle II (no network calls after the model download, nothing sent to third
  parties) and FR-002 (reachable only from the local machine). A test captures the `launch()`
  arguments and the environment to prove it (T046).
- **Alternatives**: `0.0.0.0` (exposes the UI on the network; out of scope); keeping Gradio's
  default theme (pulls web fonts from the internet).

## R3. Uploading audio without re-encoding

- **Decision**: Use `gr.File` (with `file_types` filters) for the main audio, the words file and the
  custom mask. Use `gr.Audio` only to play results and preset previews.
- **Rationale**: `gr.Audio` used as an input may convert/re-encode the upload, which would break
  the "identical to the CLI" guarantee (SC-003). `gr.File` hands over the original bytes, and the
  original file name is kept as the file's basename.
- **Alternatives**: `gr.Audio(type="filepath")` as input; rejected for the parity risk.

## R4. Background worker

- **Decision**: One `threading.Thread(daemon=True)` consuming a `queue.Queue` of job ids (FIFO).
  The worker looks up each id in the `JobStore`, skips ids deleted while queued, and calls
  `bleeper.core.process_audio` with a progress callback that writes into the job. A
  `threading.Lock` in the store guards every read and write.
- **Rationale**: FR-011 needs exactly one job at a time, in order; transcription is CPU-bound and
  faster-whisper releases the GIL in CTranslate2, so the Gradio event loop stays responsive. Jobs
  must outlive browser sessions, so they cannot be tied to a Gradio event.
- **Alternatives**: Gradio's built-in event queue with `concurrency_limit=1` (jobs die with the
  request, and there's no global jobs list); `multiprocessing` (the model can't be shared; more
  complex); `concurrent.futures` with one worker (works, but adds nothing over a thread + queue and
  makes skipping deleted jobs awkward).

## R5. Loading the model once

- **Decision**: The core already caches models (`bleeper.core.transcribe.load_model` is an
  `lru_cache`). The worker holds a single `WhisperTranscriber("small")` and passes it as
  `transcriber=` to every `process_audio` call; tests inject a fake transcriber the same way.
- **Rationale**: FR-014 / SC-007 are met with zero new core code; injecting the transcriber keeps
  the worker testable without a model.
- **Alternatives**: A UI-level model cache (duplicates core behavior; violates Principle I).

## R6. CLI parity

- **Decision**: The worker calls `process_audio(input, words, output, mask_path=… | preset=…,
  model="small", language=code_or_None, padding_ms=80)` with the report path left at its default
  (`output.with_suffix(".json")`), exactly the arguments the CLI builds from
  `bleeper IN --words W (--mask M | --preset P) -o OUT [--lang L]`. Output files are named
  `<original stem>_masked.wav` / `<original stem>_masked.json`.
- **Rationale**: SC-003 means byte-identical audio and report; using the same function with the same
  arguments is the only way to guarantee it without duplicating logic. A parity test runs the CLI
  `main()` and the worker on the same inputs with the same fake transcriber and compares bytes.
- **Alternatives**: Calling the CLI as a subprocess (slow, loses progress, reloads the model).

## R7. Checks at submit time, done by the core

- **Decision**: Add three small, additive functions to the core public API:
  - `probe_audio(path) -> AudioInfo` (in `core/audio_io.py`): checks the extension and reads the
    duration, sample rate and channels with `soundfile.info`, raising `InvalidInputError` for
    unsupported or unreadable files. libsndfile ≥ 1.1 reads MP3 headers (verified locally:
    libsndfile 1.2.2 reports a 3.0 s MP3 as 3.0 s), so no ffmpeg run is needed at submit time.
  - `load_words` is re-exported unchanged; the UI calls it to validate the words file (empty, only
    comments, not UTF-8) and get the entry count, with the CLI's own messages.
  - `preset_preview(name, seconds=1.0, sample_rate=44100) -> np.ndarray` (in `core/presets.py`):
    the preset at a fixed level with the core's 10 ms fade, for the preview players.
  The 100 MB check uses the file size (`Path.stat().st_size`), which isn't audio logic.
- **Rationale**: FR-003 forbids audio logic in the UI; the duration limit and the previews need
  audio inspection and generation, so both live in the core. The additions don't change any
  existing behavior, so the CLI's output is unaffected.
- **Alternatives**: Decoding the whole file to measure duration (slow for 30 minutes of audio);
  generating previews in the UI with numpy (duplicates preset logic).

## R8. Limits

- **Decision**: 100 MB = 100 × 1024 × 1024 bytes (shown as "100 MB"); 30 minutes = 1800.0 s;
  values at the limit are accepted. Two layers:
  1. Our submit check (authoritative for 100 MB–110 MB and for duration) names the limit and the
     file's actual size or duration.
  2. Gradio's `max_file_size="110mb"` guard stops very large files at upload time, before they are
     written to disk. Those uploads get Gradio's own "file too large" message, which doesn't show
     the actual size. The spec accepts this as an edge case, and the audio upload label always shows
     "max 100 MB, 30 min", so the user knows the limit before uploading.
  Custom masks and words files are capped by the same guard only.
- **Rationale**: FR-008 / Story 3 scenario 5 need the actual size or duration in the error for
  files near the limit; for multi-hundred-MB files, refusing the upload early protects disk and
  memory, which matters more than the exact wording.
- **Alternatives**: Relying only on Gradio's limit (generic message, no duration check).

## R9. Job storage and persistence

- **Decision**: Data directory defaults to `~/.bleeper/ui` (overridable with `--data-dir` or
  `BLEEPER_UI_DATA`). Layout: `jobs.json` plus `jobs/<job_id>/` holding copied inputs and results.
  `jobs.json` is written atomically (temp file in the same directory, then `os.replace`) on every
  status change, on create and on delete; progress updates stay in memory only. At start-up,
  queued/running jobs become `failed` with an "interrupted" message and any leftover input copies
  are removed. A corrupt `jobs.json` is renamed to `jobs.json.corrupt` and the UI starts empty with
  a notice.
- **Rationale**: FR-022/FR-023 (clarified: persistence required); atomic writes avoid a half-written
  file if the app is killed; writing only on status changes avoids disk churn every few hundred ms.
- **Alternatives**: SQLite (a database; out of scope); a per-job JSON file (more files, no benefit
  at this scale); writing on every progress tick (pointless, since running jobs are marked
  interrupted after a restart anyway).

## R10. Temporary files and privacy

- **Decision**:
  - **Gradio's cache lives in the data dir**: `main()` sets `GRADIO_TEMP_DIR=<data-dir>/tmp` before
    importing Gradio, so uploads and files Gradio serves (players, downloads) never land in the
    system temp dir. That directory is emptied at start-up.
  - **Uploads are deleted once used**: at submit, the uploads are copied into `jobs/<id>/` (input
    as `input<ext>`, `words.txt`, `mask<ext>`), and then the submit handler deletes the Gradio
    upload files (audio, words, custom mask) and clears those form fields. After a validation
    failure the uploads stay in the form so the user can fix one field without re-uploading; they
    are still inside `<data-dir>/tmp` and are removed by the cache purge or the next start-up.
  - **Job input copies are deleted when the job finishes**: the worker deletes them in a `finally`
    block, on done and on failed.
  - **Gradio's cache is purged**: `delete_cache=(600, 3600)` removes anything older than an hour
    every 10 minutes (served result copies, abandoned uploads).
  - Deleting a job removes `jobs/<id>/` entirely. Logs contain job ids, statuses and error messages
    only, never transcripts.
- **Rationale**: Principle II (temporary files deleted after use, including on error paths), FR-024
  (stored only in the local data directory), FR-025, SC-009 (no input copies remain once a job
  finishes). Without these steps Gradio would keep a copy of every upload in the system temp dir for
  up to an hour.
- **Alternatives**: Processing directly from Gradio's cache path (it can disappear before a queued
  job runs).

## R11. Layout and refresh

- **Decision**: `gr.Blocks` with the form at the top and a non-interactive `gr.Dataframe` jobs table
  below it, refreshed by `gr.Timer(2.0)`. `Dataframe.select` stores the selected job id in a
  per-session `gr.State`. The id is read from the clicked row's ID cell (`evt.row_value[0]`), never
  from the row position (`evt.index`): the table is re-rendered newest first every 2 s, so a job
  added between render and click would shift positions. Rows with an empty ID (the "No jobs yet"
  hint) are ignored. The job details panel (`gr.Audio`, two `gr.DownloadButton`s, a
  `gr.Markdown` summary and a Delete button) is updated by the same timer only when the selected
  job's `(id, status)` changes; otherwise the handler returns `gr.skip()` for the panel outputs,
  so playback is never interrupted. The Delete button is non-interactive while the job is running,
  and the store also refuses the deletion server-side. Page load (`demo.load`) renders the table
  from the global store, which is what makes the list survive a refresh.
- **Rationale**: Implements clarification Q2 (table + details panel) and FR-016 to FR-021.
  `gr.skip()` is the documented way to leave an output unchanged.
- **Alternatives**: One row/card per job with its own player (rebuilt by each refresh; rejected
  in Q2).

## R12. Option mappings

- **Decision**: Languages: Auto→`None`, Spanish→`es`, English→`en`, Portuguese→`pt`,
  French→`fr`, German→`de`, Italian→`it`. Masks: Classic beep→`beep`, Low tone→`tone`, Noise
  burst→`noise`; default Classic beep. A custom mask always wins over the selected preset, and
  "mask used" records `custom: <file name>`.
- **Rationale**: FR-005 / FR-007; these are the CLI's `--lang`/`--preset` values, so the parity
  holds.

## R13. Testing strategy

- **Decision**: The store, worker and submission modules don't import Gradio and are tested
  directly with a fake transcriber and synthetic audio (reusing `tests/conftest.py`). The Gradio
  layer is tested by calling its handler functions directly and by building the `Blocks` without
  launching it. The parity test compares CLI and worker output bytes. A worker test asserts FIFO
  order and that the transcriber instance is reused. No test needs the network or a real model.
- **Rationale**: Principle V; fast, deterministic tests for the acceptance criteria.
- **Alternatives**: Browser automation (Playwright: extra dependency, slow; manual checks in
  quickstart instead).
