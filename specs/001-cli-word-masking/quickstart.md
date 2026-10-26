# Quickstart & Validation: Bleeper CLI

Validation guide proving Feature 1 works end to end. Interfaces are defined in
[contracts/cli.md](contracts/cli.md) and [contracts/python-api.md](contracts/python-api.md).

## Prerequisites

- Python ≥ 3.10 and [`uv`](https://docs.astral.sh/uv/)
- `ffmpeg` on `PATH` (needed for mp3 input and resampling custom masks): `brew install ffmpeg`
- ~500 MB disk for the `small` model (downloaded once, on first real run)

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
bleeper --help          # shows all options, defaults, exit codes
```

## 1. Quality gates (offline, no model)

```bash
ruff format --check . && ruff check .
pytest                  # default run excludes @pytest.mark.whisper tests
```

Expected: all pass with network disabled and no model cached.

## 2. Acceptance scenarios covered by the default test suite

These run with a fake transcriber and synthetic audio (see [research.md](research.md) R11):

| Scenario (spec) | Expected |
|-----------------|----------|
| Word at 2.0–2.5 s, padding 80 ms (US1-1, SC-001) | Only samples in [1.92 s, 2.58 s) differ; same sample count, rate, channels; exit 0 |
| No matches (US1-2, SC-002) | Output samples identical to input; report `[]`; "No forbidden words found" message; exit 0 |
| Accent/case/punctuation and whole-word rules (US1-3, US1-4) | "Señor" matches "senor,"; "ass" does not match "class" |
| Custom mask 200 ms and 2 s on a 660 ms span (US2-1, US2-2, SC-003) | Masked region exactly 660 ms; looped / trimmed; 10 ms fades |
| Missing words file / only comments (US3-1, US3-2) | Exit 1 with message naming the file |
| Both or neither mask option; output = input (US3-3, US3-4) | Exit 1 |
| Processing failure (US3-6, SC-007) | Exit 2; no output, report or temp files left |
| CLI vs API parity (US4-1, SC-008) | Byte-identical WAV and report |
| Progress (US4-2) | Non-decreasing fractions ending `("done", 1.0)` |

## 3. Manual end-to-end run with the real model

```bash
printf 'hello\n# comment\n\nworld\n' > /tmp/words.txt
# Record or pick a short clip that says "hello world" → sample.wav
bleeper sample.wav --words /tmp/words.txt --preset beep -o /tmp/clean.wav
echo "exit=$?"; cat /tmp/clean.json
```

Expected: exit 0; `/tmp/clean.json` lists `hello` and `world` (or one merged entry
`"hello world"`) with times bracketing each word plus 80 ms; listening to `/tmp/clean.wav` reveals
beeps over both words and unchanged audio elsewhere; `sample.wav` unchanged.

Variants to try:

```bash
bleeper sample.mp3 --words /tmp/words.txt --mask quack.wav -o /tmp/clean2.wav --lang en --padding 0
bleeper sample.wav --words /tmp/empty.txt --preset tone -o /tmp/x.wav; echo $?   # → 1
bleeper sample.wav --words /tmp/words.txt --preset noise -o sample.wav; echo $?  # → 1
```

## 4. Offline check

After the first real run has cached the model, disconnect from the network and rerun step 3:
it must succeed identically.

## 5. Optional real-model tests

```bash
pytest -m whisper       # requires the cached model; synthesizes or uses a tiny speech clip
```
