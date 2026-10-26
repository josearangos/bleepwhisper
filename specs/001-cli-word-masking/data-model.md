# Data Model: Bleeper CLI — Mask Forbidden Words in Audio

All entities are immutable `@dataclass(frozen=True)` values in `bleeper.core`, except `AudioData`,
which wraps a numpy array. Times in seconds are `float`; sample positions are `int`.

## ForbiddenEntry

A normalized word or phrase from the words file.

| Field | Type | Notes |
|-------|------|-------|
| `original` | `str` | Line as written (trimmed); never logged |
| `tokens` | `tuple[str, ...]` | Output of `normalize(original)`; length ≥ 1 |

**Validation**: lines that are blank or start with `#` (after leading whitespace) are skipped;
lines whose normalization is empty are skipped; duplicates (same `tokens`) are collapsed. If no
entries remain → `InvalidInputError("no forbidden words found in <path>")`. File missing or not
UTF-8 → `InvalidInputError`.

## TranscribedWord

| Field | Type | Notes |
|-------|------|-------|
| `text` | `str` | Raw word from the transcriber (may include leading space/punctuation) |
| `start` | `float` | Seconds, ≥ 0 |
| `end` | `float` | Seconds, ≥ `start` |

Produced by a `Transcriber`; consumed only by matching.

## Transcription

Return value of `Transcriber.transcribe`.

| Field | Type | Notes |
|-------|------|-------|
| `words` | `list[TranscribedWord]` | In transcript order |
| `language` | `str` | The requested language code, or the detected one when none was given |

## Match

| Field | Type | Notes |
|-------|------|-------|
| `text` | `str` | Transcript text of the matched words, stripped and joined by one space |
| `start` | `float` | Start of first matched word |
| `end` | `float` | End of last matched word |

## Span

The unit of masking and reporting (the spec's **Masked Span**).

| Field | Type | Notes |
|-------|------|-------|
| `start` | `int` | First masked sample (inclusive), ≥ 0 |
| `end` | `int` | Last masked sample (exclusive), ≤ `n_samples`, > `start` |
| `words` | `tuple[str, ...]` | Match texts covered, in transcript order |

**Rules**: built from matches by pad → clamp → sort → merge (`next.start <= cur.end`). Spans in the
final list are sorted and non-overlapping. Zero-length spans (possible only after clamping
degenerate input) are dropped.

## AudioData

| Field | Type | Notes |
|-------|------|-------|
| `samples` | `numpy.ndarray` | Shape `(n_samples, channels)`, dtype `int32` (PCM) or `float32`/`float64` |
| `sample_rate` | `int` | Hz |
| `subtype` | `str` | soundfile subtype to write back (`PCM_16`, `PCM_24`, `PCM_32`, `FLOAT`, …) |

Derived: `n_samples`, `channels`, `duration = n_samples / sample_rate`.

## Mask provider

No dedicated type: the pipeline passes `apply_masks` a function
`mask_for: Callable[[int], np.ndarray]` that returns a **mono float64** mask of exactly the requested
number of samples.

| Source | `mask_for(n)` | Notes |
|--------|---------------|-------|
| Preset (`beep`, `tone`, `noise`) | `generate_preset(name, n, sample_rate)` | Generated at the exact length |
| Custom file | `fit_to_length(mask, n)` | `mask` loaded once by `load_mask`: mono float64 at the input's sample rate; looped or trimmed |

`apply_masks` scales and fades the mono mask, then broadcasts it to every channel of the input.

## ReportEntry

| Field | Type | Notes |
|-------|------|-------|
| `word` | `str` | `" ".join(span.words)` |
| `start` | `float` | `round(span.start / sample_rate, 3)` |
| `end` | `float` | `round(span.end / sample_rate, 3)` |

JSON report = `list[ReportEntry]` serialized as an array of objects, ordered by `start`
(see [contracts/report-schema.json](contracts/report-schema.json)).

## ProcessResult

Returned by `process_audio`.

| Field | Type | Notes |
|-------|------|-------|
| `output_path` | `Path` | Masked WAV |
| `report_path` | `Path` | JSON report |
| `report` | `list[ReportEntry]` | Same content as the JSON file |
| `language` | `str` | Language used or detected |

## Errors

| Type | Base | CLI exit code | Raised for |
|------|------|---------------|------------|
| `BleeperError` | `Exception` | — | Common base |
| `InvalidInputError` | `BleeperError` | 1 | Missing/unreadable/unsupported input, words or mask file; empty words list; bad padding/preset/language; output, report and input paths colliding; output directory missing; ffmpeg needed but missing |
| `ProcessingError` | `BleeperError` | 2 | Model load/download failure, transcription failure, ffmpeg failure on a valid file, write failure |

## Pipeline flow (state transitions)

```text
validate inputs ─► load words ─► load audio (decode mp3 via ffmpeg) ─► load mask
      │                                                                   │
      └──────────── InvalidInputError (exit 1) ◄──────────────────────────┘
                                                                          ▼
transcribe (progress 0.05→0.85) ─► find matches ─► build spans ─► apply masks
      │                                                                   │
      └──────────── ProcessingError (exit 2) ◄────────────────────────────┤
                                                                          ▼
                              atomic write WAV + JSON report ─► ProcessResult ("done", 1.0)
```
