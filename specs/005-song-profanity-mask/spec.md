# Feature Specification: Harmonic Profanity Mask for Songs

**Feature Branch**: `005-song-profanity-mask`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description : "Harmonic profanity mask for songs. Some radio stations are forbidden from playing swear words or profane content because minors listen to them. However, bleeps cannot be used inside songs because they would sound strange and unharmonious with the music. The feature must mask profanity in songs in a musically harmonious way (for example, muting or attenuating only the voice during the profane segment while keeping the instrumental, or applying techniques such as reverse/vocal dropout), so the song still sounds natural to the listener and is suitable for radio broadcast."

## Context

Radio stations that are heard by minors are often forbidden from broadcasting profanity. Today
Bleeper replaces each forbidden word with a beep, a tone, noise or a custom sound. That works for
speech (podcasts, interviews), but inside a song a beep clashes with the key, rhythm and texture of
the music and makes the track sound broken. Radio programmers instead want a "radio edit": the
offending word disappears while the beat and the instruments keep playing, so the listener barely
notices the edit.

This feature adds **song-friendly ("harmonic") masking styles** that hide the forbidden word
without introducing any foreign sound into the music.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remove the sung word while the music keeps playing (Priority: P1)

A radio music programmer has an explicit song and a list of forbidden words. They run Bleeper on
the song choosing the **vocal dropout** style. In the output, at each forbidden word the voice
disappears for the duration of the word, but the drums, bass and other instruments continue
without interruption. Outside the masked words, the song is identical to the original.

**Why this priority**: This is the core value of the feature: a broadcast-safe version of a song
that still sounds like music. On its own it already replaces the manual radio-edit work.

**Independent Test**: Process a short song (or a synthetic stereo mix of a centered "voice" and
wide "instruments") with one forbidden word. Listening to the output, the word is no longer
intelligible, the instrumental bed is still audible during the masked span, no beep or added tone
is present, and the report lists the masked word with its start and end.

**Acceptance Scenarios**:

1. **Given** a stereo song containing a forbidden word and the vocal dropout style, **When** the
   user processes it, **Then** the forbidden word is not intelligible in the output and the
   instrumental accompaniment remains audible during the masked span.
2. **Given** the same song, **When** the output is compared to the input, **Then** every sample
   outside the masked spans is unchanged and the output has the same sample rate, channel count and
   total duration.
3. **Given** a masked span, **When** the user listens to its boundaries, **Then** there is no click,
   pop or abrupt volume jump at the start or end of the span.

---

### User Story 2 - Choose a classic radio-edit style (Priority: P2)

Some stations prefer other well-known radio-edit techniques. The user can choose between several
song-friendly styles:

- **Vocal dropout**: the voice is removed for the word, the music continues (default for songs).
- **Reverse**: the word is played backwards, which keeps the singer's voice and rhythm but makes
  the word unintelligible (a common technique in radio edits).
- **Dip**: the whole mix is smoothly lowered in volume for the word and returns afterwards
  (for tracks where the voice cannot be separated from the music).

**Why this priority**: Different stations and genres have different conventions; offering the
standard techniques lets the programmer pick the least noticeable result for each song.

**Independent Test**: Process the same song three times, once per style, and confirm each output
applies the described effect only inside the masked spans and adds no external sound.

**Acceptance Scenarios**:

1. **Given** the reverse style, **When** a song is processed, **Then** each masked span contains the
   original audio of that span played backwards, with smooth edges.
2. **Given** the dip style, **When** a song is processed, **Then** the volume inside each masked span
   is reduced by a configurable amount (default: to silence for the word) and fades back smoothly.
3. **Given** any song style, **When** the job finishes, **Then** the report states which style was
   used.

---

### User Story 3 - Use song styles from the web UI and the CLI (Priority: P2)

The user can pick a song style from the CLI and from the web UI, the same way they pick a beep
preset today. Both interfaces produce identical output for identical inputs.

**Why this priority**: Programmers use the web UI day to day; scripts and batch work use the CLI.
Parity is a project rule.

**Independent Test**: Process the same file with the same words and style from the CLI and from the
UI and compare the outputs; they are identical, and both reports match.

**Acceptance Scenarios**:

1. **Given** the CLI, **When** the user runs it with a song style instead of a mask preset or custom
   mask, **Then** the run succeeds and writes the masked song and the report.
2. **Given** the web UI, **When** the user selects a song style in the mask selector, **Then** the
   job runs in the background and the result is identical to the CLI result.
3. **Given** the CLI, **When** the user passes both a song style and a mask sound, **Then** the
   command fails with a clear message explaining that only one mask option may be chosen.

---

### User Story 4 - Recognize lyrics over music (Priority: P3)

Sung lyrics over loud instruments are harder to recognize than speech. When the user processes a
song, Bleeper should still find the forbidden words reliably enough to be useful for broadcast
review, and the report should make it easy to double-check what was masked.

**Why this priority**: Masking quality only matters if the words are found. However, the user can
already review the report and re-run with adjusted settings, so this is an improvement rather than
a blocker.

**Independent Test**: Process a set of reference songs with known profanity timestamps and measure
how many of the known words were masked.

**Acceptance Scenarios**:

1. **Given** a song with known forbidden words, **When** it is processed, **Then** the report lists
   every masked word with its start and end so the programmer can audit the result.

---

### Edge Cases

- **Mono song**: vocal dropout cannot separate the voice from the instruments in a mono file; the
  system MUST fall back to the dip style for that file and say so in the report and output message.
- **Voice not centered / heavy stereo effects**: vocal dropout may leave part of the voice audible;
  the user can switch to reverse or dip. The report notes the style used per span.
- **Very short word** (shorter than the fade lengths): the span is still masked; fades are shortened
  so the effect covers the whole word.
- **Adjacent or overlapping forbidden words**: spans are merged and masked as one continuous span,
  as today.
- **Forbidden word at the very start or end of the song**: spans are clamped to the file bounds.
- **No forbidden words found**: the output is identical to the input and the report says zero spans
  were masked.
- **Speech file processed with a song style**: allowed; the styles behave the same way.
- **Song with no stereo difference between channels (dual mono)**: treated like a mono song.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST offer song-friendly masking styles — at minimum *vocal dropout*,
  *reverse* and *dip* — as an alternative to the existing beep/tone/noise presets and custom mask
  sound.
- **FR-002**: Song styles MUST NOT insert any sound that is not already present in the original
  recording (no beeps, tones, noise or external clips).
- **FR-003**: *Vocal dropout* MUST remove or strongly attenuate the lead voice inside each masked
  span while keeping the instrumental accompaniment audible in that span.
- **FR-004**: *Reverse* MUST replace each masked span with the original audio of that same span
  played backwards.
- **FR-005**: *Dip* MUST lower the level of the full mix inside each masked span by a configurable
  amount (default: full mute) with smooth transitions.
- **FR-006**: Every song style MUST apply smooth transitions at both edges of each span so no click
  or pop is introduced (at least the existing 10 ms fade in and fade out).
- **FR-007**: All existing correctness rules MUST still hold: word normalization, whole-word
  matching, configurable padding (default 80 ms), span clamping and merging, unchanged samples
  outside masked spans, same sample rate, channel count and duration, and the input file is never
  overwritten.
- **FR-008**: When *vocal dropout* is selected for a file that has no usable stereo information
  (mono or dual mono), the system MUST automatically use *dip* for that file and report the
  fallback clearly to the user.
- **FR-009**: The user MUST choose exactly one mask option per run: a preset, a custom mask sound,
  or a song style. Choosing more than one MUST fail with an actionable error.
- **FR-010**: The CLI and the web UI MUST both expose the song styles, and for the same inputs MUST
  produce identical audio and identical reports.
- **FR-011**: The JSON report MUST include, in addition to each masked word with `word`, `start` and
  `end`, the masking style applied (and any fallback that occurred).
- **FR-012**: The web UI MUST let the user preview each song style before running a job, as it
  does for the existing presets (e.g. on a short built-in demo clip generated in code).
- **FR-013**: Vocal isolation for *vocal dropout* MUST work offline on CPU, with no audio sent to
  any third party, and MUST use only the stereo image of the existing mix (removing the content
  common to both channels, where the lead voice is usually placed). It MUST NOT add any new
  runtime dependency. A dedicated voice/instrument separation component is deferred to a future
  feature.
- **FR-014**: The existing beep/tone/noise presets and custom mask behavior MUST remain unchanged.

### Key Entities

- **Masking style**: The way a masked span is hidden. Either a sound-replacement mask (existing
  presets or custom sound) or a song style (vocal dropout, reverse, dip). Has a name and, for dip,
  an attenuation amount.
- **Masked span**: A time range in the song (start, end, matched word(s)) plus the style actually
  applied, including any fallback.
- **Report**: The per-run JSON document listing masked spans, the chosen style and any fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a listening test, at least 90% of masked forbidden words are judged
  unintelligible by reviewers.
- **SC-002**: In a listening test, at least 80% of reviewers rate songs masked with vocal dropout or
  reverse as "sounds natural / acceptable for broadcast", compared with the beep preset on the same
  songs.
- **SC-003**: For vocal dropout on stereo songs, the instrumental accompaniment remains audible
  during 100% of masked spans (no full-silence gaps), verified on synthetic test mixes.
- **SC-004**: 100% of samples outside masked spans are identical to the decoded input, and output
  duration, sample rate and channel count always match the input.
- **SC-005**: No audible clicks are introduced at span edges in any style (verified by checking
  there is no sample discontinuity larger than the surrounding signal at span boundaries).
- **SC-006**: A programmer can produce a broadcast-safe version of a 4-minute song in under
  5 minutes end to end on a typical laptop CPU.

## Assumptions

- Primary users are radio music programmers and editors preparing broadcast versions of songs; the
  final decision about what is broadcast-safe remains theirs (they review the report).
- The list of forbidden words is provided by the user, as today; the feature does not ship a
  built-in profanity dictionary.
- Most commercial songs are stereo with the lead voice mixed in the center, which makes vocal
  dropout effective on the majority of tracks; dip and reverse cover the rest.
- The input formats, output format (WAV) and report location stay the same as existing features.
- Lyric recognition uses the existing transcription; improving recognition specifically for songs
  is best-effort in this feature (User Story 4), not a guarantee.
- Real-time / live-broadcast processing remains out of scope (constitution); this is a file-based,
  offline workflow.
- The feature should fit the project's ~2-hour-per-feature budget; if not, the P3 story and the UI
  preview (FR-012) are the first items to cut.

## Out of Scope / Future Work

- **Dedicated voice/instrument separation** for higher-quality vocal dropout (including songs whose
  voice is not centered). It needs a new runtime dependency and therefore a constitution amendment
  (Principle VII), and it likely exceeds the 2-hour budget. It will be specified as a separate
  future feature.

## Clarifications

### Session 2026-11-26

- Q: How should vocal dropout isolate the voice? → A: Use only the stereo image of the existing mix
  now (no new dependency); defer a dedicated separation component to a future feature.
- Q: What happens when a dip amount is given with vocal dropout on a stereo song? → A: The amount is
  ignored and the user is told so in a note (it is only used if the file falls back to dip).
- Q: How do song styles meet the 10 ms fade rule? → A: Constitution amended to 1.0.1: in-place
  transformations use a 10 ms crossfade with the original audio.
