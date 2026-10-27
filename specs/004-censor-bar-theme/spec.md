# Feature Specification: "Censor Bar" Dark Theme for the Web UI

**Feature Branch**: `004-censor-bar-theme`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Give the bleeper Gradio UI its own visual identity, a dark \"Censor bar\" theme, replacing the default orange Gradio look. This is a visual-only change: no behavior, layout or audio logic may change. User story: As a visitor of my portfolio, I want the app to look distinctive and polished, so it does not look like a default Gradio demo. Palette: background #0F1115, cards/blocks #181B22, text #E8EAED, primary accent #C6FF3D with dark text #0F1115 on top (primary button, selected mask preset, done status, waveform progress), running #FFB800, failed #FF4D4D, queued #8A93A3. Theme in one module (bleeper/ui/theme.py) built with gr.themes.Base and .set(...), colors defined once as constants; dark by default in both light and dark system modes; \"Mask audio\" is the main call to action in lime; Status column colored by status and always readable as text; preset waveform previews use lime progress; keep English labels and layout; system font stack, no remote fonts or CDN assets; WCAG AA 4.5:1 text contrast; short screenshot in the README. Out of scope: logo or branding images, new components, layout changes, light theme toggle, animations. Acceptance: dark palette with no orange left; status shown with color and text; renders correctly with no internet; existing UI tests and end-to-end flow pass unchanged; colors changed in one place only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A distinctive dark look on first open (Priority: P1)

A visitor opens Bleeper from the author's portfolio. Instead of the stock light-and-orange demo
look, they see a dark "censor bar" interface: near-black page, slightly lighter cards, light text,
and one sharp lime accent on the main "Mask audio" call to action and on the selected mask preset.
Everything else — labels, controls, order of sections — is exactly where it was before.

**Why this priority**: This is the whole point of the feature: the first impression of the
portfolio piece. On its own it already removes the "default demo" look.

**Independent Test**: Open the UI in a browser set to light system mode and again in dark system
mode; in both cases the page shows the dark palette, the "Mask audio" button is lime with dark
text, the selected mask preset is highlighted in lime, and no orange appears anywhere.

**Acceptance Scenarios**:

1. **Given** a browser whose system preference is light mode, **When** the visitor opens the UI,
   **Then** the page background, cards and text use the dark palette (not a light variant).
2. **Given** a browser whose system preference is dark mode, **When** the visitor opens the UI,
   **Then** the page looks identical to the light-mode case.
3. **Given** the UI is open, **When** the visitor looks at the form, **Then** "Mask audio" is the
   most prominent control, filled with lime and labelled in dark text.
4. **Given** the mask preset choice is shown, **When** the visitor selects a preset, **Then** the
   selected option is marked with the lime accent and the others are not.
5. **Given** the UI is open, **When** the visitor inspects every visible control (buttons, inputs,
   radio, dropdown, file drops, table, audio players, focus outlines, links), **Then** none of them
   shows the default orange accent.
6. **Given** the UI before and after this change, **When** the two are compared side by side,
   **Then** every label, section, control and their order are unchanged.

---

### User Story 2 - Job status readable at a glance (Priority: P2)

A visitor submits an audio file and watches the jobs table. Each job's status is shown as its word
("queued", "running", "done", "failed") and is also tinted with a matching color: gray for queued,
amber for running, lime for done, red for failed. Someone who cannot distinguish the colors still
reads the status from the text.

**Why this priority**: The jobs table is where the visitor spends time waiting; color makes
progress scannable, but it builds on the base theme from Story 1.

**Independent Test**: Populate the jobs table with one job in each of the four statuses and verify
each Status cell shows the status word in its assigned color, with readable contrast.

**Acceptance Scenarios**:

1. **Given** a job in each status, **When** the table is displayed, **Then** the Status cells show
   "queued" in gray, "running" in amber, "done" in lime and "failed" in red.
2. **Given** any Status cell, **When** color is ignored (e.g. grayscale view), **Then** the status
   is still identifiable from its text alone.
3. **Given** a job changes status while the table refreshes, **When** the next refresh happens,
   **Then** the cell's color changes together with its text.
4. **Given** the table shows only the "No jobs yet" hint row, **When** it is displayed, **Then**
   it uses the normal text color and no status color.

---

### User Story 3 - Themed audio previews (Priority: P3)

When the visitor plays the preview of each of the three mask presets, the waveform's played
portion is drawn in the lime accent, consistent with the rest of the interface.

**Why this priority**: A finishing touch; it matters for polish but the app is already distinctive
without it.

**Independent Test**: Play each of the three preset previews and confirm the progress portion of
the waveform is lime, not orange.

**Acceptance Scenarios**:

1. **Given** the three preset previews, **When** the visitor plays one, **Then** the played part of
   its waveform is lime.
2. **Given** a finished job is selected, **When** its masked audio player is shown, **Then** its
   waveform follows the same theme (no orange).

---

### User Story 4 - The look is documented (Priority: P3)

A recruiter reading the repository README sees a short screenshot of the themed UI before running
anything.

**Why this priority**: Showcases the result on the portfolio without requiring a run.

**Independent Test**: Open the README and confirm it contains one screenshot of the themed UI that
loads from the repository itself.

**Acceptance Scenarios**:

1. **Given** the README, **When** it is rendered, **Then** a screenshot of the dark UI appears in
   the UI section, stored in the repository (not hotlinked).

---

### Edge Cases

- The visitor's browser or operating system is in light mode: the UI must still be dark, with no
  light-colored panels or white inputs leaking through.
- The machine has no internet connection (including the Docker image run with no network): the UI
  must render fully with its fonts and styles, and make no failed font or stylesheet requests.
- Disabled controls (e.g. "Delete job" while a job is running) must remain visibly disabled and
  their text must stay readable.
- The destructive "Delete job" button must not look like the lime call to action; it uses the red
  "failed" color family so the main action stays unique.
- Error and success messages after submitting (e.g. "❌ …", "✅ Job … queued") must stay readable
  on the dark background.
- Long error text in the table's Error column wraps and stays readable on the dark cards.
- Keyboard focus outlines must remain visible against the dark background and must not be orange.
- Text placed on top of a status or accent color (e.g. the lime button) must use the dark text
  color so it meets contrast.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The UI MUST use this palette: page background #0F1115; cards/blocks #181B22; main
  text #E8EAED; primary accent #C6FF3D with text #0F1115 on top of it; running #FFB800; failed
  #FF4D4D; queued #8A93A3.
- **FR-002**: The UI MUST render in the dark palette regardless of the visitor's system light or
  dark preference; every themed value MUST have the same dark value in both modes.
- **FR-003**: No element of the UI MUST display the default orange accent; every place that used
  it (primary button, selected radio/checkbox, focus rings, slider/progress, links, loaders,
  waveform progress) MUST use the lime accent or a neutral palette color instead.
- **FR-004**: The "Mask audio" button MUST be styled as the single main call to action: lime fill
  with dark (#0F1115) text, including its hover and active states.
- **FR-005**: The selected mask preset MUST be highlighted with the lime accent.
- **FR-006**: Each Status cell in the jobs table MUST show the status word in its assigned color:
  done = lime, running = amber, failed = red, queued = gray. The status word MUST always be
  present so status is never conveyed by color alone.
- **FR-007**: The waveform progress of the three mask preset previews MUST use the lime accent.
- **FR-008**: The "Delete job" (destructive) button MUST use the failed/red color family, not the
  lime accent.
- **FR-009**: All text MUST meet WCAG AA contrast (at least 4.5:1) against the background it is
  drawn on, including status-colored text on cards and dark text on the lime accent.
- **FR-010**: The UI MUST use the operating system's font stack and MUST NOT request any remote
  font, stylesheet or other asset from a CDN or external host.
- **FR-011**: All colors MUST be defined exactly once, as named constants in a single theme
  module; the rest of the UI MUST reference that module rather than repeating color values.
- **FR-012**: The change MUST be visual only: labels (in English), layout, component set, event
  behavior, job processing and audio output MUST remain unchanged.
- **FR-013**: The README MUST include one short screenshot of the themed UI, stored in the
  repository.

### Key Entities

- **Palette**: The named set of seven colors (background, card, text, accent with its on-accent
  text, and the three non-done status colors) — the single source of truth for every color shown.
- **Status color mapping**: The association of each job status (queued, running, done, failed) to
  one palette color, applied to the Status cell alongside its text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Opening the UI in both light and dark system modes shows the dark palette, with 0
  orange-colored elements found on visual inspection of every section.
- **SC-002**: 100% of the four job statuses display both their word and their assigned color in
  the jobs table.
- **SC-003**: With network access disabled, the UI loads completely with 0 failed or blocked
  font, stylesheet or CDN requests.
- **SC-004**: 100% of the existing automated UI tests and the end-to-end flow (submit a job, wait
  for it, download the masked audio and report) pass without any modification to those tests.
- **SC-005**: Every text/background pair in the palette has a contrast ratio of at least 4.5:1
  (lowest expected pair: red text on cards, about 5.3:1).
- **SC-006**: Changing any palette color requires editing exactly 1 location in the codebase.
- **SC-007**: A first-time visitor identifies "Mask audio" as the main action within 5 seconds of
  opening the page.

## Assumptions

- The theme module location requested by the user (`bleeper/ui/theme.py`) refers to the existing
  UI package (`src/bleeper/ui/theme.py`), and the theme is built on the UI framework's neutral
  base theme with variable overrides, as the user specified.
- Contrast of the given palette was checked: all text/background pairs pass AA (main text on
  background 15.7:1, lime on cards 14.6:1, amber on cards 9.9:1, gray on cards 5.6:1, red on cards
  5.3:1, dark text on lime 16.0:1). No palette color needs adjusting.
- Color is applied only to the text of the Status cell (not the whole row) to keep the table calm
  and avoid new contrast pairs.
- The masked-result audio player follows the same theme as the preset previews, since leaving it
  orange would violate "no orange left".
- Secondary buttons (downloads) use neutral card/border colors so that "Mask audio" is the only
  lime filled button.
- The screenshot is a single compressed image of reasonable size (well under 500 KB), consistent
  with the constitution's rule against committing large files.
- No new runtime dependency is introduced; the existing UI framework is sufficient.
- Out of scope: logo or branding images, new components, layout changes, a light-theme toggle,
  and animations.
