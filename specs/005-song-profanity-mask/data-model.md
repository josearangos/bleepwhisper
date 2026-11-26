# Data Model: Harmonic Profanity Mask for Songs

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md)

All types are immutable and live in `bleeper.core`. Existing types not listed here are unchanged.

## SongStyle (new, `bleeper.core.song_styles`)

The in-place transformation applied to a masked span.

| Value | Meaning |
|-------|---------|
| `vocal-dropout` | Remove the center (mid) component above the low crossover; keep side + low mid (R1, R2). |
| `reverse` | Play the span backwards (R5). |
| `dip` | Lower the whole mix by `dip_db` dB, or mute when `dip_db` is `None` (R6). |

- Exposed as the tuple `SONG_STYLES = ("vocal-dropout", "reverse", "dip")`.
- Validation: any other value → `InvalidInputError("unknown style '<x>'. Choose one of: ...")`.

## MaskChoice (validation rule, not a stored type)

Exactly one of the following per run (FR-009):

| Option | Source | Existing? |
|--------|--------|-----------|
| `mask_path` | custom sound file | yes |
| `preset` | `beep` / `tone` / `noise` | yes |
| `style` | a `SongStyle` | **new** |

- `dip_db`: optional float, must be `> 0` when given; only meaningful when the applied style is
  `dip`. Passing it with a preset or custom mask → `InvalidInputError`.

## StylePlan (new, internal to the pipeline)

Resolved once per file after decoding.

| Field | Type | Description |
|-------|------|-------------|
| `requested` | `str` | Style the user chose. |
| `applied` | `str` | Style actually used for every span of this file. |
| `fallback_reason` | `str \| None` | e.g. `"mono or dual-mono input"` when `vocal-dropout` → `dip`. |

Rule (R3): `requested == "vocal-dropout"` and (`channels == 1` or side RMS < 1e-3 × mid RMS) →
`applied = "dip"`; otherwise `applied = requested`. If `requested == "vocal-dropout"`, the file is
stereo and `dip_db` was given, a note says `--dip-db` was ignored.

## Span (existing, unchanged)

`start`, `end` (sample indices, end exclusive), `words`. Padding, clamping and merging rules are
unchanged (Principle III).

## ReportEntry (extended)

| Field | Type | When present |
|-------|------|--------------|
| `word` | `str` | always (existing) |
| `start` | `float` seconds | always (existing) |
| `end` | `float` seconds | always (existing) |
| `style` | `str` | only when a song style was used: the **applied** style |
| `requested_style` | `str` | only when a fallback happened |

`to_dict()` omits `style` / `requested_style` when they are `None`, so preset and custom-mask
reports are byte-identical to today (FR-014). See [contracts/report.md](contracts/report.md).

## ProcessResult (extended)

Adds `notes: tuple[str, ...] = ()` — human-readable messages for the interfaces, e.g.
`"vocal-dropout needs stereo audio; this file is mono, so dip was used instead."` Empty for
preset/custom runs.

## UI Job (extended, `bleeper.ui.jobs`)

`Job.mask` keeps its string form; new values are `vocal-dropout`, `reverse`, `dip` (alongside
`beep`, `tone`, `noise`, `custom: <file>`). The worker maps codes in `SONG_STYLES` to `style=` and
the others to `preset=` / `mask_path=` as today. `Job` gains `notes: tuple[str, ...] = ()`, set by
`JobStore.finish(...)` from `ProcessResult.notes` and shown in the job details summary.

## State transitions

None new. Jobs keep the existing `queued → running → done | failed` lifecycle.
