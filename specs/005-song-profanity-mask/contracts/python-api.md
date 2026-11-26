# Contract: Core Python API changes

Only additions; every existing call keeps working with identical results (FR-014).

## `bleeper.core.process_audio`

```python
def process_audio(
    input_path, words_path, output_path, *,
    mask_path=None,
    preset=None,
    style: str | None = None,          # NEW: "vocal-dropout" | "reverse" | "dip"
    dip_db: float | None = None,       # NEW: attenuation for dip; None = full mute
    model="small", language=None, padding_ms=80,
    report_path=None, progress=None, transcriber=None,
) -> ProcessResult
```

Validation (before decoding or transcription, raises `InvalidInputError`):

| Condition | Message (substance) |
|-----------|---------------------|
| not exactly one of `mask_path`, `preset`, `style` | `pass exactly one of --mask, --preset or --style.` |
| `style` not in `SONG_STYLES` | `unknown style '<x>'. Choose one of: vocal-dropout, reverse, dip.` |
| `dip_db` given and `<= 0` | `--dip-db must be greater than 0, got <x>.` |
| `dip_db` given with `mask_path` or `preset`, or with `style="reverse"` | `--dip-db only applies to --style dip (or vocal-dropout on mono files).` |

Behavior:

- Spans are built exactly as today; each span is transformed in place by the applied style with a
  10 ms crossfade at both edges. Samples outside spans are bit-for-bit unchanged; sample rate,
  channel count and duration are preserved.
- `vocal-dropout` on mono / dual-mono input applies `dip` and adds a message to `result.notes`.
- `vocal-dropout` with `dip_db` on a stereo input: `dip_db` is unused, and `result.notes` gets
  `"--dip-db was ignored: this file is stereo, so vocal-dropout was applied."`
- Progress stages are unchanged (`loading`, `transcribing`, `masking`, `writing`, `done`).

## `bleeper.core.ProcessResult`

New field `notes: tuple[str, ...] = ()`.

## New exports from `bleeper.core`

```python
SONG_STYLES: tuple[str, ...]  # ("vocal-dropout", "reverse", "dip")

def style_preview(style: str, seconds: float = 2.0, sample_rate: int = 44100) -> np.ndarray:
    """Stereo (n, 2) float array: a synthetic song with the style applied to its middle second."""
```

## New pure module `bleeper.core.song_styles` (internal, unit-tested)

```python
def apply_style(block: np.ndarray, sample_rate: int, style: str,
                dip_db: float | None = None) -> np.ndarray:
    """Float (n, channels) span → transformed float block of the same shape (no edge crossfade)."""

def crossfade_edges(original: np.ndarray, processed: np.ndarray, sample_rate: int) -> np.ndarray:
    """10 ms linear crossfade original→processed at the start and processed→original at the end."""

def has_usable_stereo(samples: np.ndarray) -> bool:
    """False for 1 channel or side RMS < 1e-3 × mid RMS over the whole file."""

def apply_styles(samples: np.ndarray, sample_rate: int, spans: Sequence[Span],
                 style: str, dip_db: float | None = None) -> np.ndarray:
    """Copy of samples (n, channels) with every span transformed; same dtype as input."""
```
