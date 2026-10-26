<!--
Sync Impact Report
==================
Version change: (unversioned template) → 1.0.0
Bump rationale: Initial ratification; all placeholders replaced with project-specific content.

Modified principles (template slot → new title):
- [PRINCIPLE_1_NAME] → I. Core-First Architecture
- [PRINCIPLE_2_NAME] → II. Offline, CPU-Only, Private
- [PRINCIPLE_3_NAME] → III. Audio Correctness (NON-NEGOTIABLE)
- [PRINCIPLE_4_NAME] → IV. Code Quality
- [PRINCIPLE_5_NAME] → V. Testing
- (added)            → VI. User Experience
- (added)            → VII. Simplicity & Scope

Added sections:
- Technology & Scope Constraints (was [SECTION_2_NAME])
- Delivery Order & Quality Gates (was [SECTION_3_NAME])

Removed sections: none

Templates requiring updates: none (dependent templates read the constitution at runtime).

Follow-up TODOs: none.
-->

# Bleeper Constitution

Bleeper is a Python tool that masks forbidden words in audio files using faster-whisper. It is
delivered as a reusable core package with two thin interfaces: a CLI, then a Gradio web UI.

## Core Principles

### I. Core-First Architecture

- All audio logic (transcription, matching, masking, reporting, pipeline orchestration) MUST live
  in a reusable core package exposed as a Python API.
- The core pipeline API MUST accept a progress callback so any interface can report progress.
- The CLI and the Gradio UI MUST be thin layers over the core: argument/input parsing, calling the
  core, and presenting results. Interfaces MUST NOT duplicate or reimplement audio logic.
- Given the same inputs and options, the CLI and the UI MUST produce identical masked audio and
  identical reports.

**Rationale**: A single source of truth for audio behavior keeps both interfaces consistent,
testable, and cheap to build.

### II. Offline, CPU-Only, Private

- After the Whisper model has been downloaded, the tool MUST make no network calls.
- Inference MUST run on CPU; no GPU is required or assumed.
- Audio MUST NOT be uploaded to third parties, and audio content or transcripts MUST NOT be
  written to logs.
- Temporary files MUST be deleted after use, including on error paths.
- The default Whisper model MUST be `small`; users MUST be able to override it.

**Rationale**: Users process potentially sensitive recordings; privacy and offline operation are
core guarantees, not features.

### III. Audio Correctness (NON-NEGOTIABLE)

- Words MUST be compared after normalization: lowercase, accents removed, punctuation removed.
- Only whole-word matches count; substrings inside other words MUST NOT match.
- Each match MUST be padded on both sides by a configurable amount (default 80 ms), clamped to the
  audio bounds, and overlapping or touching spans MUST be merged.
- The mask MUST be fitted to the exact span duration (trimmed if longer, looped if shorter) and
  MUST apply a 10 ms fade in and fade out.
- Output MUST preserve the input's sample rate, channel count, and total duration.
- Samples outside masked spans MUST remain bit-for-bit unchanged relative to the decoded input.
- The input file MUST NEVER be overwritten; output is always written to a separate path.

**Rationale**: The tool's value depends on precise, predictable edits that never damage the
surrounding audio or the user's original file.

### IV. Code Quality

- Code MUST target Python 3.10+ and be fully type-hinted.
- Code MUST be formatted and linted with ruff, with zero outstanding lint errors.
- Modules MUST be small and single-purpose. Dead code and unused dependencies MUST NOT be merged.
- Built-in mask presets (beep, low tone, noise burst) MUST be generated in code. Third-party or
  copyrighted audio MUST NOT be bundled.

**Rationale**: A small, clean codebase stays within the time budget and avoids licensing risk.

### V. Testing

- Every module MUST have pytest tests.
- Matching and masking MUST be pure functions with unit tests that run without loading a Whisper
  model.
- Test fixtures MUST be short synthetic audio generated in code or kept tiny; large audio files
  MUST NOT be committed.
- Tests that require a Whisper model MUST be marked (e.g. `@pytest.mark.whisper`) and MUST be
  optional, so the default test run passes offline without the model.

**Rationale**: Fast, model-free tests make the correctness rules in Principle III verifiable on
every change.

### VI. User Experience

- CLI: a single command with clear flags and a helpful `--help`. Exit codes MUST be: `0` success,
  `1` invalid input, `2` processing error.
- UI: long-running work MUST NOT block the interface; jobs MUST run in the background with clearly
  visible status.
- Errors MUST be readable and actionable (what went wrong and how to fix it). The tool MUST NEVER
  fail silently.
- Every successful run MUST produce the masked audio file plus a JSON report listing each masked
  word with its `word`, `start`, and `end` (seconds).

**Rationale**: Predictable outputs and clear failures make the tool usable without reading the
source.

### VII. Simplicity & Scope

- Each feature MUST be buildable in about 2 hours; designs exceeding this MUST be cut down.
- Runtime dependencies are limited to faster-whisper, numpy, soundfile and/or pydub, ffmpeg, and
  Gradio (UI feature only). Any other dependency requires a constitution amendment.
- Out of scope: authentication, databases, cloud deployment, video editing, real-time streaming.

**Rationale**: A strict scope keeps the project shippable and the dependency surface small.

## Technology & Scope Constraints

- **Language**: Python 3.10+.
- **Transcription**: faster-whisper with word-level timestamps, CPU inference, default model
  `small`.
- **Audio I/O**: numpy, soundfile and/or pydub, with ffmpeg for decoding/encoding.
- **UI**: Gradio, used only by the UI feature and not imported by the core or CLI.
- **Tooling**: ruff (format + lint), pytest.
- **Outputs**: masked audio file (never the input path) + JSON report.

## Delivery Order & Quality Gates

Delivery order:

1. **Feature 1**: Core package + CLI.
2. **Feature 2**: Gradio UI reusing the core package unchanged in behavior.

Quality gates for every feature:

- `ruff format --check` and `ruff check` pass.
- Default `pytest` run passes without network access or a Whisper model.
- No audio logic exists outside the core package.
- Masked output preserves sample rate, channels, and duration, verified by tests.
- Feature plans include a Constitution Check confirming compliance with Principles I–VII.

## Governance

- This constitution takes precedence over feature specs, plans, and tasks. Where they conflict,
  the constitution wins until amended.
- Amendments MUST be documented in this file with a justification, an updated version, and an
  updated Last Amended date.
- Versioning follows semantic versioning:
  - MAJOR: removal or backward-incompatible redefinition of a principle or governance rule.
  - MINOR: a new principle or section, or materially expanded guidance.
  - PATCH: clarifications, wording, and typo fixes.
- Every spec, plan, and review MUST verify compliance with these principles. Any deviation MUST be
  justified explicitly in the plan's complexity tracking, or the constitution amended first.

**Version**: 1.0.0 | **Ratified**: 2026-10-26 | **Last Amended**: 2026-10-26
