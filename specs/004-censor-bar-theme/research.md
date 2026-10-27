# Research: "Censor Bar" Dark Theme

All findings were checked against the installed Gradio **6.30.0** (Python 3.12 venv).

## R1. Building the theme

- **Decision**: `gr.themes.Base(font=SYSTEM_FONTS, font_mono=SYSTEM_MONO)` followed by a single
  `.set(...)` call that assigns every color variable we touch **and** its `*_dark` twin to the
  same palette constant.
- **Rationale**: `Base` is the neutral starting point the user asked for. Gradio switches to the
  `*_dark` values when the browser prefers dark mode (or `?__theme=dark`); giving both the same
  value makes the page dark in both system modes without JavaScript or URL tricks (FR-002).
  Base's default fonts are bundled `LocalFont`s (IBM Plex), not remote, but we still pass plain
  system-font strings so the existing launcher test (all fonts are `str`, none `GoogleFont`) keeps
  passing and no font files are requested at all (FR-010).
- **Alternatives considered**:
  - `gr.themes.Default(...)` re-tinted: its orange `primary_hue` would leak into every variable we
    forget to override.
  - Forcing dark mode with a `js=` snippet that adds `.dark` to `<body>`: works, but light-mode
    values would still need overriding for the first paint, and it adds JS for no gain.
  - Building hues with `gr.themes.Color(...)`: needs 11 shades per hue, i.e. many more hex values
    than the palette, against "colors defined once".

## R2. Which variables to override

- **Decision**: Override the color groups listed in [contracts/theme.md](contracts/theme.md):
  body/background fills, blocks, block labels/titles, inputs, borders, accent (`color_accent`,
  `color_accent_soft`, `border_color_accent*`, `loader_color`, `slider_color`), primary button,
  secondary button, cancel button (`variant="stop"`), checkbox/radio (selected state), tables,
  links, and error box. Size, spacing and radius variables are left at Base defaults.
- **Rationale**: These are all the color variables Gradio 6 exposes that can show the default
  accent. Leaving sizes untouched keeps the layout identical (FR-012).
- **Alternatives considered**: Overriding all 325 variables — noise, no visible gain.

## R3. Coloring the Status column

- **Decision**: Keep `render_table()` and every handler returning plain `list[list[str]]`. Wrap the
  jobs table instance's `postprocess` with a function from `theme.py` that adds
  `metadata={"styling": [[css, ...], ...]}` — `color: <status color>` on the Status cell of rows
  whose status is one of the four known words, `""` elsewhere.
- **Rationale**:
  - Existing tests assert `render_table()` and handler outputs are lists of string rows (e.g.
    `rows = {row[1]: row for row in table}`), so values cannot change shape (SC-004).
  - `gr.Dataframe.postprocess` already returns a `DataframeData` with an optional `metadata`
    field whose `styling` matrix the frontend applies per cell, including for
    `interactive=False`. Prototyped: the wrapped postprocess yields
    `[['', 'color: #C6FF3D'], ['', 'color: #FF4D4D'], ['', '']]`, and the hint row stays unstyled.
  - Only the cell's text color changes; the status word itself is always present (FR-006).
- **Gotcha**: The component computes its initial `value` in `__init__`, before the wrapper is
  installed, so its config carries `metadata: None`. After wrapping, the initial value must be
  recomputed through the wrapped `postprocess` (or rely on `demo.load`, which re-renders the
  table on every page open). The plan recomputes it so the first paint is already colored.
- **Alternatives considered**:
  - Subclassing `gr.Dataframe`: Gradio's component metaclass writes a `.pyi` stub next to the
    defining module at class-creation time (it failed under `stdin` with `FileNotFoundError`), and
    the subclass name changes the frontend block name unless `get_block_name` is overridden.
    Side effects at import are unacceptable in a read-only Docker image.
  - Returning a pandas `Styler` or a `{"data", "headers", "metadata"}` dict from handlers: breaks
    existing tests and imports pandas directly.
  - `datatype="html"` with `<span style=...>` cells: changes cell values (tests, row selection by
    ID cell).
  - Client-side `js=` + `MutationObserver` tagging cells: depends on Gradio's DOM, untestable
    from pytest.

## R4. Waveform colors

- **Decision**: Pass `waveform_options=gr.WaveformOptions(waveform_color=MUTED,
  waveform_progress_color=ACCENT)` to the three preset previews and the masked-result player,
  with the options object defined once in `theme.py`.
- **Rationale**: `gr.WaveformOptions` (present in 6.30.0) sets wavesurfer colors directly; theme
  variables alone do not reliably reach the canvas. Applying it to the result player too
  satisfies "no orange left".

## R5. Extra CSS

- **Decision**: A small inline CSS string in `theme.py`, passed to `launch(css=...)`, containing
  only `:root { color-scheme: dark; }` (native scrollbars, date/file pickers and form controls
  render dark).
- **Rationale**: Not expressible through theme variables; inline CSS needs no network.
  `launch()` accepts `css` in Gradio 6 (alongside `theme`).

## R6. Extra neutral tones

- **Decision**: Besides the seven palette colors, define three neutral helpers in `theme.py`:
  `BORDER` (#2A2F3A, card/input borders), `ACCENT_HOVER` (#D4FF6B, primary button hover) and
  `MUTED` = queued gray reused for subdued text and the unplayed waveform.
- **Rationale**: Borders and hover states need a value; deriving them once as constants keeps
  FR-011. Contrast: dark text on `ACCENT_HOVER` ≈ 16.5:1; text on `BORDER` (secondary button hover) 11.1:1. Red text on `BORDER` is only 4.1:1, so the cancel button's hover uses a red fill with dark text (5.8:1) instead; borders are non-text (WCAG 1.4.11
  doesn't apply to decorative card edges).

## R7. Contrast (FR-009)

Computed with the WCAG relative-luminance formula:

| Foreground | Background | Ratio |
|------------|------------|-------|
| Text #E8EAED | Background #0F1115 | 15.7 |
| Text #E8EAED | Card #181B22 | 14.3 |
| Lime #C6FF3D | Card #181B22 | 14.6 |
| Amber #FFB800 | Card #181B22 | 9.9 |
| Gray #8A93A3 | Card #181B22 | 5.6 |
| Red #FF4D4D | Card #181B22 | 5.3 |
| Dark #0F1115 | Lime #C6FF3D | 16.0 |
| Dark #0F1115 | Lime hover #D4FF6B | 16.5 |
| Text #E8EAED | Border #2A2F3A | 11.1 |
| Dark #0F1115 | Red #FF4D4D | 5.8 |

All ≥ 4.5:1. A unit test recomputes these from the constants so a future color edit cannot
silently break AA.

## R8. Offline rendering

- **Decision**: No `GoogleFont`, no `head=`/`css_paths=` to external URLs; verify by loading the UI
  with the network disabled and checking the browser's network panel for failed requests, and in
  Docker with `--network none` (feature 003).
- **Rationale**: Gradio 6 ships its frontend assets in the wheel; the only remote fetch in the
  default theme was Google Fonts, which the system stack removes.

## R9. README screenshot

- **Decision**: One PNG at `docs/ui-screenshot.png`, around 1280 px wide, with one job in each
  status if practical. Optimized to under 500 KB, referenced with a relative path from the README's
  web UI section.
- **Rationale**: Stored in the repo (no hotlinking), small enough for the constitution's rule
  against committing large files.
