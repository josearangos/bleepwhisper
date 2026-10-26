# Feature Specification: Bleeper CLI — Mask Forbidden Words in Audio

**Feature Branch**: `001-cli-word-masking`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Build "bleeper", a Python CLI that masks forbidden words in an audio
file. A content creator gives bleeper an audio file, a text file of forbidden words and a mask
sound, and gets the same audio back with every forbidden word replaced by the mask. Usage:
`bleeper input.wav --words words.txt (--mask mask.wav | --preset beep|tone|noise) -o output.wav
[--model small] [--lang es] [--padding 80] [--report report.json]`. Expose a reusable
`bleeper.core.process_audio(...)` API with a progress callback for a future UI."

## Clarifications

### Session 2026-10-26

- Q: How loud should the mask sound be inside each masked span? → A: Match the RMS of up to
  500 ms of audio on each side of the span; use about -20 dBFS if that audio is silent; never clip.
- Q: Should report `start`/`end` be the masked span or the original word times? → A: The padded,
  merged, clamped span exactly as masked; one entry per masked span.
- Q: If the output or report file already exists, replace it or refuse? → A: Replace silently;
  the input file is always protected.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bleep forbidden words with a built-in preset (Priority: P1)

A content creator has a recording and a list of words that must not be heard. They run one command
naming the recording, the words file, a built-in mask preset (beep, low tone or noise burst) and an
output path. They receive a new audio file where each forbidden word is covered by the mask, plus a
report of what was masked and when. The original recording is untouched.

**Why this priority**: This is the core value of the product; without it nothing else matters. It
needs no custom mask file, so it is the smallest usable slice.

**Independent Test**: Run the command on a short recording containing a known forbidden word with
`--preset beep`, then confirm the output contains a beep over that word, is identical elsewhere,
has the same length, and the report lists the word with its time range.

**Acceptance Scenarios**:

1. **Given** a synthetic recording where a forbidden word is recognized at 2.0–2.5 s and padding of
   80 ms, **When** the user runs bleeper with a preset, **Then** the output differs from the input
   only within 1.92–2.58 s, has the same duration, sample rate and channel count, and the exit code
   is 0.
2. **Given** a recording in which no listed word is spoken, **When** the user runs bleeper,
   **Then** the output audio is sample-identical to the (decoded) input, the report is an empty
   list, a "no forbidden words found" message is shown, and the exit code is 0.
3. **Given** a words file containing "Señor" and a recording where "senor," is spoken, **When** the
   user runs bleeper, **Then** the word is masked (normalized match ignores case, accents and
   punctuation).
4. **Given** a words file containing "ass" and a recording where only "class" is spoken, **When**
   the user runs bleeper, **Then** nothing is masked (whole-word matches only).
5. **Given** a successful run, **When** the user inspects the input file, **Then** its content and
   modification time are unchanged.

---

### User Story 2 - Use a custom mask sound (Priority: P2)

The creator wants their own signature sound (e.g., a quack) instead of a preset. They pass
`--mask mask.wav`; each masked span is filled with that sound, fitted exactly to the span length.

**Why this priority**: Adds personalization on top of the working core; not required for the MVP.

**Independent Test**: Run bleeper with a mask shorter than the span and with a mask longer than the
span; confirm the masked region has exactly the span's length in both cases, the short mask
repeats, and the long mask is cut off.

**Acceptance Scenarios**:

1. **Given** a 200 ms custom mask and a 660 ms masked span, **When** the user runs bleeper,
   **Then** the mask is looped to fill exactly 660 ms, with a 10 ms fade in and fade out.
2. **Given** a 2 s custom mask and a 660 ms masked span, **When** the user runs bleeper, **Then**
   the mask is trimmed to exactly 660 ms, with a 10 ms fade in and fade out.
3. **Given** a mask whose sample rate or channel count differs from the input, **When** the user
   runs bleeper, **Then** the mask is converted to match the input and the output still keeps the
   input's format and duration.

---

### User Story 3 - Clear errors and tunable options (Priority: P2)

The creator makes mistakes (wrong path, empty words file, both mask options) or wants to tune
behavior (language, model size, padding, report location). bleeper explains what went wrong and how
to fix it, and exits with a meaningful code so scripts can react.

**Why this priority**: Required for a trustworthy CLI and for scripting, but builds on Story 1.

**Independent Test**: Run bleeper with each invalid input listed below and confirm the exit code and
message; run with `--lang`, `--model`, `--padding` and `--report` and confirm they take effect.

**Acceptance Scenarios**:

1. **Given** a missing words file, **When** the user runs bleeper, **Then** it exits with code 1
   and a message naming the missing file.
2. **Given** a words file that is empty or contains only blank lines and `#` comments, **When** the
   user runs bleeper, **Then** it exits with code 1 and a message saying no forbidden words were
   found in the file.
3. **Given** both `--mask` and `--preset`, or neither, **When** the user runs bleeper, **Then** it
   exits with code 1 and explains that exactly one must be given.
4. **Given** an output path equal to the input path, **When** the user runs bleeper, **Then** it
   exits with code 1 and refuses to overwrite the input.
5. **Given** `--padding 0`, **When** a word is matched at 2.0–2.5 s, **Then** only 2.0–2.5 s is
   masked.
6. **Given** a failure during transcription or writing output (e.g., the speech model cannot be
   loaded, the output directory is not writable), **When** the user runs bleeper, **Then** it exits
   with code 2 and an actionable message, and leaves no partial output or temporary files behind.
7. **Given** `bleeper --help`, **Then** every option, its default and the exit codes are described.

---

### User Story 4 - Reusable processing API with progress (Priority: P3)

A developer (and later the web UI) calls `bleeper.core.process_audio(...)` directly with the same
options as the CLI, receives the output path and the report, and gets progress updates through a
callback.

**Why this priority**: Enables Feature 2 (UI) without duplicating logic; the CLI already exercises
it internally.

**Independent Test**: Call the API with a progress callback on a short recording; confirm the
callback receives increasing progress values ending at completion, and that the returned output and
report are identical to what the CLI produces for the same inputs.

**Acceptance Scenarios**:

1. **Given** the same inputs and options, **When** processed via the CLI and via the API, **Then**
   both produce identical audio and identical reports.
2. **Given** a progress callback, **When** processing runs, **Then** the callback is invoked with a
   stage name and a fraction from 0.0 to 1.0 that never decreases and ends at 1.0 on success.
3. **Given** invalid input, **When** calling the API, **Then** it raises a distinct "invalid input"
   error; processing failures raise a distinct "processing" error (these map to exit codes 1 and 2).

---

### Edge Cases

- Forbidden word at the very start or end of the audio: padded span is clamped to the audio bounds;
  duration is unchanged.
- Two matches whose padded spans overlap or touch: merged into one span, reported once with the
  words joined by a space.
- Multi-word phrase in the words file (e.g., "shut up"): matches only when those words appear
  consecutively in the transcript; the span runs from the first word's start to the last word's end.
- Same word repeated many times: every occurrence is masked and reported.
- Words file lines with surrounding whitespace or duplicates: whitespace is trimmed; duplicates are
  harmless.
- A words-file line that is empty after normalization (e.g., only punctuation): ignored; if no
  usable entries remain the run fails with exit code 1.
- Surrounding audio is silent: mask is played at a fixed default level rather than inaudibly.
- Masking must never clip: the masked region is limited to the valid sample range.
- Unsupported or corrupt input file, or an mp3 when the audio decoder (ffmpeg) is unavailable:
  exit code 1 with a message naming the problem and how to fix it.
- Very short audio (shorter than the padding): still processed; span clamped to bounds.
- Output or report file already exists (and is not the input): it is replaced silently.
- Words file not valid UTF-8: exit code 1 with a message saying the file must be UTF-8.

## Requirements *(mandatory)*

### Functional Requirements

**Inputs & options**

- **FR-001**: The CLI MUST be a single command: `bleeper INPUT --words FILE (--mask FILE | --preset
  beep|tone|noise) -o OUTPUT [--model NAME] [--lang CODE] [--padding MS] [--report FILE]`.
- **FR-002**: The system MUST accept WAV and MP3 input audio and MUST write WAV output.
- **FR-003**: Exactly one of `--mask` or `--preset` MUST be provided.
- **FR-004**: The words file MUST be read as UTF-8 with one word or phrase per line; blank lines and
  lines starting with `#` (after trimming leading whitespace) MUST be ignored.
- **FR-005**: `--model` MUST default to `small`; `--lang` MUST be optional, with automatic language
  detection when omitted; `--padding` MUST default to 80 ms and accept any integer ≥ 0.
- **FR-006**: `--report` MUST default to the output path with its extension replaced by `.json`.

**Transcription & matching**

- **FR-007**: The system MUST transcribe the input with word-level timestamps, entirely on the
  local machine, with no network access once the speech model is available locally.
- **FR-008**: Words MUST be compared after normalization: lowercase, accents removed, punctuation
  removed.
- **FR-009**: Only whole-word matches count; a forbidden entry MUST NOT match inside a longer word.
  Multi-word entries MUST match consecutive transcribed words.

**Masking**

- **FR-010**: Each matched span MUST be extended by the padding on both sides and clamped to
  [0, audio duration].
- **FR-011**: Overlapping or adjacent padded spans MUST be merged into a single span.
- **FR-012**: Each span MUST be replaced by the mask, looped or trimmed to exactly the span's
  length, with a 10 ms linear fade in and fade out.
- **FR-013**: The mask level MUST be matched to the RMS of the input audio within up to 500 ms on
  each side of the span (excluding the span itself, clamped to the audio bounds). If that audio is
  silent, the mask MUST be played at about -20 dBFS RMS. The masked region MUST NOT clip.
- **FR-014**: The system MUST provide three built-in presets generated at runtime: `beep` (1 kHz
  sine), `tone` (low-frequency sine), and `noise` (noise burst). No audio files may be bundled.
- **FR-015**: Custom masks MUST be converted to the input's sample rate and channel count before
  use.

**Output & integrity**

- **FR-016**: The output MUST keep the input's sample rate, channel count and exact duration (sample
  count).
- **FR-017**: All samples outside merged masked spans MUST be identical to the decoded input.
- **FR-018**: The input file MUST never be modified; an output or report path equal to the input
  path MUST be rejected as invalid input. Existing output and report files (other than the input)
  MUST be replaced without prompting.
- **FR-019**: Every successful run MUST write a JSON report: a list of `{word, start, end}` objects,
  one per merged masked span, ordered by start time. `start`/`end` MUST be the exact boundaries of
  the masked region (padded, merged and clamped — not the original word times), in seconds rounded
  to milliseconds. An empty list is written when there are no matches.
- **FR-020**: Temporary files MUST be removed after the run, whether it succeeds or fails; a failed
  run MUST NOT leave a partial output file.
- **FR-021**: Audio content and transcripts MUST NOT be written to logs or sent anywhere.

**Interface behavior**

- **FR-022**: Exit codes MUST be: `0` success (including no matches, with a message saying so),
  `1` invalid input, `2` processing error.
- **FR-023**: Every error MUST print a readable message to standard error stating what failed and
  how to fix it.
- **FR-024**: On success the CLI MUST print a summary: number of masked spans, output path and
  report path.
- **FR-025**: `--help` MUST describe every option, its default, and the exit codes.

**Reusable API**

- **FR-026**: The system MUST expose `bleeper.core.process_audio(...)` accepting the same options as
  the CLI plus an optional progress callback, and returning the output path and the report.
- **FR-027**: The progress callback MUST receive a stage name and a non-decreasing fraction in
  [0.0, 1.0], reaching 1.0 on success.
- **FR-028**: The API MUST signal invalid input and processing failures as two distinct error kinds,
  which the CLI maps to exit codes 1 and 2.
- **FR-029**: The CLI MUST contain no audio logic of its own; for identical inputs the CLI and API
  MUST produce identical output audio and reports.

### Key Entities

- **Forbidden Word List**: Ordered set of normalized words/phrases loaded from the words file.
- **Transcribed Word**: A recognized word with its text, start time and end time (seconds).
- **Match**: A forbidden entry found in the transcript, with original text and start/end times.
- **Masked Span**: A merged, padded, clamped time range plus the matched word(s) it covers; the unit
  of both masking and reporting.
- **Mask**: The replacement sound — a generated preset or a user-supplied file — fitted per span.
- **Report**: Ordered list of masked spans as `{word, start, end}`, saved as JSON.
- **Progress Update**: A stage name and completion fraction delivered to the caller.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a recording with a known forbidden word at 2.0–2.5 s, 100% of changed samples fall
  within the padded span (1.92–2.58 s at default padding) and output duration equals input duration
  to the sample.
- **SC-002**: For recordings with no matches, output audio is 100% sample-identical to the decoded
  input and the run reports success.
- **SC-003**: Masked regions with custom masks of any length are exactly the span length (0-sample
  difference).
- **SC-004**: Every invalid-input scenario listed in User Story 3 produces exit code 1 and a message
  that names the problem, on the first attempt.
- **SC-005**: A first-time user can mask a file using only `--help` in under 2 minutes.
- **SC-006**: A 1-minute recording is processed in under 1 minute with the default model on the
  reference machine (an Apple M-series laptop with 8 GB RAM), after the model is available locally.
- **SC-007**: After any run, successful or failed, zero temporary files remain and the input file is
  unchanged.
- **SC-008**: CLI and API runs with identical inputs produce identical output and report in 100% of
  test cases.

## Assumptions

- Recognition accuracy (whether a spoken word is detected at all) depends on the speech model; the
  feature guarantees correct masking of what the model recognizes, not perfect recognition.
- The speech model is downloaded once on first use (the only permitted network access); later runs
  work fully offline. A missing model with no connectivity is a processing error (exit 2).
- Acceptance tests for masking use synthetic audio and simulated transcriptions so they run without
  the speech model; tests that need the real model are optional.
- The low `tone` preset is a sine around 400 Hz; the `noise` preset is white noise. All presets are
  shaped by the same 10 ms fades.
- The mask is applied identically to every channel of multi-channel audio.
- Merged spans report their matched words joined by a single space in transcript order.
- WAV output uses the input's sample encoding when the input is WAV; MP3 input is written as 16-bit
  WAV.
- Constitution constraints apply: CPU-only, offline, Python 3.10+, limited dependencies; GUI, web
  server, video, streaming and cloud are out of scope for this feature.
