# Data Model: "Censor Bar" Dark Theme

No persisted data changes. `jobs.json`, `Job` and `JobStatus` are untouched. The "entities" here
are constants in `src/bleeper/ui/theme.py`.

## Palette (constants)

| Constant | Value | Used for |
|----------|-------|----------|
| `BACKGROUND` | `#0F1115` | Page body, input fills |
| `CARD` | `#181B22` | Blocks, panels, table rows, secondary buttons |
| `TEXT` | `#E8EAED` | Body, labels, table text |
| `ACCENT` | `#C6FF3D` | Primary button, selected radio, focus/accent borders, loader, slider, links, waveform progress, `done` status |
| `ON_ACCENT` | `#0F1115` | Text on `ACCENT` / `ACCENT_HOVER` |
| `RUNNING` | `#FFB800` | `running` status |
| `FAILED` | `#FF4D4D` | `failed` status, "Delete job" (cancel) button, error text/border |
| `QUEUED` | `#8A93A3` | `queued` status |
| `MUTED` | `= QUEUED` | Subdued text, placeholder, unplayed waveform |
| `BORDER` | `#2A2F3A` | Block, input and table borders |
| `ACCENT_HOVER` | `#D4FF6B` | Primary button hover fill |

Rule: no other module contains a hex color literal (enforced by a test).

## Status color mapping

`STATUS_COLORS: dict[str, str]` keyed by `JobStatus` value:

| Status text | Color |
|-------------|-------|
| `queued` | `QUEUED` |
| `running` | `RUNNING` |
| `done` | `ACCENT` |
| `failed` | `FAILED` |

Rules:

- Applied only to the Status column's text color; the cell value is unchanged.
- Any other cell value (including the "No jobs yet" hint row's empty Status) gets no style.
- Keys come from `JobStatus` values; `theme.py` imports `JobStatus` (no Gradio dependency in
  `jobs.py` is introduced).

## Derived objects

- `THEME`: `gr.themes.Base(...).set(...)` with every overridden variable and its `_dark` twin
  equal.
- `CSS`: inline string, `:root { color-scheme: dark; }`.
- `WAVEFORM`: `gr.WaveformOptions(waveform_color=MUTED, waveform_progress_color=ACCENT)`.
