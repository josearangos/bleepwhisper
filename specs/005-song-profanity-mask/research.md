# Research: Harmonic Profanity Mask for Songs

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-11-26

All decisions below use only the existing runtime dependencies (numpy, soundfile, ffmpeg,
faster-whisper, Gradio for the UI). No `NEEDS CLARIFICATION` items remain.

## R1. Vocal dropout without a separation model

- **Decision**: Mid/side processing on the span. For stereo `L`, `R`: `mid = (L + R) / 2`,
  `side = (L - R) / 2`. Remove the mid component **above a low crossover** and keep the side
  component untouched: `L' = low(mid) + side`, `R' = low(mid) - side`.
- **Rationale**: Commercial mixes place the lead voice (and its intelligible consonants and vowels)
  in the center, so removing the mid kills the word while wide elements (guitars, keys, pads,
  stereo reverb, overheads) keep playing. Kick and bass are also centered; keeping the mid below the
  crossover preserves the groove and avoids an obvious "hole" in the low end, which satisfies
  SC-003 (accompaniment audible during the span). Pure numpy; trivial cost per span.
- **Alternatives considered**:
  - *Plain side-only ("karaoke") signal*: also removes bass and kick → the edit is very noticeable.
  - *Dedicated source-separation model*: best quality but a heavy new dependency; deferred to a
    future feature (spec Clarifications, constitution Principle VII).
  - *Spectral masking of vocal frequency band (200 Hz–4 kHz) on the full mix*: also removes most
    instruments in that band; sounds like a muffled dip rather than a vocal dropout.

## R2. Low crossover filter

- **Decision**: Zero-phase FFT filter on the span's mid signal: gain 1 below 100 Hz, 0 above
  200 Hz, raised-cosine transition in between. The span is extended by the 10 ms edge regions
  already covered by the crossfade (R4), so filter edge effects fall inside the crossfade.
- **Rationale**: numpy `rfft`/`irfft` only, no SciPy (not an allowed dependency). Zero phase keeps
  the kept low band time-aligned with the untouched audio around the span, so the crossfade does not
  comb-filter. The smooth transition limits ringing compared to a brick-wall cut.
- **Alternatives considered**: IIR biquad written by hand (phase shift at crossover makes the
  crossfade audible); SciPy filters (new dependency).

## R3. Detecting "no usable stereo" (FR-008)

- **Decision**: Decide once per file from the decoded samples: the file is treated as mono when it
  has 1 channel, or when the RMS of `side` over the whole file is below `1e-3 ×` the RMS of `mid`
  (−60 dB; covers exact dual-mono and near-identical channels from mp3 joint stereo). In that case
  every span uses `dip`, and the result records the fallback.
- **Rationale**: Per-file decision matches the spec ("for that file") and keeps the report simple;
  −60 dB is well below any intentional stereo width but above codec noise.
- **Alternatives considered**: Per-span decision (inconsistent sound inside one song); exact
  equality check only (misses mp3 joint-stereo files whose channels differ by rounding noise).

## R4. Smooth edges for song styles (FR-006, Principle III)

- **Decision**: Song styles **crossfade** between the original audio and the processed audio over
  the first and last 10 ms of each span (linear, half the span when shorter than 20 ms — same rule as
  the existing `fade`). For `dip`, this is exactly a 10 ms gain ramp.
- **Rationale**: The existing presets fade a *replacement* sound in and out; song styles transform
  the music in place, so fading to silence would create two audible dropouts per word. A crossfade
  is the equivalent "10 ms fade in and fade out" of the processed signal and removes clicks. Level
  matching (`match_level`) does not apply: the processed audio is derived from the span itself.
- **Alternatives considered**: Reusing `fade` (fades the music to zero at both edges → audible
  gaps); equal-power crossfade (the two signals are highly correlated, so linear is correct).

## R5. Reverse style

- **Decision**: Replace each span (all channels) with the same samples in reverse order, then apply
  the R4 crossfade.
- **Rationale**: Standard radio-edit technique; keeps the singer's timbre, pitch and level, which is
  why it sounds musical. The crossfade hides the discontinuity created at both edges.
- **Alternatives considered**: Reversing only the mid (vocal) part — more complex, marginal gain.

## R6. Dip style and its amount

- **Decision**: Multiply the span by a constant gain derived from an attenuation in dB. Default is
  full mute; `dip_db` (positive number, e.g. `20`) is configurable in the core API and the CLI
  (`--dip-db`). The UI uses the default only.
- **Rationale**: Spec FR-005 requires a configurable amount with mute as default. Keeping the UI
  free of a new control preserves its layout; parity holds because the UI passes the same default.
- **Alternatives considered**: UI slider (extra control, out of the 2-hour budget).

## R7. Choosing a style: API and CLI surface (FR-009, FR-010)

- **Decision**: `process_audio(..., style: str | None = None, dip_db: float | None = None)`; exactly
  one of `mask_path`, `preset`, `style`. CLI adds `--style {vocal-dropout,reverse,dip}` to the
  existing mutually exclusive group with `--mask`/`--preset`, plus `--dip-db DB` (valid only with
  `--style dip`, or when vocal dropout falls back to dip). The UI's "Mask" radio gains three
  entries.
- **Rationale**: Minimal change to existing call sites; argparse's mutually exclusive group gives
  the FR-009 error for free (exit 1).
- **Alternatives considered**: Overloading `--preset` with song names (mixes two different
  behaviors — replacement vs. in-place transform — and complicates validation).

## R8. Report format (FR-011, FR-014)

- **Decision**: The report stays a JSON array of entries. When a song style is used, each entry
  gains `"style"` (the style actually applied) and, if a fallback happened, `"requested_style"`.
  Preset and custom-mask runs produce exactly the same report as today.
- **Rationale**: Backward compatible for existing consumers and tests (FR-014); the per-entry style
  makes each span self-describing.
- **Alternatives considered**: Wrapping the array in an object with metadata (breaking change).

## R9. Previewing song styles in the UI (FR-012)

- **Decision**: `style_preview(style, seconds=2.0, sample_rate=...)` in the core builds a synthetic
  stereo "song" in code — a centered vibrato tone as the "voice", a centered low tone as the "bass",
  and left/right-panned chord tones as "instruments" — and applies the style to its middle second.
- **Rationale**: Lets users hear the difference between styles with no bundled audio (Principle
  IV). Uses the same style functions as the pipeline.
- **Alternatives considered**: Bundling a real music clip (licensing risk; constitution forbids).

## R10. Recognizing lyrics over music (User Story 4)

- **Decision**: No pipeline change in this feature. The quickstart recommends `--lang` (skips
  language detection on instrumental intros) and a larger `--model` for difficult songs; the report
  remains the audit tool.
- **Rationale**: Spec marks this as best effort; improving recognition reliably would need vocal
  separation (deferred). Keeps the feature inside the 2-hour budget.
- **Alternatives considered**: Transcribing the mid channel only (cheap, but untested gain and it
  changes transcription behavior for speech files; can be revisited with measurements).
