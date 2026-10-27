# Contract: `bleeper.ui.theme`

The only module that defines colors. Imports Gradio (UI-only, like `app.py`) and
`bleeper.ui.jobs.JobStatus`. No audio imports.

## Public names

| Name | Type | Contract |
|------|------|----------|
| Palette constants (`BACKGROUND`, `CARD`, `TEXT`, `ACCENT`, `ON_ACCENT`, `RUNNING`, `FAILED`, `QUEUED`, `MUTED`, `BORDER`, `ACCENT_HOVER`) | `str` | `#RRGGBB` hex; values in [data-model.md](../data-model.md). |
| `STATUS_COLORS` | `dict[str, str]` | Exactly the four `JobStatus` values → palette constant. |
| `THEME` | `gr.themes.Base` | Fonts are plain strings (system stack); for every overridden variable `x`, `x == x_dark`. |
| `CSS` | `str` | Inline CSS only; no `url(`, `@import` or `http`. |
| `WAVEFORM` | `gr.WaveformOptions` | `waveform_progress_color == ACCENT`. |
| `color_status(postprocess, column)` | `Callable[[Callable[[Any], DataframeData]], ...]` → same signature | Returns a wrapper: calls the original, then sets `metadata = {"styling": matrix}` where `matrix[r][column] == f"color: {STATUS_COLORS[status]}"` for known statuses and `""` for every other cell. Leaves `headers`/`data` untouched; empty data → unchanged. |

## Theme variable groups (each with its `_dark` twin set to the same value)

| Group | Variables | Value |
|-------|-----------|-------|
| Page | `body_background_fill`, `background_fill_primary` | `BACKGROUND` |
| Surfaces | `background_fill_secondary`, `block_background_fill`, `panel_background_fill`, `block_label_background_fill`, `block_title_background_fill`, `code_background_fill`, `stat_background_fill`, `table_even_background_fill`, `table_odd_background_fill`, `checkbox_label_background_fill`, `checkbox_label_background_fill_hover`, `checkbox_label_background_fill_selected` | `CARD` |
| Text | `body_text_color`, `block_label_text_color`, `block_title_text_color`, `block_info_text_color` (`MUTED`), `body_text_color_subdued` (`MUTED`), `table_text_color`, `checkbox_label_text_color`, `checkbox_label_text_color_selected`, `accordion_text_color`, `input_placeholder_color` (`MUTED`) | `TEXT` unless noted |
| Borders | `border_color_primary`, `block_border_color`, `block_label_border_color`, `input_border_color`, `input_border_color_hover`, `table_border_color`, `panel_border_color`, `checkbox_border_color`, `checkbox_label_border_color` | `BORDER` |
| Accent | `color_accent`, `color_accent_soft` (`BORDER`), `border_color_accent`, `border_color_accent_subdued`, `input_border_color_focus`, `checkbox_border_color_focus`, `checkbox_border_color_selected`, `checkbox_background_color_selected`, `checkbox_label_border_color_selected`, `loader_color`, `slider_color`, `table_row_focus` (`BORDER`), `link_text_color*` | `ACCENT` unless noted |
| Inputs | `input_background_fill`, `input_background_fill_focus`, `input_background_fill_hover`, `checkbox_background_color`, `checkbox_background_color_hover`, `checkbox_background_color_focus` | `BACKGROUND` |
| Primary button | `button_primary_background_fill`, `button_primary_border_color` / `_hover` → `ACCENT` / `ACCENT_HOVER`; `button_primary_text_color(_hover)` → `ON_ACCENT` | |
| Secondary button | `button_secondary_background_fill(_hover)` → `CARD`/`BORDER`; `button_secondary_border_color(_hover)` → `BORDER`; `button_secondary_text_color(_hover)` → `TEXT` | |
| Cancel button ("Delete job") | `button_cancel_background_fill` → `CARD`, `_hover` → `FAILED`; `button_cancel_border_color(_hover)` → `FAILED`; `button_cancel_text_color` → `FAILED`, `_hover` → `ON_ACCENT` (red on `BORDER` would be only 4.1:1) | |
| Errors | `error_background_fill` → `CARD`; `error_border_color`, `error_text_color`, `error_icon_color` → `FAILED` | |

## Consumers

- `bleeper.ui.app.build_app`: `waveform_options=WAVEFORM` on the 3 preview `gr.Audio` and the
  result player; `table.postprocess = color_status(table.postprocess, TABLE_HEADERS.index("Status"))`
  then recompute the table's initial value through it.
- `bleeper.ui.__main__.main`: `launch(..., theme=THEME, css=CSS)`; `THEME` imported from
  `bleeper.ui.theme` (removed from `app.py`).

## Invariants checked by tests

1. No hex color literal (`#[0-9A-Fa-f]{6}`) in any `src/bleeper/ui/*.py` other than `theme.py`.
2. For every `x` set by `.set()`, `getattr(THEME, x) == getattr(THEME, x + "_dark")`.
3. No orange: none of Gradio's orange shades (`gr.themes.colors.orange` c50–c950) appears in any
   resolved `THEME` color variable.
4. All text/background pairs from research R7 have contrast ≥ 4.5.
5. `color_status` styles each known status, leaves the hint row and other columns unstyled, and
   never changes `data`.
6. `THEME` fonts are all `str` (existing launcher test, unchanged).
