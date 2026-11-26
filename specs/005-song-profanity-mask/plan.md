# Implementation Plan: Harmonic Profanity Mask for Songs

**Branch**: `005-song-profanity-mask` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-song-profanity-mask/spec.md`

## Summary

Add three song-friendly masking styles — `vocal-dropout`, `reverse` and `dip` — that transform each
masked span of the original recording in place instead of replacing it with a beep. Vocal dropout
uses mid/side processing (remove the center above a ~150 Hz crossover, keep the side and the low
center so bass and kick keep playing), reverse plays the span backwards, and dip lowers the whole mix
(mute by default, `--dip-db` configurable). Every style uses a 10 ms crossfade with the original at
both edges. Mono or dual-mono files fall back from vocal dropout to dip and say so. The logic lives
in a new pure module `bleeper.core.song_styles`; `process_audio` gains `style` and `dip_db`; the CLI
gains `--style`/`--dip-db`; the UI mask selector gains three options with generated previews. The
report adds a `style` field only for song-style runs. No new dependencies. See
[research.md](research.md).

## Technical Context

**Language/Version**: Python ≥ 3.10

**Primary Dependencies**: numpy (FFT filter, mid/side math), soundfile, ffmpeg, faster-whisper,
Gradio (UI only) — all existing; no new dependency

**Storage**: Files only (input audio, words file, output WAV, JSON report)

**Testing**: pytest with synthetic stereo audio generated in code; fake transcriber; whisper-marked
tests stay optional

**Target Platform**: macOS / Linux desktop and the existing Docker image, CPU only

**Project Type**: Single Python package (core library + CLI + Gradio UI)

**Performance Goals**: Style processing adds < 1 s per 4-minute song (one small FFT per span);
end-to-end time dominated by transcription, as today (SC-006)

**Constraints**: Offline; bit-identical samples outside spans; preserve rate/channels/duration;
input never overwritten; existing preset/custom-mask outputs and reports unchanged (FR-014)

**Scale/Scope**: One new core module (~120 lines), small edits to pipeline, report, models, CLI, UI
submit/worker/app/jobs; ~2 h

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Pre-research | Post-design |
|-----------|------|--------------|-------------|
| I. Core-first | Style logic only in `bleeper.core.song_styles`; CLI/UI just pass `style`; parity CLI ↔ UI | ✅ | ✅ [python-api](contracts/python-api.md), [ui](contracts/ui.md) parity rule |
| II. Offline, CPU, private | No network, no model, no logging of audio; numpy only | ✅ | ✅ R1, R2 |
| III. Audio correctness | Matching/padding/merging unchanged; spans exact length; 10 ms edge crossfade for in-place transformations (1.0.1); outside samples identical; format preserved; input never overwritten | ✅ | ✅ R4 |
| IV. Code quality | Typed, ruff-clean, small single-purpose module; no bundled audio (previews generated in code) | ✅ | ✅ R9 |
| V. Testing | Pure functions unit-tested without Whisper; synthetic fixtures | ✅ | ✅ [quickstart](quickstart.md) §1 |
| VI. User experience | Exit codes 0/1/2 kept; clear errors for conflicting options; UI jobs stay in background; report lists word/start/end | ✅ | ✅ [cli](contracts/cli.md), fallback note shown |
| VII. Simplicity & scope | ~2 h; no new dependency; no real-time | ✅ | ✅ separation model deferred (spec Clarifications) |

**Principle III (constitution 1.0.1)**: the constitution was amended on 2026-11-26 so the 10 ms
fade rule applies to replacement mask sounds, and in-place transformations use a 10 ms crossfade
with the original audio. Song styles follow the new rule (R4); `match_level` is not used because
the processed audio is derived from the span itself. No violation remains.

## Project Structure

### Documentation (this feature)

```text
specs/005-song-profanity-mask/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R10 decisions
├── data-model.md        # Phase 1: SongStyle, StylePlan, ReportEntry/ProcessResult/Job extensions
├── quickstart.md        # Phase 1: validation guide
├── contracts/
│   ├── python-api.md    # process_audio(style, dip_db), SONG_STYLES, style_preview
│   ├── cli.md           # --style, --dip-db
│   ├── report.md        # style / requested_style fields
│   └── ui.md            # mask selector, previews, worker mapping
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks) — not created here
```

### Source Code (repository root)

```text
src/bleeper/
├── core/
│   ├── song_styles.py   # NEW: apply_style, crossfade_edges, has_usable_stereo, apply_styles, style_preview
│   ├── pipeline.py      # style/dip_db params, validation, StylePlan resolution, notes
│   ├── models.py        # ReportEntry.style/requested_style, ProcessResult.notes
│   ├── report.py        # to_report(..., style, requested_style)
│   └── __init__.py      # export SONG_STYLES, style_preview
├── cli.py               # --style in the mask group, --dip-db, print notes
└── ui/
    ├── submit.py        # MASKS gains three song entries
    ├── worker.py        # route SONG_STYLES codes to style=; store notes
    ├── jobs.py          # Job.notes; finish(..., notes)
    └── app.py           # previews for song styles; show notes in details

tests/
├── unit/
│   ├── test_song_styles.py      # NEW: dropout/reverse/dip/crossfade/stereo detection/preview
│   ├── test_report.py           # style fields; unchanged preset output
│   └── test_ui_submit.py        # new MASKS entries
└── integration/
    ├── test_pipeline.py         # styles end-to-end, fallback, validation
    ├── test_cli.py              # --style, --dip-db, conflicting options exit 1
    └── test_ui_parity.py        # CLI ↔ UI identical output per style
```

**Structure Decision**: Keep the existing single-package layout. All new audio logic goes into one
new pure core module; interfaces only map options to the new `style` parameter.

## Complexity Tracking

None. The crossfade previously tracked here is now allowed by constitution 1.0.1 (Principle III).
