---

description: "Task list for the harmonic profanity mask for songs"
---

# Tasks: Harmonic Profanity Mask for Songs

**Input**: Design documents from `/specs/005-song-profanity-mask/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (python-api.md, cli.md,
report.md, ui.md), quickstart.md

**Tests**: Included. Constitution Principle V requires pytest tests for every module, and masking
logic must be unit-tested without a Whisper model. Existing tests may only be **extended**, never
weakened: every existing assertion for presets and custom masks must keep passing unchanged
(FR-014).

**Organization**: Tasks are grouped by user story (US1–US4 from spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)

## Path Conventions

Single project: `src/bleeper/core/`, `src/bleeper/cli.py`, `src/bleeper/ui/`, `tests/unit/`,
`tests/integration/` at the repository root. Run commands with the repo venv
(`.venv/bin/python -m pytest`, `.venv/bin/ruff`). Style codes are exactly `"vocal-dropout"`,
`"reverse"`, `"dip"` everywhere (core, CLI, UI, report).

---

## Phase 1: Setup

Work happens on branch `005-song-profanity-mask` (created 2026-11-26). Constitution is at 1.0.1
(Principle III allows the 10 ms crossfade for in-place transformations).

- [X] T001 Run `.venv/bin/ruff format --check && .venv/bin/ruff check && .venv/bin/python -m pytest` from the repo root and record that everything passes on the untouched code (baseline for FR-014 / SC-004)
- [X] T002 [P] Add shared synthetic stereo fixtures to `tests/conftest.py`: a helper `make_song(seconds=2.0, sample_rate=16000) -> np.ndarray` returning float64 `(n, 2)` audio made of (a) a centered "voice" sine at 1000 Hz (same on L and R), (b) a centered "bass" sine at 60 Hz, (c) a "wide instrument" sine at 440 Hz on L only and 660 Hz on R only, each at amplitude 0.2; and a fixture `song_file(tmp_path)` that writes it with `soundfile` as a PCM_16 WAV and returns the path. Keep it tiny (no committed audio, Principle V)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared plumbing every style needs: the new module, the `style`/`dip_db` options, the
report fields and the result notes. No style produces audible output yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Create `src/bleeper/core/song_styles.py` (module docstring "Song-friendly masking styles that transform spans in place (pure)."; `from __future__ import annotations`; fully type-hinted; imports only numpy, `bleeper.core.errors`, `bleeper.core.masking` (`to_float`, `from_float`) and `bleeper.core.models`). Add `SONG_STYLES = ("vocal-dropout", "reverse", "dip")`; `_FADE_SECONDS = 0.010`; `crossfade_edges(original, processed, sample_rate) -> np.ndarray` doing a linear crossfade original→processed over the first `length` samples and processed→original over the last `length` samples, where `length = min(round(0.010 * sample_rate), n // 2)` (same rule as `masking.fade`; research R4), broadcasting over channels; and `apply_styles(samples, sample_rate, spans, style, dip_db=None) -> np.ndarray` that copies `samples`, and for each span converts `samples[span.start:span.end]` with `to_float`, calls `apply_style(...)`, then `crossfade_edges(...)`, and writes back with `from_float(..., samples.dtype)`. Add `apply_style(block, sample_rate, style, dip_db=None)` as a dispatcher that raises `InvalidInputError(f"unknown style '{style}'. Choose one of: vocal-dropout, reverse, dip.")` for unknown names; each branch is filled in by its story
- [X] T004 [P] In `src/bleeper/core/models.py`, extend `ReportEntry` with `style: str | None = None` and `requested_style: str | None = None`; `to_dict()` must add `"style"` / `"requested_style"` keys only when they are not `None`, so preset/custom reports stay byte-identical (data-model.md, contracts/report.md). Extend `ProcessResult` with `notes: tuple[str, ...] = ()`
- [X] T005 [P] In `src/bleeper/core/report.py`, add keyword arguments `style: str | None = None, requested_style: str | None = None` to `to_report(spans, sample_rate, ...)` and pass them to every `ReportEntry`
- [X] T006 In `src/bleeper/core/pipeline.py`, add keyword parameters `style: str | None = None` and `dip_db: float | None = None` to `process_audio` (after `preset`) and extend `_validate` per contracts/python-api.md, before any decoding: exactly one of `mask_path`, `preset`, `style` else `InvalidInputError("pass exactly one of --mask, --preset or --style.")`; `style` not in `SONG_STYLES` → `"unknown style '<x>'. Choose one of: vocal-dropout, reverse, dip."`; `dip_db is not None and dip_db <= 0` → `f"--dip-db must be greater than 0, got {dip_db}."`; `dip_db` given with `mask_path`, `preset` or `style == "reverse"` → `"--dip-db only applies to --style dip (or vocal-dropout on mono files)."`. In the masking step, when `style` is set call `apply_styles(audio.samples, audio.sample_rate, spans, applied_style, dip_db)` instead of `apply_masks(...)`, build the report with `to_report(spans, sr, style=applied_style, requested_style=...)`, and return `ProcessResult(..., notes=notes)`. For now `applied_style = style`, `requested_style = None`, `notes = ()` (US1 adds the fallback). The preset/custom path must stay exactly as it is
- [X] T007 In `src/bleeper/core/__init__.py`, export `SONG_STYLES` and add it to `__all__` (keep the list sorted as today)
- [X] T008 [P] Add `tests/unit/test_song_styles.py` with foundational tests: `crossfade_edges` returns `original` at index 0 and the last index, `processed` in the middle, and for a span shorter than 20 ms uses half the span; `apply_styles` with no spans returns an array equal to the input with the same dtype; `apply_style(..., "karaoke")` raises `InvalidInputError`
- [X] T009 [P] Extend `tests/unit/test_report.py`: `ReportEntry("x", 1.0, 2.0).to_dict() == {"word": "x", "start": 1.0, "end": 2.0}` (no new keys); with `style="dip", requested_style="vocal-dropout"` both keys appear; `to_report(..., style="reverse")` sets `style` on every entry
- [X] T010 Extend `tests/integration/test_pipeline.py` with validation tests (fake transcriber, no model): `style` with `preset` or `mask_path` → `InvalidInputError` mentioning `--style`; unknown style; `dip_db=0` and `dip_db=-3`; `dip_db=10` with `preset="beep"` and with `style="reverse"` → `InvalidInputError`. Confirm all pre-existing pipeline tests still pass

**Checkpoint**: `pytest` and ruff green; `process_audio(..., style=...)` is accepted and validated.

---

## Phase 3: User Story 1 - Remove the sung word while the music keeps playing (Priority: P1) 🎯 MVP

**Goal**: `vocal-dropout` removes the centered voice inside each span while bass, kick and wide
instruments keep playing; mono / dual-mono files fall back to `dip` and say so.

**Independent Test**: `process_audio(song_file, words, out, style="vocal-dropout", transcriber=fake)`
with one fake word in the middle: inside the span the 1000 Hz center tone is ≥ 30 dB lower, the
60 Hz center tone and the 440/660 Hz side tones are within 1 dB; outside the span the samples are
bit-identical; rate, channels and duration unchanged; report entry has `"style": "vocal-dropout"`.

### Tests for User Story 1

- [X] T011 [P] [US1] In `tests/unit/test_song_styles.py`, add `vocal-dropout` tests on `make_song()` (use FFT magnitude at each test frequency over the span interior, excluding the 10 ms edges): 1000 Hz centered component attenuated ≥ 30 dB; 60 Hz centered component within 1 dB; 440 Hz (L) and 660 Hz (R) within 1 dB; output shape and dtype equal the input's
- [X] T012 [P] [US1] In `tests/unit/test_song_styles.py`, add `has_usable_stereo` tests: 1-channel array → `False`; identical L/R → `False`; L/R differing only by noise at −70 dB relative to the signal → `False`; `make_song()` → `True`
- [X] T013 [P] [US1] In `tests/unit/test_song_styles.py`, add an edge test for SC-005: for each span boundary, the absolute sample step `|out[i] - out[i-1]|` across the boundary and within the 10 ms crossfade is ≤ 1.5 × the largest step in the original audio over the same region
- [X] T014 [US1] In `tests/integration/test_pipeline.py`, add the Independent Test above using the `song_file` fixture and a `FakeTranscriber` returning one word at 0.9–1.1 s; plus a fallback test: a mono WAV (and a dual-mono stereo WAV) with `style="vocal-dropout"` yields span interior ≈ 0 (default dip = mute), report entry `{"style": "dip", "requested_style": "vocal-dropout"}`, and `result.notes == ("vocal-dropout needs stereo audio; this file is mono, so dip was used instead.",)`; plus a stereo run with `style="vocal-dropout", dip_db=20` that applies vocal dropout (not dip) and returns `result.notes == ("--dip-db was ignored: this file is stereo, so vocal-dropout was applied.",)`

### Implementation for User Story 1

- [X] T015 [US1] In `src/bleeper/core/song_styles.py`, implement `_low_band(mid, sample_rate) -> np.ndarray`: zero-phase FFT filter with `np.fft.rfft`/`irfft` (length preserved via `n=len(mid)`), gain 1 below 100 Hz, 0 above 200 Hz, raised-cosine `0.5 * (1 + cos(pi * (f - 100) / 100))` between (research R2). No SciPy
- [X] T016 [US1] In `src/bleeper/core/song_styles.py`, implement the `"vocal-dropout"` branch of `apply_style` for 2-channel blocks: `mid = (L + R) / 2`, `side = (L - R) / 2`, `low = _low_band(mid, sr)`, return `np.stack([low + side, low - side], axis=1)` (research R1). For more than 2 channels, process channels 0 and 1 this way and leave the others unchanged
- [X] T017 [US1] In `src/bleeper/core/song_styles.py`, implement `has_usable_stereo(samples) -> bool`: `False` if `samples.shape[1] < 2`; otherwise with `x = to_float(samples)`, compute RMS of `(x[:,0] - x[:,1]) / 2` and of `(x[:,0] + x[:,1]) / 2` over the whole file and return `side_rms >= 1e-3 * mid_rms` (and `False` if both are 0) (research R3)
- [X] T018 [US1] In `src/bleeper/core/song_styles.py`, implement the `"dip"` branch of `apply_style` with `gain = 0.0 if dip_db is None else 10 ** (-dip_db / 20)` and `return block * gain` (needed here as the mono fallback; US2 exposes it as a style)
- [X] T019 [US1] In `src/bleeper/core/pipeline.py`, resolve the StylePlan after decoding (data-model.md): if `style == "vocal-dropout"` and not `has_usable_stereo(audio.samples)`, set `applied_style = "dip"`, `requested_style = "vocal-dropout"`, `notes = ("vocal-dropout needs stereo audio; this file is mono, so dip was used instead.",)`; otherwise `applied_style = style`, `requested_style = None`, `notes = ()`; and if `style == "vocal-dropout"`, the file is stereo and `dip_db is not None`, set `notes = ("--dip-db was ignored: this file is stereo, so vocal-dropout was applied.",)`. Pass these through to `apply_styles`, `to_report` and `ProcessResult`
- [X] T020 [US1] Run pytest + ruff; all green, including every pre-existing test

**Checkpoint**: The MVP works through the core API: a broadcast-safe song with the voice removed and
the music kept.

---

## Phase 4: User Story 2 - Choose a classic radio-edit style (Priority: P2)

**Goal**: `reverse` and `dip` (with configurable `dip_db`) are available as styles.

**Independent Test**: Process `song_file` with `style="reverse"`, `style="dip"` and
`style="dip", dip_db=20`; each output transforms only the span (reversed audio / silence / −20 dB),
has smooth edges and adds no foreign sound; the report records the style.

### Tests for User Story 2

- [X] T021 [P] [US2] In `tests/unit/test_song_styles.py`, add `reverse` tests: span interior (excluding 10 ms edges) equals `original[span][::-1]` interior within float tolerance (and exactly after round-trip for float input); shape/dtype preserved
- [X] T022 [P] [US2] In `tests/unit/test_song_styles.py`, add `dip` tests: default (`dip_db=None`) interior is all zeros; `dip_db=20` interior RMS is 20 dB ± 0.1 dB below the original interior RMS; edges ramp over 10 ms
- [X] T023 [US2] In `tests/integration/test_pipeline.py`, add end-to-end runs for `style="reverse"` and `style="dip", dip_db=20` on `song_file` with a fake word: samples outside the span bit-identical, rate/channels/duration preserved, report entries carry `"style"` and no `"requested_style"`

### Implementation for User Story 2

- [X] T024 [US2] In `src/bleeper/core/song_styles.py`, implement the `"reverse"` branch of `apply_style`: `return block[::-1].copy()` (all channels; research R5)
- [X] T025 [US2] Verify the `"dip"` branch from T018 meets FR-005 with the new tests (no code change expected); run pytest + ruff

**Checkpoint**: All three styles work through the core API.

---

## Phase 5: User Story 3 - Use song styles from the web UI and the CLI (Priority: P2)

**Goal**: `--style` / `--dip-db` in the CLI and three "Song:" options with previews in the web UI,
producing identical outputs (contracts/cli.md, contracts/ui.md).

**Independent Test**: For each style, `bleeper song.wav --words w.txt --style <s> -o a.wav` and a UI
worker job with the same inputs produce identical WAV bytes and identical reports; `--style` with
`--preset` exits 1.

### Tests for User Story 3

- [X] T026 [P] [US3] Extend `tests/integration/test_cli.py`: `--style vocal-dropout` succeeds (exit 0) and prints `Masked 1 span.`; `--style reverse --preset beep` exits 1 with an argparse "not allowed with" message; `--style karaoke` exits 1; `--dip-db 0` exits 1; `--style dip --dip-db 20` succeeds; a mono input with `--style vocal-dropout` prints a line starting with `Note: vocal-dropout needs stereo audio`; a stereo input with `--style vocal-dropout --dip-db 20` exits 0 and prints `Note: --dip-db was ignored`. Use the existing fake-transcriber pattern of this file
- [X] T027 [P] [US3] Extend `tests/unit/test_ui_submit.py`: `MASKS` contains `"Song: vocal dropout": "vocal-dropout"`, `"Song: reverse": "reverse"`, `"Song: dip": "dip"` after the three existing entries (order preserved); `create_job(..., preset="Song: reverse", custom_mask=None)` stores `job.mask == "reverse"`
- [X] T028 [P] [US3] In `tests/unit/test_song_styles.py`, add `style_preview` tests: for each style the result is float `(round(seconds * sr), 2)`, finite, peak ≤ 1.0, and differs from the unprocessed synthetic clip only inside the middle second; unknown style raises `InvalidInputError`
- [X] T029 [US3] Extend `tests/integration/test_ui_parity.py`: for each of the three styles, the worker output WAV and report equal the CLI output for the same input/words (follow the existing preset parity test)
- [X] T030 [P] [US3] Extend the UI jobs tests (`tests/unit/test_ui_jobs.py`): `JobStore.finish(..., notes=("n",))` stores `job.notes == ("n",)`; a job loaded from a saved JSON that has no `"notes"` key loads with `notes == ()` (backward compatible)

### Implementation for User Story 3

- [X] T031 [US3] In `src/bleeper/core/song_styles.py`, add `style_preview(style, seconds=2.0, sample_rate=44100) -> np.ndarray`: build the same kind of synthetic stereo clip as research R9 (centered vibrato "voice" 5 Hz vibrato around 600 Hz, centered 60 Hz "bass", 330 Hz L-only and 495 Hz R-only "instruments"), apply `apply_styles` to one span covering the middle second (`Span(n//4, 3*n//4, ("preview",))`), and scale to a 0.5 peak. Export `style_preview` from `src/bleeper/core/__init__.py`
- [X] T032 [US3] In `src/bleeper/cli.py`, import `SONG_STYLES`; add `source.add_argument("--style", choices=SONG_STYLES, help="song-friendly mask: vocal-dropout (remove the voice, keep the music), reverse (play the word backwards) or dip (lower the whole mix)")` to the existing mutually exclusive group, and `parser.add_argument("--dip-db", type=float, metavar="DB", help="attenuation in dB for dip, a number > 0 (default: full mute)")`. Pass `style=args.style, dip_db=args.dip_db` to `process_audio`; after the `Masked N spans.` / no-words line, print `f"Note: {note}"` for each `result.notes`. Exit codes unchanged
- [X] T033 [US3] In `src/bleeper/ui/submit.py`, append `"Song: vocal dropout": "vocal-dropout"`, `"Song: reverse": "reverse"`, `"Song: dip": "dip"` to `MASKS` (after the existing three; dict order is the UI order)
- [X] T034 [US3] In `src/bleeper/ui/jobs.py`, add `notes: tuple[str, ...] = ()` to `Job` (update the `mask` field comment to list the song codes), accept `notes: tuple[str, ...] = ()` in `JobStore.finish(...)` and store it; make loading from persisted JSON tolerate a missing `notes` key and convert a JSON list back to a tuple
- [X] T035 [US3] In `src/bleeper/ui/worker.py`, import `SONG_STYLES`; in `_run`, when `job.mask in SONG_STYLES` call `process_audio(..., style=job.mask, preset=None, mask_path=None)`, otherwise keep today's preset/custom mapping exactly. Pass `notes=result.notes` to `self.store.finish(...)`
- [X] T036 [US3] In `src/bleeper/ui/app.py`: change `preview_values()` to use `preset_preview(code, sample_rate=PREVIEW_RATE)` for codes in `PRESETS` and `style_preview(code, sample_rate=PREVIEW_RATE)` for codes in `SONG_STYLES`; render the previews in two `gr.Row()`s (presets, then song styles) keeping the same `gr.Audio(..., label=f"Preview: {label}", interactive=False, waveform_options=WAVEFORM)` arguments; in `render_details`, when the job is done and `job.notes` is non-empty, append `"\n\n" + "\n".join(job.notes)` to the summary. No other layout or theme change
- [ ] T037 [US3] Run pytest + ruff; then manually run `python -m bleeper.ui`, check the three "Song:" options and their stereo previews, and submit one job per style (quickstart.md §3)

**Checkpoint**: Programmers can use song styles from both interfaces with identical results.

---

## Phase 6: User Story 4 - Recognize lyrics over music (Priority: P3)

**Goal**: Best-effort recognition guidance and an audit-friendly report (no pipeline change, research
R10).

**Independent Test**: The report for a song run lists every masked word with `word`, `start`, `end`
and `style`, and the README explains how to improve recognition on songs.

- [X] T038 [US4] In `README.md`, add a "### Songs and radio edits" subsection under Usage: what each `--style` does (one line each), the `--dip-db` option, the mono fallback note, a JSON report example with `"style"`, and tips for lyrics over loud music (pass `--lang`, try `--model medium`, review the report). Add `--style` and `--dip-db` rows to the options table and change "Exactly one of `--mask` / `--preset` is required" to include `--style`
- [ ] T039 [US4] Optional, model required: add a `@pytest.mark.whisper` test in `tests/whisper/test_real_model.py` that synthesizes nothing new but runs `process_audio(..., style="vocal-dropout")` on the existing whisper fixture to confirm the real-model path accepts styles (skipped in the default run)

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T040 Confirm no new runtime dependency: `git diff main -- pyproject.toml requirements.lock` is empty, and `grep -rn "scipy\|librosa\|demucs\|spleeter" src/` returns nothing (Principle VII)
- [X] T041 Confirm FR-014: the pre-existing preset/custom tests in `tests/` pass unmodified (`git diff main -- tests/` shows only added tests and the `conftest.py` fixtures, no changed assertions)
- [X] T042 Confirm audio logic stays in the core: `tests/unit/test_ui_boundaries.py` passes, and `grep -n "numpy\|np\." src/bleeper/cli.py src/bleeper/ui/submit.py src/bleeper/ui/worker.py src/bleeper/ui/jobs.py` finds no audio processing
- [ ] T043 Final gate: `.venv/bin/ruff format --check && .venv/bin/ruff check && .venv/bin/python -m pytest`, then quickstart.md §2 with a real stereo song for each style and the mono fallback check

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories.
- **US1 (P1)**: needs Phase 2. Adds `vocal-dropout`, stereo detection, the dip math used for the
  fallback, and the StylePlan in the pipeline.
- **US2 (P2)**: needs Phase 2; `dip` reuses T018 from US1 (if US2 is built first, do T018 there).
  Otherwise independent of US1.
- **US3 (P2)**: needs Phase 2; its parity and preview tests cover whichever styles exist, so it is
  fully meaningful after US1 + US2.
- **US4 (P3)**: documentation; best after US3 so the README matches the final CLI.
- **Polish**: after all stories.

### Within Each Story

- Tests first (they should fail), then `song_styles.py`, then `pipeline.py`, then interfaces, then
  run the suite.
- `song_styles.py`, `pipeline.py` and `tests/unit/test_song_styles.py` are shared files: tasks
  touching the same file run sequentially.

### Parallel Opportunities

- Phase 2: T004 (models) and T005 (report) in parallel; T008 and T009 in parallel with each other.
- US1: T011, T012, T013 (append-only tests) in parallel.
- US2: T021, T022 in parallel.
- US3: T026 (CLI tests), T027 (submit tests), T028 (preview tests), T030 (jobs tests) in parallel;
  T032 (CLI) and T033–T034 (UI submit/jobs) touch different files and can proceed in parallel.

## Parallel Example: User Story 3

```text
Task: "T026 [US3] CLI --style tests in tests/integration/test_cli.py"
Task: "T027 [US3] MASKS tests in tests/unit/test_ui_submit.py"
Task: "T028 [US3] style_preview tests in tests/unit/test_song_styles.py"
Task: "T030 [US3] Job.notes tests in tests/unit/test_ui_jobs.py"
```

## Implementation Strategy

### MVP First (User Story 1 only)

1. T001–T002 → T003–T010 → T011–T020.
2. **Stop and validate**: vocal dropout via `process_audio` on a synthetic song and a real stereo
   song; mono fallback works. Already usable from Python.

### Incremental Delivery

1. + US2 (reverse, dip) → validate with unit + pipeline tests.
2. + US3 (CLI + UI + previews) → validate quickstart §2 and §3, parity tests.
3. + US4 (README guidance) → validate the README example matches real output.
4. Polish gates T040–T043.
