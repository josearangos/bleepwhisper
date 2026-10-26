---

description: "Task list for Bleeper CLI — Mask Forbidden Words in Audio"
---

# Tasks: Bleeper CLI — Mask Forbidden Words in Audio

**Input**: Design documents from `/specs/001-cli-word-masking/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (cli.md, python-api.md,
report-schema.json), quickstart.md

**Tests**: INCLUDED. The constitution (Principle V) requires pytest for every module, and the spec
defines acceptance criteria that must be proven by tests. Within each story, write tests first and
confirm they fail before implementing.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Paths are relative to the repository root (single project, `src/` layout)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling

- [X] T001 Create `pyproject.toml` at repo root: name `bleeper`, `requires-python = ">=3.10"`, setuptools backend with `src/` layout, runtime deps `faster-whisper`, `numpy`, `soundfile` (no others), optional `dev` extra `pytest`, `ruff`, console script `bleeper = "bleeper.cli:main"`; `[tool.ruff]` with `target-version = "py310"`, `line-length = 100`, lint rules `E,F,I,UP,B,ANN` (ignore `ANN401` only if needed); `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `markers = ["whisper: requires a downloaded Whisper model"]`, `addopts = "-m 'not whisper'"`
- [X] T002 Create package skeleton: `src/bleeper/__init__.py` (only `__version__ = "0.1.0"`), empty `src/bleeper/core/__init__.py`, and test dirs `tests/unit/`, `tests/integration/`, `tests/whisper/` (no `__init__.py` needed with pytest rootdir conftest)
- [X] T003 [P] Create `.gitignore` at repo root ignoring `.venv/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, `/out/`, and any `*.wav` / `*.mp3` file (audio is never committed; do not ignore `*.json`, so `contracts/report-schema.json` stays tracked)
- [X] T004 Create the dev environment and verify tooling: `uv venv && uv pip install -e ".[dev]"`, then `ruff check .` and `pytest` run (pytest may report "no tests collected")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, errors and test fixtures used by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Implement errors in `src/bleeper/core/errors.py`: `BleeperError(Exception)`, `InvalidInputError(BleeperError)` (CLI exit 1), `ProcessingError(BleeperError)` (CLI exit 2); each message must state what failed and how to fix it
- [X] T006 [P] Implement frozen dataclasses in `src/bleeper/core/models.py` per data-model.md: `TranscribedWord(text: str, start: float, end: float)`, `Transcription(words: list[TranscribedWord], language: str)` (language = the requested code, or the detected one when none was given), `Match(text: str, start: float, end: float)`, `Span(start: int, end: int, words: tuple[str, ...])` ("First masked sample (inclusive), ≥ 0" / "Last masked sample (exclusive), ≤ n_samples, > start"), `ReportEntry(word: str, start: float, end: float)` with `to_dict()`, `ProcessResult(output_path: Path, report_path: Path, report: list[ReportEntry], language: str)`, and `ProgressCallback = Callable[[str, float], None]`
- [X] T007 Create `tests/conftest.py` with: `make_tone(path, seconds, sr=16000, channels=1, subtype="PCM_16", freq=220.0, amp=0.3)` fixture factory writing synthetic WAVs via soundfile into `tmp_path`; a `words_file(tmp_path, lines: list[str]) -> Path` factory; and `FakeTranscriber(words: list[TranscribedWord], language="en")` implementing `transcribe(audio_path, language, on_progress) -> Transcription` (calls `on_progress(0.5)` then `on_progress(1.0)`; returns `Transcription(words, language or self.language)`; records the call arguments)

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 - Bleep forbidden words with a built-in preset (Priority: P1) 🎯 MVP

**Goal**: `bleeper input.wav --words words.txt --preset beep -o out.wav` masks every matched word with a generated preset, keeps format/duration, writes a JSON report.

**Independent Test**: With a FakeTranscriber reporting a forbidden word at 2.0–2.5 s on a 5 s synthetic WAV and default padding, only samples in [round(1.92·sr), round(2.58·sr)) differ, sample count/rate/channels match, report is `[{"word": ..., "start": 1.92, "end": 2.58}]`, exit code 0; with no matches the output is sample-identical and report is `[]`.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [X] T008 [P] [US1] Unit tests in `tests/unit/test_words.py`: UTF-8 parsing; blank lines and lines starting with `#` after leading whitespace are skipped; whitespace trimmed; duplicates collapsed; "Señor" → tokens `("senor",)`; "shut up" → `("shut", "up")`; a line that is only punctuation is skipped; a file with no usable entries raises `InvalidInputError` mentioning "no forbidden words"; missing file and non-UTF-8 file raise `InvalidInputError`
- [X] T009 [P] [US1] Unit tests in `tests/unit/test_matching.py`: `normalize` lowercases, strips accents, deletes punctuation/symbols ("Don't!" → `["dont"]`, " senor," → `["senor"]`); whole-token only ("ass" does not match "class"); multi-word phrase matches only consecutive words and spans first start → last end; repeated occurrences all matched; transcript words that normalize to empty are ignored; matches returned in transcript order
- [X] T010 [P] [US1] Unit tests in `tests/unit/test_spans.py`: padding converted with `round(padding_ms*sr/1000)` samples; times converted with `round(t*sr)`; clamping to `[0, n_samples]` at start and end; overlapping and touching (`next.start <= cur.end`) spans merge with words kept in order; non-touching spans stay separate; zero-length spans dropped; padding 0 yields exact word bounds
- [X] T011 [P] [US1] Unit tests in `tests/unit/test_presets.py`: `generate_preset(name, n_samples, sr)` returns float64 mono array of exactly `n_samples`; `beep` has dominant frequency 1000 Hz and `tone` 400 Hz (check via `numpy.fft.rfft` peak); `noise` is deterministic (two calls equal) and non-periodic; unknown name raises `InvalidInputError`
- [X] T012 [P] [US1] Unit tests in `tests/unit/test_masking.py` (preset path): `apply_masks` returns a new array (input not mutated); samples outside spans bit-identical for int32 and float32 data; masked region RMS ≈ RMS of up to 500 ms each side (span excluded) within 1 dB; with two spans 300 ms apart, the second span's level matches the RMS of the *original* surrounding audio (not the first mask); silent surroundings → RMS ≈ 0.1 (-20 dBFS); peak never exceeds 0.99 FS (test with loud surroundings); first/last 10 ms ramp linearly from/to 0; spans shorter than 20 ms use half-span fades; multi-channel input gets the same mask on every channel
- [X] T013 [P] [US1] Unit tests in `tests/unit/test_report.py`: `to_report(spans, sr)` gives `word = " ".join(span.words)`, `start/end = round(sample/sr, 3)`, ordered by start; `write_report(path, entries)` writes JSON matching `specs/001-cli-word-masking/contracts/report-schema.json` (array of `{word, start, end}`, no extra keys, UTF-8, `ensure_ascii=False`), writes `[]` for no entries, replaces an existing file, and leaves no temp file
- [X] T014 [P] [US1] Unit tests in `tests/unit/test_audio_io.py`: `load_audio` on PCM_16/PCM_24/FLOAT WAVs returns `(n, channels)` array (int32 for PCM, float for FLOAT) plus sample rate and subtype; `write_wav` round-trips bit-identically with the same subtype; `write_wav` is atomic (no temp file left, existing file replaced, on simulated failure no partial file); mp3 input decoded via ffmpeg to PCM_16 at native rate/channels (skip if `shutil.which("ffmpeg")` is None, generate the mp3 with ffmpeg in `tmp_path`); missing file / unsupported extension raise `InvalidInputError`; mp3 without ffmpeg (monkeypatch `shutil.which`) raises `InvalidInputError` mentioning "install ffmpeg"
- [X] T015 [P] [US1] Unit tests in `tests/unit/test_transcribe.py`: `WhisperTranscriber` maps a stubbed model's segments/words (monkeypatch the model loader, no real model) into a `Transcription` whose `words` are `TranscribedWord`s, passes `word_timestamps=True`, `language` through, reports progress as `segment.end / info.duration`, and sets `Transcription.language` to `info.language` when no language was requested; loader is called with `device="cpu"`, `compute_type="int8"`, tries `local_files_only=True` first and retries without it only when the model is not cached; load failure raises `ProcessingError`; faster-whisper `ValueError` for an invalid language raises `InvalidInputError`
- [X] T016 [US1] Integration tests in `tests/integration/test_pipeline.py` using `FakeTranscriber` and synthetic WAVs: acceptance "word at 2.0–2.5 s → only [1.92 s, 2.58 s) differs, same duration/rate/channels"; "no matches → output samples equal input, report `[]`"; input file bytes and mtime unchanged; report path defaults to `output.with_suffix(".json")`; existing output/report replaced; stereo PCM_24 input preserved
- [X] T017 [US1] Integration tests in `tests/integration/test_cli.py` calling `bleeper.cli.main(argv)` with a monkeypatched default transcriber (FakeTranscriber): `--preset beep` run exits 0 and prints "Masked 1 span" plus output and report paths; no-match run exits 0 and prints "No forbidden words found"; stdout/stderr never contain transcript or words-file text

### Implementation for User Story 1

- [X] T018 [P] [US1] Implement `src/bleeper/core/words.py`: `ForbiddenEntry(original: str, tokens: tuple[str, ...])` frozen dataclass; `parse_words(text: str) -> list[ForbiddenEntry]` and `load_words(path: Path) -> list[ForbiddenEntry]` per data-model.md validation ("lines that are blank or start with `#` (after leading whitespace) are skipped; lines whose normalization is empty are skipped; duplicates (same `tokens`) are collapsed"); raise `InvalidInputError` for missing file, non-UTF-8 ("the words file must be UTF-8"), or no entries ("no forbidden words found in <path>")
- [X] T019 [P] [US1] Implement `src/bleeper/core/matching.py`: `normalize(text: str) -> list[str]` (NFKD → drop category `Mn` → `casefold` → delete categories `P*` and `S*` → split on whitespace); `find_matches(words: Sequence[TranscribedWord], entries: Sequence[ForbiddenEntry]) -> list[Match]` sliding each entry's token tuple over the flattened transcript tokens (each token keeps its source word's start/end), `Match.text` = stripped source words joined by one space; pure, no I/O (make `words.py` import `normalize` from here)
- [X] T020 [P] [US1] Implement `src/bleeper/core/spans.py`: `build_spans(matches: Sequence[Match], sample_rate: int, n_samples: int, padding_ms: int) -> list[Span]` — `start = round(m.start*sr) - pad`, `end = round(m.end*sr) + pad`, `pad = round(padding_ms*sr/1000)`, clamp to `[0, n_samples]`, sort, merge when `next.start <= cur.end`, drop zero-length; pure
- [X] T021 [P] [US1] Implement `src/bleeper/core/presets.py`: `PRESETS = ("beep", "tone", "noise")`; `generate_preset(name: str, n_samples: int, sample_rate: int) -> np.ndarray` returning float64 mono at unit-ish amplitude: `beep` 1000 Hz sine, `tone` 400 Hz sine, `noise` white noise from `np.random.default_rng(0).uniform(-1, 1, n_samples)`; unknown name → `InvalidInputError`
- [X] T022 [US1] Implement `src/bleeper/core/masking.py` (depends on T021): `to_float(segment, dtype)` / `from_float(segment, dtype)` helpers (int32 ↔ [-1, 1) with clipping on conversion back); `fade(mask, sample_rate)` 10 ms linear in/out (half span if span < 20 ms); `match_level(mask, context)` scaling to context RMS (context = up to 500 ms each side of span, span excluded, clamped, all channels, always sliced from the original `samples` argument, never from the working copy being masked), using 0.1 when context RMS < 1e-4, and reducing gain so peak ≤ 0.99; `apply_masks(samples: np.ndarray, sample_rate: int, spans: Sequence[Span], mask_for: Callable[[int], np.ndarray]) -> np.ndarray` copying `samples`, building each span's mono mask via `mask_for(length)`, applying level → fade, broadcasting to all channels, and writing back in the original dtype only inside the span; pure
- [X] T023 [P] [US1] Implement `src/bleeper/core/report.py`: `to_report(spans: Sequence[Span], sample_rate: int) -> list[ReportEntry]` and `write_report(path: Path, entries: Sequence[ReportEntry]) -> None` writing JSON (`indent=2`, `ensure_ascii=False`) to a temp file in the same directory then `os.replace`, removing the temp file on error
- [X] T024 [P] [US1] Implement `src/bleeper/core/audio_io.py`: `AudioData(samples, sample_rate, subtype)` with `n_samples`/`channels` properties; `load_audio(path: Path, tmp_dir: Path) -> tuple[AudioData, Path]` returning the decoded data and the path to give the transcriber — WAV with PCM/FLOAT/DOUBLE subtype read via soundfile (`always_2d=True`, dtype `int32` for PCM, `float32`/`float64` for float), MP3 or other WAV subtypes decoded with `ffmpeg -nostdin -v error -i IN -acodec pcm_s16le -f wav TMP` into `tmp_dir` (subtype `PCM_16`); `write_wav(path: Path, audio: AudioData) -> None` atomic via temp file in destination dir + `os.replace`; errors: missing/unsupported/corrupt file → `InvalidInputError`, ffmpeg missing → `InvalidInputError` ("install ffmpeg"), ffmpeg failure on a valid file or write failure → `ProcessingError`
- [X] T025 [P] [US1] Implement `src/bleeper/core/transcribe.py`: `Transcriber` Protocol (`transcribe(audio_path: Path, language: str | None, on_progress: Callable[[float], None]) -> Transcription`; stateless per call, so one instance is reusable); `WhisperTranscriber(model: str = "small")` loading `faster_whisper.WhisperModel(model, device="cpu", compute_type="int8", local_files_only=True)` with fallback to download only if not cached, cached per model name with `functools.lru_cache`; iterates segments with `word_timestamps=True`, reports `segment.end / info.duration`; maps load failures to `ProcessingError` and invalid-language `ValueError` to `InvalidInputError`; never logs transcript text
- [X] T026 [US1] Implement `src/bleeper/core/pipeline.py` `process_audio(input_path, words_path, output_path, *, mask_path=None, preset=None, model="small", language=None, padding_ms=80, report_path=None, progress=None, transcriber=None) -> ProcessResult` per contracts/python-api.md, preset path only for now (until T034 lands, a `mask_path` argument raises `InvalidInputError("custom masks are not supported yet")`; T034 removes this): load words → load audio in a `tempfile.TemporaryDirectory()` → transcribe (use `Transcription.words`; set `ProcessResult.language` from `Transcription.language`) → `find_matches` → `build_spans` → `apply_masks` with `lambda n: generate_preset(preset, n, sr)` → `write_wav` → `write_report`; wrap unexpected exceptions in `ProcessingError`; on error ensure output/report are not created
- [X] T027 [US1] Export the public API from `src/bleeper/core/__init__.py`: `process_audio`, `ProcessResult`, `ReportEntry`, `ProgressCallback`, `Transcriber`, `Transcription`, `TranscribedWord`, `BleeperError`, `InvalidInputError`, `ProcessingError`, `PRESETS` (with `__all__`)
- [X] T028 [US1] Implement `src/bleeper/cli.py`: `build_parser()` with `INPUT`, required `--words`, required mutually exclusive group `--mask`/`--preset` (`choices=PRESETS`), required `-o/--output`, `--model` (default `small`), `--lang`, `--padding` (int, default 80), `--report`; `main(argv: list[str] | None = None) -> int` calling `core.process_audio` and printing the success summary from contracts/cli.md ("Masked N span(s)." or "No forbidden words found; output is identical to the input.", then `Output:` and `Report:` lines); map `InvalidInputError` → 1, `ProcessingError` → 2 with `error: <message>` on stderr; module guard `raise SystemExit(main())`; no audio logic in this file

**Checkpoint**: User Story 1 is fully functional — `pytest` green for T008–T017; MVP demo with `--preset beep`

---

## Phase 4: User Story 2 - Use a custom mask sound (Priority: P2)

**Goal**: `--mask mask.wav` fills each span with the user's sound, looped or trimmed to exactly the span length, converted to the input's rate and channels.

**Independent Test**: With a 660 ms span, a 200 ms custom mask is looped and a 2 s mask is trimmed; in both cases exactly the span's samples change, with 10 ms fades; a 44.1 kHz stereo mask on a 16 kHz mono input still yields output at 16 kHz mono with unchanged duration.

### Tests for User Story 2 ⚠️

- [X] T029 [P] [US2] Unit tests in `tests/unit/test_masking.py` (append): `fit_to_length(mask, n)` loops a 200 ms mask to exactly n samples (content repeats with period = mask length) and trims a 2 s mask to exactly n samples; empty mask raises `InvalidInputError`
- [X] T030 [P] [US2] Unit tests in `tests/unit/test_audio_io.py` (append): `load_mask(path, sample_rate, tmp_dir)` returns float64 mono at the target rate; stereo mask averaged to mono; differing sample rate resampled via ffmpeg (skip if no ffmpeg) with length scaled accordingly; missing mask file raises `InvalidInputError`
- [X] T031 [US2] Integration tests in `tests/integration/test_pipeline.py` (append): custom 200 ms and 2 s masks on the 2.0–2.5 s word → masked region exactly 660 ms (0-sample difference, SC-003), outside identical; 44.1 kHz stereo mask on 16 kHz mono input → output 16 kHz mono, same sample count; CLI `--mask` run in `tests/integration/test_cli.py` exits 0

### Implementation for User Story 2

- [X] T032 [US2] Add `fit_to_length(mask: np.ndarray, n_samples: int) -> np.ndarray` to `src/bleeper/core/masking.py` (tile via `np.resize` then slice; empty mask → `InvalidInputError`); pure
- [X] T033 [US2] Add `load_mask(path: Path, sample_rate: int, tmp_dir: Path) -> np.ndarray` to `src/bleeper/core/audio_io.py`: load via `load_audio`, convert to float64 mono (average channels), resample with `ffmpeg -nostdin -v error -i IN -ar <sr> -acodec pcm_s16le TMP` only when rates differ; channel broadcast to the input happens in `apply_masks`
- [X] T034 [US2] Wire the custom mask branch in `src/bleeper/core/pipeline.py`: when `mask_path` is set, load it once with `load_mask` and use `mask_for = lambda n: fit_to_length(mask, n)`; remove any "not yet supported" placeholder

**Checkpoint**: User Stories 1 and 2 both work independently

---

## Phase 5: User Story 3 - Clear errors and tunable options (Priority: P2)

**Goal**: Every invalid input exits 1 and every processing failure exits 2 with an actionable message; `--lang`, `--model`, `--padding`, `--report` take effect; `--help` documents everything.

**Independent Test**: Run each invalid scenario from spec US3 and contracts/cli.md and assert exit code + message; run with `--padding 0` and `--report custom.json` and assert effects; force a transcription failure and assert exit 2 with no output, report or temp files left.

### Tests for User Story 3 ⚠️

- [X] T035 [P] [US3] CLI error tests in `tests/integration/test_cli.py` (append): missing words file → 1 and message names the file; words file with only blanks/comments → 1 "no forbidden words found"; both `--mask` and `--preset` → 1; neither → 1; unknown `--preset` → 1; negative `--padding` → 1; output path equal to input (also via a different relative spelling) → 1; report path equal to output or input → 1; output directory missing → 1; missing input → 1; unknown argument → 1 (argparse remapped, not 2); all error output is a single `error: ...` line on stderr
- [X] T036 [P] [US3] Processing-failure tests in `tests/integration/test_pipeline.py` (append): a transcriber raising `ProcessingError` and one raising an arbitrary `RuntimeError` → `ProcessingError`, no output, no report, no stray temp files in the output dir or `tempfile.gettempdir()` created by the run (compare listings), input unchanged; CLI maps these to exit 2
- [X] T037 [US3] Option tests in `tests/integration/test_cli.py` (append; after T035, same file): `--padding 0` masks exactly 2.0–2.5 s; `--report custom.json` writes there; `--lang es` and `--model tiny` are passed to the transcriber factory (monkeypatched); `--help` output contains every option, the defaults `small` and `80`, and the text "Exit codes: 0 success, 1 invalid input, 2 processing error"

### Implementation for User Story 3

- [X] T038 [US3] Add upfront validation to `src/bleeper/core/pipeline.py` before any decoding or transcription: exactly one of `mask_path`/`preset`; `preset in PRESETS`; `padding_ms >= 0`; input, words and mask exist; resolved `input_path`, `output_path`, `report_path` pairwise distinct ("refusing to overwrite the input file"); output and report parent directories exist — all raising `InvalidInputError` with what/how-to-fix messages
- [X] T039 [US3] Harden `src/bleeper/cli.py`: subclass `argparse.ArgumentParser` overriding `error()` to print `error: <message>` to stderr and exit 1; use `ArgumentDefaultsHelpFormatter`; add an epilog "Exit codes: 0 success, 1 invalid input, 2 processing error"; help text for every option as in contracts/cli.md; pass `model`, `lang`, `padding`, `report` through to `process_audio`
- [X] T040 [US3] Ensure cleanup on every failure path in `src/bleeper/core/pipeline.py`, `src/bleeper/core/audio_io.py` and `src/bleeper/core/report.py`: temp output/report files removed in `finally`/`except`; if the WAV was written but the report write fails, remove the new WAV so no partial result remains

**Checkpoint**: User Stories 1–3 work; every exit-code scenario in contracts/cli.md is covered

---

## Phase 6: User Story 4 - Reusable processing API with progress (Priority: P3)

**Goal**: `bleeper.core.process_audio` reports monotonic progress through a callback and yields output identical to the CLI.

**Independent Test**: Call `process_audio` with a recording callback: stages appear in order `loading → transcribing → masking → writing → done`, fractions are non-decreasing in [0, 1] ending at `("done", 1.0)`; CLI and API runs with identical inputs produce byte-identical WAV and report files.

### Tests for User Story 4 ⚠️

- [X] T041 [P] [US4] Progress tests in `tests/integration/test_pipeline.py` (append): recorded `(stage, fraction)` calls are non-decreasing, within [0, 1], stages in order, transcribing fractions within 0.05–0.85, last call `("done", 1.0)`; no callback → runs fine; a callback that raises aborts with that exception and leaves no output
- [X] T042 [P] [US4] Parity test in `tests/integration/test_cli.py` (append): same inputs via `main([...])` and via `process_audio(...)` (both with the same FakeTranscriber, preset `noise` to exercise determinism, and a custom mask) produce byte-identical WAV files and identical report JSON

### Implementation for User Story 4

- [X] T043 [US4] Add progress reporting in `src/bleeper/core/pipeline.py`: a private `_Progress` wrapper around the optional callback that clamps to [0, 1] and never goes backwards; emit `loading` 0.0→0.05, map transcriber `on_progress(f)` to `transcribing` 0.05 + 0.80·f, `masking` 0.85→0.95, `writing` 0.95→1.0, and final `("done", 1.0)` only on success
- [X] T044 [US4] Show progress in `src/bleeper/cli.py` by passing a callback that writes `\r[<stage>] NN%` to stderr (newline at `done`, nothing when stderr is not a TTY); no other logic

**Checkpoint**: All four user stories are independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T045 [P] Optional real-model test in `tests/whisper/test_real_model.py` marked `@pytest.mark.whisper`: `pytest.importorskip("faster_whisper")`, skip if the `tiny` model is not cached; run `process_audio` with `model="tiny"` on a tiny speech clip generated at test time (e.g. macOS `say -o` → ffmpeg to WAV, skip if unavailable) and assert the report contains the spoken forbidden word and duration is preserved; add a second test that times `process_audio` with `model="small"` on a 60 s clip (speech built the same way, padded or repeated to 60 s), skips if `small` is not cached, asserts wall time < 60 s (SC-006, reference machine: Apple M-series laptop, 8 GB RAM) and prints the measured time
- [X] T046 [P] Write `README.md` at repo root: purpose, install (`uv pip install -e .`, ffmpeg), usage from contracts/cli.md, words file format, presets, exit codes, report format, offline/privacy notes, Python API example with progress callback, known limitation (digits vs spelled numbers)
- [X] T047 Run `ruff format .` and `ruff check .` and fix all findings; confirm every function is type-hinted and no unused code or imports remain across `src/` and `tests/`
- [X] T048 Run the default `pytest` with the network disabled (no model cached required) and confirm all tests pass; then execute the quickstart.md validation steps 1–3 and record results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — blocks all stories
- **US1 (Phase 3)**: depends on Foundational
- **US2 (Phase 4)**: depends on US1's `masking.py`, `audio_io.py`, `pipeline.py` (extends them)
- **US3 (Phase 5)**: depends on US1's `pipeline.py` and `cli.py`; independent of US2 (its mask tests can use presets; the "both/neither mask" checks only need argparse)
- **US4 (Phase 6)**: depends on US1; T042 parity with a custom mask also needs US2
- **Polish (Phase 7)**: after desired stories

### User Story Dependencies

```text
Setup → Foundational → US1 ─┬─► US2 ─┐
                            ├─► US3 ─┼─► US4 ─► Polish
                            └────────┘
```

### Within Each User Story

- Tests first; confirm they fail
- Pure modules (words, matching, spans, presets, masking, report) before I/O (audio_io, transcribe)
- Pipeline after its modules; CLI after pipeline

### Parallel Opportunities

- T003 with T001/T002
- T005 and T006
- US1 tests T008–T015 all in parallel (different files); T016/T017 after T007
- US1 implementation T018–T021, T023–T025 in parallel; T022 after T021; T026 after all; T027–T028 after T026
- US2 tests T029/T030 in parallel
- US3 tests T035 and T036 in parallel; T037 after T035 (same file)
- US4 tests T041/T042 in parallel
- T045 and T046 in parallel

---

## Parallel Example: User Story 1

```bash
# Tests (all different files):
Task: "Unit tests in tests/unit/test_words.py"
Task: "Unit tests in tests/unit/test_matching.py"
Task: "Unit tests in tests/unit/test_spans.py"
Task: "Unit tests in tests/unit/test_presets.py"
Task: "Unit tests in tests/unit/test_masking.py"
Task: "Unit tests in tests/unit/test_report.py"
Task: "Unit tests in tests/unit/test_audio_io.py"
Task: "Unit tests in tests/unit/test_transcribe.py"

# Pure + I/O modules:
Task: "Implement src/bleeper/core/words.py"
Task: "Implement src/bleeper/core/matching.py"
Task: "Implement src/bleeper/core/spans.py"
Task: "Implement src/bleeper/core/presets.py"
Task: "Implement src/bleeper/core/report.py"
Task: "Implement src/bleeper/core/audio_io.py"
Task: "Implement src/bleeper/core/transcribe.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational
2. Phase 3 US1 (preset masking end to end)
3. **STOP and VALIDATE**: `pytest` green; run quickstart.md step 3 with `--preset beep`

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → MVP (presets, WAV/MP3, report)
3. US2 → custom masks
4. US3 → full validation, exit codes, options, cleanup guarantees
5. US4 → progress callback + parity, ready for Feature 2 (Gradio UI)
6. Polish → README, real-model test, lint, quickstart validation

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- Never commit audio files; fixtures are generated in `tmp_path`
- Never log or print transcript text, audio content or words-file content
- Commit after each task or logical group
