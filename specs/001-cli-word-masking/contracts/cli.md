# CLI Contract: `bleeper`

## Synopsis

```text
bleeper INPUT --words FILE (--mask FILE | --preset {beep,tone,noise}) -o OUTPUT
        [--model NAME] [--lang CODE] [--padding MS] [--report FILE]
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `INPUT` | yes | — | Input audio, `.wav` or `.mp3`. Never modified. |
| `--words FILE` | yes | — | UTF-8 text, one word/phrase per line; blank lines and `#` comments ignored. |
| `--mask FILE` | one of | — | Custom mask sound (`.wav`/`.mp3`); looped or trimmed to each span. |
| `--preset NAME` | one of | — | Built-in mask: `beep` (1 kHz), `tone` (400 Hz), `noise` (white noise). |
| `-o, --output FILE` | yes | — | Output WAV path. Replaced if it exists; must differ from `INPUT`. |
| `--model NAME` | no | `small` | faster-whisper model name or local model path. |
| `--lang CODE` | no | auto-detect | Spoken language code, e.g. `es`, `en`. |
| `--padding MS` | no | `80` | Milliseconds added before and after each match; integer ≥ 0. |
| `--report FILE` | no | `OUTPUT` with `.json` suffix | JSON report path. Replaced if it exists. |
| `-h, --help` | no | — | Show usage, defaults and exit codes. |

Exactly one of `--mask` / `--preset` is required.

## Exit codes

| Code | Meaning | Examples |
|------|---------|----------|
| `0` | Success, including "no forbidden words found" | Output and report written |
| `1` | Invalid input | Missing/unsupported/corrupt input, missing or empty words file, both or neither of `--mask`/`--preset`, negative padding, unknown language code, output equals input, report equals output/input, output directory missing, ffmpeg required but not installed, any argument parsing error |
| `2` | Processing error | Model cannot be loaded/downloaded, transcription failure, ffmpeg failure on a valid file, cannot write output |

## Streams

- **stdout** (success only):
  ```text
  Masked 3 spans.
  Output: out/episode-clean.wav
  Report: out/episode-clean.json
  ```
  With no matches:
  ```text
  No forbidden words found; output is identical to the input.
  Output: out/episode-clean.wav
  Report: out/episode-clean.json
  ```
- **stderr**: progress lines (`[transcribing] 42%`) and errors. Errors are a single line
  `error: <what failed>. <how to fix it>`, e.g.
  `error: words file 'words.txt' not found. Check the path passed to --words.`
- Transcript text, audio content and words-file content are never printed.

## Side effects

- Writes exactly two files: OUTPUT and the report. Both are written atomically (temp file + rename);
  on failure neither is left partially written.
- Temporary files (mp3 decode, mask resample) are removed before exit in all cases.
- Network access happens only if the model is not yet cached locally.
