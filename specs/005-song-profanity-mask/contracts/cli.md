# Contract: CLI changes

```bash
bleeper INPUT --words FILE (--mask FILE | --preset {beep,tone,noise} | --style {vocal-dropout,reverse,dip})
        -o OUTPUT [--dip-db DB] [--model NAME] [--lang CODE] [--padding MS] [--report FILE]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--style NAME` | — | **New.** Song-friendly mask: `vocal-dropout` (remove the voice, keep the music), `reverse` (play the word backwards), `dip` (lower the whole mix). Mutually exclusive with `--mask` and `--preset`. |
| `--dip-db DB` | full mute | **New.** Attenuation in dB for `dip` (number > 0, e.g. `20`). Also used when `vocal-dropout` falls back to `dip`. |

## Examples

```bash
bleeper song.mp3 --words words.txt --style vocal-dropout -o out/song-radio.wav
bleeper song.mp3 --words words.txt --style dip --dip-db 24 -o out/song-dip.wav
```

## Output (stdout)

Unchanged, plus one `Note:` line per entry in `result.notes`:

```text
Masked 3 spans.
Note: vocal-dropout needs stereo audio; this file is mono, so dip was used instead.
Output: out/song-radio.wav
Report: out/song-radio.json
```

With `--style vocal-dropout --dip-db 20` on a stereo file:

```text
Note: --dip-db was ignored: this file is stereo, so vocal-dropout was applied.
```

## Exit codes (unchanged)

| Code | When |
|------|------|
| 0 | success |
| 1 | invalid input — including `--style` together with `--mask`/`--preset`, unknown style, invalid or misplaced `--dip-db` |
| 2 | processing error |
