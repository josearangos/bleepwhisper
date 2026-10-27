# Implementation Plan: "Censor Bar" Dark Theme for the Web UI

**Branch**: `004-censor-bar-theme` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-censor-bar-theme/spec.md`

## Summary

Replace the Gradio Default look with a dark "Censor bar" theme defined once in a new
`src/bleeper/ui/theme.py`: palette constants, a `gr.themes.Base(...).set(...)` theme whose light
and dark values are identical (always dark), an inline `color-scheme: dark` CSS string, a lime
`WaveformOptions`, and a `color_status` wrapper that adds per-cell styling metadata to the jobs
table's Status column without changing the table's values. `app.py` and `__main__.py` only wire
these in; labels, layout, handlers and audio behavior stay the same. A screenshot is added to the
README.

## Technical Context

**Language/Version**: Python 3.10+ (venv: 3.12)

**Primary Dependencies**: Gradio `>=6,<7` (installed 6.30.0); no new dependencies

**Storage**: N/A (no data changes)

**Testing**: pytest (default run offline, no Whisper model), ruff

**Target Platform**: Local browser via `bleeper-ui` on 127.0.0.1; Docker image from feature 003
with no network

**Project Type**: Python library + CLI + local web UI (single project)

**Performance Goals**: No measurable change to page load or table refresh (2 s timer); styling
adds one small list per refresh

**Constraints**: Visual only; existing tests unchanged; offline (no remote fonts/CDN); WCAG AA
4.5:1; colors in one module; about 2 hours of work

**Scale/Scope**: 1 new module (~120 lines), small edits to `app.py` and `__main__.py`, 1 new test
file, README + 1 image

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I. Core-First | No audio logic touched; theme lives in the UI layer only. CLI/UI output parity unaffected. | ✅ |
| II. Offline, CPU-Only, Private | System fonts only; inline CSS; no remote assets (R1, R5, R8). | ✅ |
| III. Audio Correctness | No change to transcription, matching, masking or output. | ✅ |
| IV. Code Quality | One small single-purpose module, typed, ruff-clean; `THEME` moves out of `app.py` (no dead code). | ✅ |
| V. Testing | New `tests/unit/test_ui_theme.py` covers the module; existing tests unchanged; runs offline. Boundary test (`test_no_audio_logic_in_ui`) automatically covers `theme.py`. | ✅ |
| VI. User Experience | Status stays readable as text; disabled/destructive states stay distinct; jobs stay non-blocking. | ✅ |
| VII. Simplicity & Scope | No new dependency, no JS, no new components; fits the ~2 h budget. | ✅ |

Note: `app.py`'s docstring says it is "the only module that imports Gradio". `theme.py` will also
import Gradio, as the user required. This doesn't conflict with the constitution, which only
forbids Gradio in the core and CLI (`test_module_does_not_import_gradio` checks exactly those).
The docstring will be updated.

**Post-design re-check**: ✅ No violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-censor-bar-theme/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── theme.md         # Public names + theme variable groups + invariants
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/bleeper/ui/
├── theme.py        # NEW: palette, STATUS_COLORS, THEME, CSS, WAVEFORM, color_status()
├── app.py          # EDIT: drop THEME; WAVEFORM on 4 gr.Audio; wrap table postprocess; docstring
└── __main__.py     # EDIT: import THEME, CSS from theme; launch(..., css=CSS)

tests/unit/
└── test_ui_theme.py  # NEW: invariants 1–5 from contracts/theme.md

docs/
└── ui-screenshot.png # NEW: < 500 KB

README.md            # EDIT: screenshot in "Web UI" section
```

**Structure Decision**: Single project, existing layout. The theme sits beside `app.py` in the UI
package; nothing outside `src/bleeper/ui/`, tests, README and `docs/` changes.

## Implementation Notes

1. **Status coloring** wraps the table *instance's* `postprocess` (R3). Don't subclass
   `gr.Dataframe`: Gradio's metaclass writes `.pyi` files at import. After wrapping, recompute
   the initial value so the first paint is colored, e.g. assign `table.value` from the wrapped
   `postprocess(render_table(store))` (confirm the attribute shape against the component config
   during implementation; `demo.load` re-renders anyway as a fallback).
2. **`_dark` twins**: build the `.set()` kwargs from a `{name: value}` dict and expand it with both
   `name` and `f"{name}_dark"`. This keeps the call short and makes invariant 2 true by
   construction.
3. **Launcher**: `THEME` is still imported inside the `try` that guards the missing-Gradio case.
   `test_launch_is_local_and_offline` reads `kwargs["theme"]` only, so adding `css` is safe.
4. **Screenshot**: capture after running a few jobs. Compress (e.g. `pngquant` or macOS Preview
   export) to under 500 KB.

## Complexity Tracking

No constitution violations to justify.
