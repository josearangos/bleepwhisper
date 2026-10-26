# Phase 0 Research: Bleeper CLI — Mask Forbidden Words in Audio

All Technical Context unknowns are resolved below. Each entry: Decision / Rationale / Alternatives.

## R1. Python version & environment

- **Decision**: Support Python ≥ 3.10 (`requires-python = ">=3.10"`). Develop with `uv` (installed
  locally); local interpreter is 3.14 and `ctranslate2` 4.8.x (faster-whisper's engine) ships
  macOS arm64 wheels for both 3.12 and 3.14.
- **Rationale**: Constitution mandates 3.10+; wheels exist so no compiler toolchain is needed.
- **Alternatives**: Pinning a single minor version — unnecessary restriction.

## R2. Packaging & entry point

- **Decision**: `pyproject.toml` with `src/` layout, setuptools backend, console script
  `bleeper = "bleeper.cli:main"`. Runtime deps: `faster-whisper`, `numpy`, `soundfile`. Dev extras:
  `pytest`, `ruff`.
- **Rationale**: Standard, zero extra runtime deps; `src/` layout prevents tests importing the
  working tree by accident.
- **Alternatives**: pydub (allowed by constitution) — not needed: soundfile + ffmpeg subprocess cover
  all I/O with exact sample control, so pydub would be an unused dependency.

## R3. CLI argument parsing and exit codes

- **Decision**: stdlib `argparse` with a mutually exclusive required group for `--mask`/`--preset`
  and `choices` for presets. Subclass `ArgumentParser` and override `error()` to print the message
  and exit with **1** (argparse's default is 2, which would collide with "processing error").
- **Rationale**: No dependency; `--help` generated with defaults via
  `ArgumentDefaultsHelpFormatter`; exit codes follow the constitution.
- **Alternatives**: click/typer — extra dependency forbidden by Principle VII.

## R4. Audio decoding and sample-exact preservation

- **Decision**:
  - **WAV with PCM or float subtype**: read with `soundfile` in a lossless dtype (`int32` for all PCM
    subtypes, `float32`/`float64` for FLOAT/DOUBLE) and write back with the **same subtype**. Values
    outside masked spans are copied untouched, so they are bit-identical.
  - **MP3 (and WAV with exotic subtypes such as µ-law/ADPCM)**: decode with the `ffmpeg` CLI into a
    temporary 16-bit PCM WAV at the native sample rate and channel count (`-acodec pcm_s16le`, no
    `-ar`/`-ac` change), then treat as PCM_16. Output is PCM_16 WAV.
  - Missing `ffmpeg` when needed → `InvalidInputError` with "install ffmpeg" guidance.
- **Rationale**: Satisfies FR-016/FR-017 exactly; ffmpeg is the constitution's decoder for mp3.
  `soundfile` reads 24-bit PCM left-aligned in int32 and writes it back losslessly.
- **Alternatives**: Read everything as float64 — loses bit-identity for integer PCM after
  re-quantization rounding. soundfile's own MP3 support — spec explicitly names ffmpeg.

## R5. Transcription with faster-whisper

- **Decision**: `WhisperModel(model, device="cpu", compute_type="int8")`;
  `model.transcribe(path, language=lang_or_None, word_timestamps=True)`, iterating the lazy segment
  generator and collecting `segment.words` (`word`, `start`, `end`). Progress = `segment.end /
  info.duration`. Model loading tries `local_files_only=True` first and only falls back to a
  download if the model is not cached. Models are cached per name within the process (helps the
  future UI). The transcriber is passed the decoded path (original WAV or temp WAV for mp3) so
  timestamps align with the samples being masked.
- **Errors**: model load/download failure → `ProcessingError` (exit 2); faster-whisper `ValueError`
  for an unknown language code → `InvalidInputError` (exit 1).
- **Rationale**: int8 on CPU is the fastest CPU setting; `local_files_only` guarantees no network
  after the first download (Principle II). Lazy generator gives natural progress updates.
- **Alternatives**: VAD filter — can drop short words; off by default. openai-whisper — heavier,
  not allowed.
- **Testability**: the pipeline accepts an injectable `Transcriber` (protocol with
  `transcribe(path, language, on_progress) -> Transcription`, where `Transcription` carries the words
  and the requested-or-detected language), so pipeline/CLI tests run with a fake transcriber and no
  model.

## R6. Text normalization & whole-word / phrase matching

- **Decision**: `normalize(text)`: Unicode NFKD → drop combining marks (category `Mn`) → `casefold`
  → delete characters in Unicode categories `P*` (punctuation) and `S*` (symbols) → split on
  whitespace. The same function normalizes words-file entries and transcript words. Each entry
  becomes a token tuple; a transcript word whose normalization is empty is dropped. Matching slides
  each entry's tuple over the transcript token sequence; equality is per whole token, so "ass" never
  matches "class". A phrase match spans first token start → last token end.
- **Rationale**: Deleting (not spacing) punctuation makes "don't"/"dont" and "f-word"/"fword" match
  consistently on both sides. Token equality enforces whole words.
- **Alternatives**: Regex `\b` on the joined transcript — fragile with accents and loses timestamps.
- **Known limitation**: digits vs spelled numbers ("5" vs "five") are not equivalent; documented.

## R7. Spans: padding, clamping, merging

- **Decision**: Work in integer sample indices. `start = round(t_start*sr) - pad`, `end =
  round(t_end*sr) + pad`, `pad = round(padding_ms*sr/1000)`, clamp to `[0, n_samples]`, sort, merge
  when `next.start <= current.end` (overlap or touch). Merged spans keep their words in order,
  joined by one space. Report times = `sample / sr` rounded to 3 decimals.
- **Rationale**: Sample indices make "exact duration" and "identical outside spans" provable in
  tests; report reflects exactly the masked region (clarification Q2).

## R8. Mask fitting, fades, level and clipping

- **Decision**:
  - **Presets** are generated at exactly the span length: `beep` = 1 kHz sine, `tone` = 400 Hz sine,
    `noise` = white noise from `numpy.random.default_rng(seed=0)` (deterministic, so CLI and UI give
    identical output).
  - **Custom mask** is loaded once as mono float64 (multi-channel masks are averaged) at the input's
    sample rate (ffmpeg resample only when rates differ), then looped (`numpy.resize`-style tiling)
    or trimmed to exactly the span length. Every mask (preset or custom) is mono and is broadcast
    to all input channels by `apply_masks`, which satisfies FR-015's channel conversion.
  - **Level**: target RMS = RMS of the **original** input samples within up to 500 ms each side of
    the span (span excluded, clamped, all channels), never of the partly masked working copy, so a
    nearby mask cannot change a later span's level. If target RMS < 1e-4 (~ -80 dBFS, i.e. silence) use 0.1 (-20 dBFS).
    Gain = target / mask RMS (mask RMS of 0 → silent mask).
  - **Clipping guard**: if `peak * gain > 0.99`, reduce gain so the peak is 0.99 FS.
  - **Fades**: 10 ms linear fade in and out, applied after gain; for spans shorter than 20 ms the fade
    length is half the span.
  - Masked samples **replace** (not mix with) the original; float result is quantized to the output
    dtype only within the span.
- **Rationale**: Implements FR-012–FR-015 and clarification Q1; all pure numpy functions testable
  without a model.

## R9. Atomic output, temp files and privacy

- **Decision**: Temporary decoding/resampling files live in a `tempfile.TemporaryDirectory()`
  context. Output WAV and JSON report are written to a temp file in the destination directory and
  moved into place with `os.replace`; on any exception the temp file is removed. Existing outputs
  are replaced silently (clarification Q3). Reject as invalid input when output, report, or input
  resolve to the same path as each other (`Path.resolve()`), or the output directory does not
  exist.
- **Rationale**: No partial outputs, no leftover temp files (FR-020, SC-007), input never touched.
- **Privacy**: No `logging` of transcript text or audio; CLI only prints counts and paths
  (FR-021). The words file content is not echoed either.

## R10. Progress callback

- **Decision**: `ProgressCallback = Callable[[str, float], None]`. Stages and fraction ranges:
  `loading` 0.00–0.05, `transcribing` 0.05–0.85, `masking` 0.85–0.95, `writing` 0.95–1.00, final
  call `("done", 1.0)`. A small wrapper clamps to [0, 1] and enforces monotonic values.
- **Rationale**: FR-027; maps cleanly onto a Gradio progress bar in Feature 2.

## R11. Testing strategy

- **Decision**: pytest. Unit tests per module (words, matching, spans, presets, masking, report,
  audio_io). Integration tests for `process_audio` and the CLI (via `main(argv)` and a subprocess
  smoke test) using a `FakeTranscriber` and synthetic audio generated in `tmp_path` fixtures
  (sine + silence, ≤ 5 s). Real-model tests marked `@pytest.mark.whisper`, deselected by default via
  `addopts = "-m 'not whisper'"`. mp3 tests skip when `ffmpeg` is absent.
- **Rationale**: Principle V — fast, offline, model-free default suite.
