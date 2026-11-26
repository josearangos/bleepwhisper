# Quickstart: Validate the Harmonic Profanity Mask for Songs

**Feature**: [spec.md](spec.md) | Contracts: [cli](contracts/cli.md) · [python-api](contracts/python-api.md) · [report](contracts/report.md) · [ui](contracts/ui.md)

## Prerequisites

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
which ffmpeg               # required for mp3 input
```

## 1. Quality gates (offline, no Whisper model)

```bash
ruff format --check && ruff check
pytest                     # default run; whisper-marked tests are skipped
```

Expected: all green. New tests cover, with synthetic stereo audio generated in code:

| Check | Spec |
|-------|------|
| vocal-dropout attenuates a centered tone above the crossover by ≥ 30 dB inside the span, keeps a side-panned tone within 1 dB and a centered 60 Hz tone within 1 dB | FR-003, SC-003 |
| reverse span equals the reversed original away from the 10 ms edges | FR-004 |
| dip with default mutes the span interior; with `dip_db=20` the interior is 20 dB lower | FR-005 |
| no sample jump at span edges larger than the largest step in the surrounding original | FR-006, SC-005 |
| samples outside spans are bit-identical; rate, channels, duration preserved | FR-007, SC-004 |
| mono and dual-mono inputs with vocal-dropout apply dip and report the fallback | FR-008 |
| `--style` together with `--mask`/`--preset` → exit 1 with a clear message | FR-009 |
| CLI and UI worker outputs are identical for each style | FR-010 |
| report has `style` (and `requested_style` on fallback); preset reports unchanged | FR-011, FR-014 |
| `style_preview` returns stereo audio for each style | FR-012 |

## 2. Manual end-to-end with a real song (requires the Whisper model)

Use a stereo song you are allowed to process, and a words file:

```bash
printf 'damn\nshit\n' > /tmp/words.txt
for s in vocal-dropout reverse dip; do
  bleeper song.mp3 --words /tmp/words.txt --style "$s" --lang en -o "out/song-$s.wav"
done
```

Expected:

- Each run prints `Masked N spans.` and writes `out/song-<style>.wav` + `.json`.
- Listening at each reported `start`: the word is unintelligible; with `vocal-dropout` the drums,
  bass and wide instruments keep playing; with `reverse` the voice is heard backwards; with `dip`
  the mix goes quiet for the word only. No clicks at the edges. No beep anywhere.
- `out/song-<style>.json` entries include `"style": "<style>"`.

Fallback check:

```bash
ffmpeg -y -i song.mp3 -ac 1 /tmp/song-mono.wav
bleeper /tmp/song-mono.wav --words /tmp/words.txt --style vocal-dropout -o out/mono.wav
```

Expected: a `Note:` line saying dip was used; report entries have `"style": "dip"` and
`"requested_style": "vocal-dropout"`.

Lyrics over loud music (User Story 4, best effort): if words are missed, pass `--lang` and try a
larger model, e.g. `--model medium`, then compare the reports.

## 3. Web UI

```bash
python -m bleeper.ui
```

Expected: the Mask selector lists "Song: vocal dropout", "Song: reverse" and "Song: dip", each with
a stereo preview player; a job run with a song style finishes with the same WAV and report as the
CLI run above; a mono file shows the fallback note in the job details.
