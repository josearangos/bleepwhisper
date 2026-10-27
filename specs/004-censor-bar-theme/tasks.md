---

description: "Task list for the Censor Bar dark theme"
---

# Tasks: "Censor Bar" Dark Theme for the Web UI

**Input**: Design documents from `/specs/004-censor-bar-theme/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/theme.md, quickstart.md

**Tests**: Included. Constitution Principle V requires pytest tests for every module, so the new
`theme.py` gets `tests/unit/test_ui_theme.py`. **Existing test files MUST NOT be edited** (SC-004).

**Organization**: Tasks are grouped by user story (US1–US4 from spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)

## Path Conventions

Single project: `src/bleeper/ui/`, `tests/unit/` at the repository root. Run commands with the repo
venv (`.venv/bin/python -m pytest`, `.venv/bin/ruff`). Gradio installed: 6.30.0.

---

## Phase 1: Setup

**Purpose**: Confirm the baseline before any change

- [ ] T001 Run `.venv/bin/ruff format --check && .venv/bin/ruff check && .venv/bin/python -m pytest` from the repo root and record that everything passes on the untouched code (baseline for SC-004)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The palette module every story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 Create `src/bleeper/ui/theme.py` with a module docstring ("Censor bar" dark theme for the web UI: the only place colors are defined) and the palette constants, exactly: `BACKGROUND = "#0F1115"`, `CARD = "#181B22"`, `TEXT = "#E8EAED"`, `ACCENT = "#C6FF3D"`, `ON_ACCENT = "#0F1115"`, `RUNNING = "#FFB800"`, `FAILED = "#FF4D4D"`, `QUEUED = "#8A93A3"`, `MUTED = QUEUED`, `BORDER = "#2A2F3A"`, `ACCENT_HOVER = "#D4FF6B"`. Fully type-hinted, `from __future__ import annotations`, match `app.py` style. No audio or numpy imports (checked by `tests/unit/test_ui_boundaries.py`)
- [ ] T003 Create `tests/unit/test_ui_theme.py` with (a) a test that no `src/bleeper/ui/*.py` file other than `theme.py` contains a hex color literal matching `#[0-9A-Fa-f]{6}\b` (contract invariant 1) and (b) a WCAG contrast helper (relative luminance per WCAG 2.x) plus a parametrized test asserting ≥ 4.5 for every pair in research.md R7: TEXT/BACKGROUND, TEXT/CARD, ACCENT/CARD, RUNNING/CARD, QUEUED/CARD, FAILED/CARD, ON_ACCENT/ACCENT, ON_ACCENT/ACCENT_HOVER, TEXT/BORDER, ON_ACCENT/FAILED (contract invariant 4). Gradio is a dev dependency, so import `bleeper.ui.theme` directly

**Checkpoint**: `pytest tests/unit/test_ui_theme.py` passes (`app.py` has no hex literals today, so the one-place test already passes).

---

## Phase 3: User Story 1 - A distinctive dark look on first open (Priority: P1) 🎯 MVP

**Goal**: The UI is dark in both system modes; "Mask audio" is the lime call to action; the selected preset is lime; no orange anywhere; system fonts only; offline-safe.

**Independent Test**: quickstart.md §2 and §5. Open the UI in light and dark system modes: both identical and dark, lime primary button and radio, no orange, no failed font/CDN requests.

### Tests for User Story 1

- [ ] T004 [P] [US1] In `tests/unit/test_ui_theme.py`, add tests: (a) for every theme variable name in `theme.THEME_COLORS` (see T005), `getattr(THEME, name) == getattr(THEME, name + "_dark")` (invariant 2); (b) no value of `gr.themes.colors.orange` (`c50`…`c950`, compared case-insensitively) appears in any attribute of `THEME` whose name contains `color` or `fill` (invariant 3); (c) all `THEME._font` and `THEME._font_mono` entries are `str` (invariant 6); (d) `"url(" not in CSS`, `"@import" not in CSS`, `"http" not in CSS`, and `"color-scheme: dark" in CSS`; (e) `THEME.button_primary_background_fill == ACCENT` and `THEME.button_primary_text_color == ON_ACCENT`

### Implementation for User Story 1

- [ ] T005 [US1] In `src/bleeper/ui/theme.py`, add `import gradio as gr`, `SYSTEM_FONTS = ["ui-sans-serif", "system-ui", "sans-serif"]`, `SYSTEM_MONO = ["ui-monospace", "monospace"]`, and a module constant `THEME_COLORS: dict[str, str]` mapping each variable in the "Theme variable groups" table of `specs/004-censor-bar-theme/contracts/theme.md` to its palette constant (Page, Surfaces, Text, Borders, Accent, Inputs, Primary button incl. `button_primary_background_fill_hover`/`button_primary_border_color_hover` → `ACCENT_HOVER` and `button_primary_text_color_hover` → `ON_ACCENT`, Secondary button, Cancel button: `button_cancel_background_fill` → `CARD`, `button_cancel_background_fill_hover` → `FAILED`, `button_cancel_border_color(_hover)` → `FAILED`, `button_cancel_text_color` → `FAILED`, `button_cancel_text_color_hover` → `ON_ACCENT`, Errors). Expand `link_text_color*` to `link_text_color`, `link_text_color_active`, `link_text_color_hover`, `link_text_color_visited`. Then `THEME = gr.themes.Base(font=SYSTEM_FONTS, font_mono=SYSTEM_MONO).set(**THEME_COLORS, **{f"{name}_dark": value for name, value in THEME_COLORS.items()})` and `CSS = ":root { color-scheme: dark; }"`. Keep sizes/spacing/radii at Base defaults (no layout change)
- [ ] T006 [US1] In `src/bleeper/ui/app.py`, remove the `THEME = gr.themes.Default(...)` block and its "System fonts only" comment, and update the module docstring to say Gradio is imported only here and in `theme.py` (e.g. "Gradio layout and event handlers (Gradio is imported only here and in theme.py)."). Change nothing else in this task
- [ ] T007 [US1] In `src/bleeper/ui/__main__.py`, change the guarded import to `from bleeper.ui.app import build_app` plus `from bleeper.ui.theme import CSS, THEME` (both inside the existing `try`/`except ImportError`), and add `css=CSS` to the `demo.launch(...)` call next to `theme=THEME`. Do not change any other launch argument (`tests/integration/test_ui_main.py` checks them)
- [ ] T008 [US1] Run `.venv/bin/python -m pytest` and ruff; all pass with no edits to existing tests. Then manually verify quickstart.md §2 (light + dark system mode, lime button/radio, hover, focus rings, no orange) and §5 (offline: no failed requests, nothing to fonts.googleapis.com / fonts.gstatic.com / CDNs)

**Checkpoint**: MVP — the UI has its own dark identity.

---

## Phase 4: User Story 2 - Job status readable at a glance (Priority: P2)

**Goal**: Status cells show the status word in gray/amber/lime/red; values unchanged; hint row unstyled.

**Independent Test**: quickstart.md §3. A job in each status shows the right color and its word; readable in grayscale.

### Tests for User Story 2

- [ ] T009 [P] [US2] In `tests/unit/test_ui_theme.py`, add tests for `STATUS_COLORS` and `color_status` (invariant 5): `set(STATUS_COLORS) == {s.value for s in JobStatus}` with `queued→QUEUED`, `running→RUNNING`, `done→ACCENT`, `failed→FAILED`; build `gr.Dataframe(headers=["ID", "Status"], interactive=False)`, wrap `df.postprocess` with `color_status(df.postprocess, 1)`, call it with rows for all four statuses plus the hint row `["", "No jobs yet. Submit an audio file above."]` and assert: `out.data` equals the input rows unchanged; `out.metadata["styling"][r][1] == f"color: {STATUS_COLORS[status]}"` for status rows; every other cell, and the hint row's cells, are `""`; an empty value (`[]`) returns `metadata` `None` without error

### Implementation for User Story 2

- [ ] T010 [US2] In `src/bleeper/ui/theme.py`, import `JobStatus` from `bleeper.ui.jobs` and add `STATUS_COLORS: dict[str, str] = {JobStatus.QUEUED.value: QUEUED, JobStatus.RUNNING.value: RUNNING, JobStatus.DONE.value: ACCENT, JobStatus.FAILED.value: FAILED}`. Add `color_status(postprocess, column)` that returns a wrapper (use `functools.wraps`) which calls `postprocess(value)`, and if the result's `data` is non-empty sets `result.metadata = {"styling": [[f"color: {STATUS_COLORS[row[i]]}" if i == column and row[i] in STATUS_COLORS else "" for i in range(len(row))] for row in result.data]}`, then returns it. Type it with `Callable[[Any], DataframeData]` (`from gradio.components.dataframe import DataframeData`). Do NOT subclass `gr.Dataframe` (Gradio's metaclass writes `.pyi` files at class creation, research R3)
- [ ] T011 [US2] In `src/bleeper/ui/app.py` `build_app`, right after creating `table = gr.Dataframe(...)`, add `table.postprocess = color_status(table.postprocess, TABLE_HEADERS.index("Status"))` (import `color_status` from `bleeper.ui.theme`), then recompute the initial value through the wrapper so the first paint is colored: inspect how Gradio 6.30 stores `table.value` (postprocessed dict vs raw) and assign accordingly, e.g. `table.value = table.postprocess(render_table(store)).model_dump()`. Verify with `demo.get_config_file()` that the dataframe's `props.value.metadata.styling` is present when the store has jobs and that its `type` is still `"dataframe"`. Do not change `render_table`, `_row` or any handler
- [ ] T012 [US2] Run the full pytest suite and ruff (existing `tests/integration/test_ui_app.py` must pass untouched), then manually verify quickstart.md §3 (queued gray, running amber, done lime, failed red after an interrupted run; readable with "Emulate vision deficiency: achromatopsia"; hint row in normal text color)

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Themed audio previews (Priority: P3)

**Goal**: The played part of every waveform (3 presets + result player) is lime.

**Independent Test**: quickstart.md §4.

### Tests for User Story 3

- [ ] T013 [P] [US3] In `tests/unit/test_ui_theme.py`, assert `WAVEFORM.waveform_progress_color == ACCENT` and `WAVEFORM.waveform_color == MUTED`

### Implementation for User Story 3

- [ ] T014 [US3] In `src/bleeper/ui/theme.py`, add `WAVEFORM = gr.WaveformOptions(waveform_color=MUTED, waveform_progress_color=ACCENT)`
- [ ] T015 [US3] In `src/bleeper/ui/app.py` `build_app`, pass `waveform_options=WAVEFORM` (imported from `bleeper.ui.theme`) to the three preview `gr.Audio(value=value, label=f"Preview: {label}", interactive=False)` calls and to the `player = gr.Audio(...)` result player. Change no other argument or label
- [ ] T016 [US3] Run pytest + ruff; then manually verify quickstart.md §4 (play each preview and a done job's result: progress is lime)

**Checkpoint**: All waveforms match the theme.

---

## Phase 6: User Story 4 - The look is documented (Priority: P3)

**Goal**: The README shows a screenshot of the themed UI.

**Independent Test**: quickstart.md §7.

- [ ] T017 [US4] Run `bleeper-ui --data-dir /tmp/bleeper-screenshot`, submit a few jobs from `samples/` so the table shows several statuses, and capture the browser window (~1280 px wide) to `docs/ui-screenshot.png`; compress it to under 500 KB (e.g. `pngquant --quality 70-90` or export as optimized PNG) and check with `ls -lh docs/ui-screenshot.png`. If capture needs the user (e.g. screen access), ask them to save the screenshot at that path
- [ ] T018 [US4] In `README.md` "## Web UI" section, right after the intro paragraph, add `![Bleeper web UI with the dark "Censor bar" theme](docs/ui-screenshot.png)` (relative path, no hotlinking)

**Checkpoint**: README renders the screenshot.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T019 Confirm "colors in one place": `grep -rnE '#[0-9A-Fa-f]{6}\b' src/bleeper` returns matches only in `src/bleeper/ui/theme.py` (also covered by T003's test)
- [ ] T020 Confirm `git diff main --stat -- tests/integration tests/unit` lists only the new `tests/unit/test_ui_theme.py` (existing tests unchanged, SC-004) and `git status` shows no stray `.pyi` files under `src/bleeper/ui/`
- [ ] T021 Run the final gate: `.venv/bin/ruff format --check && .venv/bin/ruff check && .venv/bin/python -m pytest`, then the end-to-end flow in quickstart.md §6 (submit, wait for done, download audio and report)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories.
- **US1 (P1)**: needs T002–T003. Introduces `import gradio` and `THEME` in `theme.py`.
- **US2 (P2)**: needs Phase 2. T010 also adds `import gradio`; if US1 is done first, reuse it.
  Independent of US1 functionally.
- **US3 (P3)**: needs Phase 2 (and `import gradio` in `theme.py`). Independent of US1/US2.
- **US4 (P3)**: needs US1–US3 done so the screenshot shows the final look.
- **Polish**: after all stories.

### Within Each Story

- Test task first (it should fail), then theme.py, then app.py / `__main__.py` wiring, then verify.
- `theme.py`, `app.py` and `tests/unit/test_ui_theme.py` are shared files, so tasks touching the
  same file run sequentially.

### Parallel Opportunities

- Each story's test task ([P]) can be written while another story's `theme.py` work is in
  progress. They only append separate test functions, but coordinate edits to the same file.
- US2 and US3 implementation can be developed in parallel by different people (separate
  functions in `theme.py`, separate lines in `app.py`). Merge carefully.

## Parallel Example: User Story 2

```text
Task: "T009 [US2] status color tests in tests/unit/test_ui_theme.py"
Task: "T013 [US3] waveform tests in tests/unit/test_ui_theme.py"   # different story, same file: append-only
```

## Implementation Strategy

### MVP First (User Story 1 only)

1. T001 → T002–T003 → T004–T008.
2. **Stop and validate**: dark in both modes, no orange, offline-safe. Already shippable.

### Incremental Delivery

1. + US2 (status colors) → validate quickstart §3.
2. + US3 (waveforms) → validate §4.
3. + US4 (screenshot) → validate §7.
4. Polish gates (T019–T021).

## Notes

- Visual only: no label, layout, handler, job or audio change. If a task seems to require one,
  stop and flag it.
- Commit after each phase checkpoint.
