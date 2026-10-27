# Quickstart: Validate the "Censor Bar" Theme

## Prerequisites

- Repo venv with the UI extra: `uv pip install -e ".[dev]"`.
- A desktop browser with developer tools.

## 1. Automated checks (no network, no Whisper model)

```bash
ruff format --check && ruff check
pytest
```

Expected: everything passes, and `git diff main -- tests/integration tests/unit` shows **no changes
to existing test files** (only new `tests/unit/test_ui_theme.py`). Covers SC-004, SC-005, SC-006
and the invariants in [contracts/theme.md](contracts/theme.md).

## 2. Dark in both system modes, no orange (SC-001, User Story 1)

```bash
bleeper-ui --data-dir /tmp/bleeper-theme-check
```

1. Open http://127.0.0.1:7860 with the OS in **light** mode, then in **dark** mode (or use DevTools
   → Rendering → "Emulate prefers-color-scheme"). Both look identical and dark.
2. "Mask audio" is lime with dark text; hovering lightens it.
3. Click each mask preset: the selected radio is lime.
4. Tab through the controls: focus outlines are visible and not orange.
5. In DevTools console: `getComputedStyle(document.body).getPropertyValue('--color-accent')` →
   `#C6FF3D` (case may vary).

## 3. Status colors with text (SC-002, User Story 2)

1. Submit two or three short files (e.g. `samples/prueba_parcero.wav` with
   `samples/groserias_colombianas.txt`) quickly so one is **running** and others **queued**.
2. Status cells show `queued` (gray), `running` (amber), then `done` (lime).
3. To get `failed`, submit and stop the UI mid-run, then restart: the job shows `failed`
   ("Interrupted") in red.
4. DevTools → Rendering → "Emulate vision deficiency: achromatopsia": status is still readable
   from the words.

## 4. Waveforms (User Story 3)

Play each of the three previews and the masked result of a done job: the played part is lime.

## 5. Offline (SC-003)

1. Turn off Wi-Fi / network, restart `bleeper-ui`, reload with DevTools → Network open and
   "Disable cache" checked.
2. Expected: no failed (red) requests; no requests to `fonts.googleapis.com`, `fonts.gstatic.com`
   or any CDN.
3. Optional, with feature 003: run the UI container with no network access and repeat.

## 6. End-to-end flow unchanged (SC-004)

Submit a job, wait for `done`, select it, download the audio and the report: same files and
behavior as before the change.

## 7. README screenshot (User Story 4)

`docs/ui-screenshot.png` exists, is under 500 KB (`ls -lh docs/ui-screenshot.png`), and renders
in the README's "Web UI" section on GitHub.
