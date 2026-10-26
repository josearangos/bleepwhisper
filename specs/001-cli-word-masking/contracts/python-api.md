# Python API Contract: `bleeper.core`

Public names exported from `bleeper.core`:
`process_audio`, `ProcessResult`, `ReportEntry`, `ProgressCallback`, `Transcriber`,
`Transcription`, `TranscribedWord`, `BleeperError`, `InvalidInputError`, `ProcessingError`,
`PRESETS`.

## `process_audio`

```python
def process_audio(
    input_path: str | Path,
    words_path: str | Path,
    output_path: str | Path,
    *,
    mask_path: str | Path | None = None,
    preset: str | None = None,          # one of PRESETS = ("beep", "tone", "noise")
    model: str = "small",
    language: str | None = None,        # None → auto-detect
    padding_ms: int = 80,
    report_path: str | Path | None = None,  # None → output_path.with_suffix(".json")
    progress: ProgressCallback | None = None,
    transcriber: Transcriber | None = None, # None → faster-whisper on CPU with `model`
) -> ProcessResult: ...
```

**Preconditions** (violations raise `InvalidInputError` before any transcription):
exactly one of `mask_path`/`preset`; `preset in PRESETS`; `padding_ms >= 0`; input, words and mask
files exist and are readable; resolved `output_path`, `report_path` and `input_path` are pairwise
distinct; output and report parent directories exist.

**Postconditions** (on return):
- `output_path` holds a WAV with the input's sample rate, channel count and sample count.
- Samples outside every reported span equal the decoded input samples.
- `report_path` holds the JSON from [report-schema.json](report-schema.json); `result.report` has
  the same entries.
- No temporary files remain; `input_path` is unmodified.

**Errors**: `InvalidInputError` (CLI exit 1) or `ProcessingError` (CLI exit 2). Any other
exception from dependencies is wrapped in `ProcessingError` with an actionable message. On error
neither output nor report is created or partially written.

**Determinism**: identical arguments and identical transcriber output ⇒ byte-identical output WAV and
report.

## `ProgressCallback`

```python
ProgressCallback = Callable[[str, float], None]
```

Called with `(stage, fraction)`. `stage ∈ {"loading", "transcribing", "masking", "writing",
"done"}`; `fraction ∈ [0.0, 1.0]`, non-decreasing across calls; the last call on success is
`("done", 1.0)`. Exceptions raised by the callback propagate (they abort processing).

## `Transcriber`

```python
class Transcriber(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        language: str | None,
        on_progress: Callable[[float], None],  # fraction of audio transcribed, 0..1
    ) -> Transcription: ...

@dataclass(frozen=True)
class Transcription:
    words: list[TranscribedWord]
    language: str  # the `language` argument if given, otherwise the detected language
```

`process_audio` copies `Transcription.language` into `ProcessResult.language`. The transcriber
holds no per-call state, so one instance can be reused across calls (the future UI relies on this).

The default implementation wraps faster-whisper (`device="cpu"`, `compute_type="int8"`,
`word_timestamps=True`, `local_files_only=True` first). Tests supply a fake returning fixed words.

## `ProcessResult` / `ReportEntry`

```python
@dataclass(frozen=True)
class ReportEntry:
    word: str
    start: float  # seconds, 3 decimals
    end: float

@dataclass(frozen=True)
class ProcessResult:
    output_path: Path
    report_path: Path
    report: list[ReportEntry]
    language: str
```
