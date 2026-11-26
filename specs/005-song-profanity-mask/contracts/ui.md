# Contract: Web UI changes

Layout, theme and job lifecycle are unchanged. Only the mask selector grows.

## Mask selector (`MASKS` in `bleeper/ui/submit.py`)

| Label | Code | Kind |
|-------|------|------|
| Classic beep | `beep` | preset (existing) |
| Low tone | `tone` | preset (existing) |
| Noise burst | `noise` | preset (existing) |
| Song: vocal dropout | `vocal-dropout` | song style (new) |
| Song: reverse | `reverse` | song style (new) |
| Song: dip | `dip` | song style (new) |

- A custom mask upload still overrides the selected option (existing rule, label unchanged).
- Jobs table "Mask" column shows the code, as today.

## Previews

Each new option has a preview player built from `style_preview(code)` (stereo, generated in code),
shown alongside the existing preset previews.

## Worker

- Codes in `SONG_STYLES` → `process_audio(..., style=code)`; other codes unchanged.
- `dip_db` is not exposed; the default (full mute) is used.
- `result.notes` are appended to the job's details summary when the job is done.

## Parity

For the same input, words and style, the UI output WAV and report are identical to
`bleeper INPUT --words FILE --style CODE` with default options (Principle I).
