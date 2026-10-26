# Core API Additions: `bleeper.core`

These are additive only. Existing functions, the CLI and `process_audio` don't change, so CLI output
stays identical. The new names are re-exported from `bleeper.core`: `probe_audio`, `AudioInfo`,
`load_words`, `preset_preview`.

## `probe_audio`

```python
@dataclass(frozen=True)
class AudioInfo:
    duration: float      # seconds
    sample_rate: int
    channels: int

def probe_audio(path: str | Path) -> AudioInfo: ...
```

- Reads only the header (`soundfile.info`), with no full decode; it works for WAV and MP3.
- Raises `InvalidInputError` when the file is missing, the extension isn't `.wav`/`.mp3` (same
  message as `load_audio`), or the header can't be read ("cannot read '<name>': not a valid audio
  file. Check that the file is not corrupt.").
- Used by the UI for the 30-minute limit, zero-length files and custom-mask readability.

## `load_words` (re-export)

```python
def load_words(path: str | Path) -> list[ForbiddenEntry]: ...
```

Unchanged behavior and messages (missing, not UTF-8, no usable entries → `InvalidInputError`). The
UI uses `len(...)` for the "N forbidden words loaded" confirmation.

## `preset_preview`

```python
def preset_preview(name: str, seconds: float = 1.0, sample_rate: int = 44100) -> np.ndarray: ...
```

- Returns mono float64 samples of exactly `round(seconds * sample_rate)` samples: `generate_preset`
  scaled to 0.5 peak, with the core's 10 ms `fade`.
- Raises `InvalidInputError` for an unknown preset name (same message as `generate_preset`).
- Pure: no I/O. The UI passes `(sample_rate, samples)` to `gr.Audio` for each preview.
