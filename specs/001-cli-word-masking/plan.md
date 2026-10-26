# Implementation Plan: Bleeper CLI — Mask Forbidden Words in Audio

**Branch**: `001-cli-word-masking` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-cli-word-masking/spec.md`

## Summary

A single `bleeper` command transcribes an audio file locally with faster-whisper (word timestamps,
CPU, default model `small`), finds forbidden words/phrases after normalization (whole tokens only),
pads/clamps/merges them into sample-exact spans, and replaces each span with a level-matched,
faded mask (generated preset or looped/trimmed custom sound). It writes a WAV with the input's exact
format and duration plus a JSON report. All logic lives in `bleeper.core`, exposed as
`process_audio(...)` with a progress callback; the CLI is a thin argparse wrapper mapping
`InvalidInputError`/`ProcessingError` to exit codes 1/2. See [research.md](research.md).

## Technical Context

**Language/Version**: Python ≥ 3.10 (developed on 3.14 via `uv`)

**Primary Dependencies**: faster-whisper (CTranslate2), numpy, soundfile; `ffmpeg` CLI (system
binary) for mp3 decode and mask resampling; dev: pytest, ruff

**Storage**: Files only (input audio, words file, mask, output WAV, JSON report)

**Testing**: pytest; fake transcriber + synthetic audio; `@pytest.mark.whisper` opt-in model tests

**Target Platform**: macOS / Linux desktop, CPU only

**Project Type**: Single Python package (library core + CLI)

**Performance Goals**: 1 min of audio processed in < 1 min on a typical laptop CPU with `small`
(int8) once the model is cached (SC-006); masking itself < 1 s per minute of audio

**Constraints**: Offline after model download; no audio/transcript logging; temp files always
removed; bit-identical samples outside spans; input never modified

**Scale/Scope**: Single file per run, typical recordings up to ~1 h; words lists up to a few
thousand entries; ~10 small modules, buildable in ~2 h

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Pre-research | Post-design |
|-----------|------|--------------|-------------|
| I. Core-first | All audio logic in `bleeper.core`; `process_audio` with progress callback; CLI only parses args, calls core, prints | ✅ | ✅ `cli.py` has no audio code; parity test planned |
| II. Offline, CPU, private | CPU int8; `local_files_only` first; no logging of audio/transcripts; temp dirs cleaned; default `small`, overridable | ✅ | ✅ R5, R9 |
| III. Audio correctness | Normalized whole-word match; 80 ms default padding; merge; exact-length mask with 10 ms fades; preserve rate/channels/duration; untouched samples identical; never overwrite input | ✅ | ✅ R4, R6–R8; path-collision check |
| IV. Code quality | 3.10+, type hints, ruff, small modules, presets generated in code, no bundled audio | ✅ | ✅ pydub dropped as unused |
| V. Testing | pytest per module; pure matching/masking tests without model; synthetic fixtures; whisper tests marked/optional | ✅ | ✅ R11 |
| VI. UX | One command, `--help`, exit codes 0/1/2 (argparse errors remapped to 1); actionable errors; WAV + JSON report every run | ✅ | ✅ contracts/cli.md |
| VII. Simplicity | ~2 h scope; deps ⊆ {faster-whisper, numpy, soundfile, ffmpeg}; no out-of-scope features | ✅ | ✅ only stdlib beyond allowed deps |

**Result**: PASS — no violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-cli-word-masking/
├── plan.md              # This file
├── research.md          # Phase 0 decisions (R1–R11)
├── data-model.md        # Entities, validation, errors, pipeline flow
├── quickstart.md        # Setup and validation scenarios
├── contracts/
│   ├── cli.md           # Command-line contract and exit codes
│   ├── python-api.md    # bleeper.core.process_audio contract
│   └── report-schema.json
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
pyproject.toml               # package metadata, deps, console script, ruff + pytest config
src/bleeper/
├── __init__.py              # __version__
├── cli.py                   # argparse wrapper → core.process_audio; exit-code mapping
└── core/
    ├── __init__.py          # public API re-exports
    ├── errors.py            # BleeperError, InvalidInputError, ProcessingError
    ├── models.py            # TranscribedWord, Match, Span, ReportEntry, ProcessResult
    ├── words.py             # parse/load words file → ForbiddenEntry list
    ├── matching.py          # normalize(), find_matches()          (pure)
    ├── spans.py             # build_spans(): pad, clamp, merge       (pure)
    ├── presets.py           # beep / tone / noise generators         (pure)
    ├── masking.py           # fit, level-match, fade, apply_masks()  (pure)
    ├── audio_io.py          # load_audio, load_mask, ffmpeg, atomic WAV write
    ├── transcribe.py        # Transcriber protocol, WhisperTranscriber
    ├── report.py            # to_report(), atomic JSON write
    └── pipeline.py          # process_audio(): orchestration + progress

tests/
├── conftest.py              # synthetic audio fixtures, FakeTranscriber
├── unit/
│   ├── test_words.py
│   ├── test_matching.py
│   ├── test_spans.py
│   ├── test_presets.py
│   ├── test_masking.py
│   ├── test_report.py
│   ├── test_audio_io.py
│   └── test_transcribe.py   # WhisperTranscriber mapping with a stubbed model
├── integration/
│   ├── test_pipeline.py     # acceptance scenarios via process_audio + FakeTranscriber
│   └── test_cli.py          # exit codes, messages, CLI/API parity
└── whisper/
    └── test_real_model.py   # @pytest.mark.whisper, optional
```

**Structure Decision**: Single package with `src/` layout. `bleeper.core` is the reusable library
that Feature 2 (Gradio UI) will import; `bleeper.cli` is the only interface in this feature.
Pure modules (`matching`, `spans`, `presets`, `masking`) have no I/O and no model dependency.

## Complexity Tracking

No constitution violations to justify.
