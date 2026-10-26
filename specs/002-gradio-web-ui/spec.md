# Feature Specification: Bleeper Web UI — Background Masking Jobs in the Browser

**Feature Branch**: `002-gradio-web-ui`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Add a Gradio web UI to bleeper that reuses bleeper.core.process_audio.
Do not duplicate any audio logic. Launch with `bleeper-ui` (or `python -m bleeper.ui`), runs
locally. As a content creator, I upload an audio file, choose a language, upload my forbidden words
and pick a mask sound, then click a button. The job runs in the background and I see all my
requests in a list, with the result ready to download when done. [Form: audio upload (wav, mp3);
language dropdown (Auto, Spanish, English, Portuguese, French, German, Italian); forbidden words
.txt upload in the CLI format, validated on submit; mask selector with 3 built-in presets (classic
beep, low tone, noise burst) each with a preview player, plus an optional custom mask upload that
overrides the preset; a "Mask audio" button that validates, creates a job and returns immediately.
Background jobs: single worker, FIFO, one job at a time; each job stores id, original filename,
language, mask used, status (queued, running, done, failed), progress percent, created and finished
time, error message; jobs table auto-refreshes every 2 s and survives a page refresh (in-memory,
optionally persisted to a local JSON file); done jobs show a player, audio and report downloads and
the masked-word count; failed jobs show a readable error; jobs can be deleted; the speech model is
loaded once and reused. Limits: 100 MB or 30 minutes per upload. Out of scope: authentication,
multi-user, database, cloud deployment, video, real-time processing.]"

## Clarifications

### Session 2026-10-26

- Q: Should the jobs list survive restarting the UI, or only a browser refresh? → A: Persist to a
  local JSON file; after a restart finished jobs and downloads return, and jobs that were queued or
  running are marked "failed" as interrupted.
- Q: How should a finished job's player and downloads appear given the 2-second refresh? → A: A
  compact auto-refreshing jobs table; selecting a row opens a job details panel with the player,
  both downloads and Delete; the table refresh does not interrupt the panel.
- Q: What happens when the user tries to delete a running job? → A: Refused; Delete is unavailable
  for a running job, with a note that it can be deleted once it finishes. There is no cancellation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit a masking job and download the result (Priority: P1)

A content creator starts the web UI on their own computer and opens it in a browser. They upload a
recording, choose its language (or leave it on Auto), upload their forbidden-words file, pick one of
the built-in mask sounds and click "Mask audio". The form confirms the job was created right away.
The job appears in the jobs list, moves from "queued" to "running" with a progress percentage, and
ends as "done". The creator listens to the masked result in the page, sees how many words were
masked, and downloads the masked audio and the report.

**Why this priority**: This is the whole point of the UI: the CLI workflow without a terminal. One
job end to end is a usable MVP.

**Independent Test**: Launch the UI, submit one short recording containing a known forbidden word
with the "classic beep" preset, wait for "done", then download the audio and report and compare
them with the CLI output for the same inputs.

**Acceptance Scenarios**:

1. **Given** the UI is running, **When** the user submits a valid recording, words file and preset,
   **Then** the form returns a confirmation within 1 second and a new job appears in the list with
   status "queued" or "running".
2. **Given** a running job, **When** the user watches the list, **Then** its progress percentage
   updates at least every 2 seconds without reloading the page and never decreases.
3. **Given** a job that finished successfully, **When** the user looks at the jobs table, **Then**
   its row shows the number of masked words and the finish time; **when** they select it, **then**
   the job details panel shows an audio player with the masked result, a download for the masked
   audio, a download for the JSON report and a Delete action, and playback continues while the
   table refreshes.
4. **Given** the same recording, words file, language and mask, **When** processed once by the UI
   and once by the CLI (default model and padding), **Then** the masked audio and the report are
   identical.
5. **Given** a recording in which no forbidden word is spoken, **When** the job finishes, **Then**
   it is "done" with 0 masked words, and the downloadable audio equals the decoded input.

---

### User Story 2 - Queue several jobs while the UI stays responsive (Priority: P1)

The creator has several recordings. They submit one, then immediately submit another without
waiting. The second job waits as "queued" while the first runs; jobs are processed one at a time in
submission order. The page stays usable the whole time: they can preview masks, fill the form and
submit more jobs while processing happens.

**Why this priority**: Background, non-blocking processing is an explicit acceptance criterion and
a constitution requirement for the UI.

**Independent Test**: Submit two jobs back to back; confirm the second shows "queued" while the
first shows "running", that the form accepts a third submission meanwhile, and that both jobs end
"done" with downloadable results, in submission order.

**Acceptance Scenarios**:

1. **Given** a job is running, **When** the user submits a second job, **Then** the second appears
   as "queued" with 0% progress and the form responds within 1 second.
2. **Given** jobs A then B were submitted, **When** processing completes, **Then** A finishes
   before B starts, and both end "done" with downloadable audio and report.
3. **Given** a job fails, **When** later jobs are queued, **Then** they still run normally.
4. **Given** several jobs have run, **When** the second and later jobs run, **Then** the speech
   model is not reloaded, so they start transcribing without the initial model-loading delay.

---

### User Story 3 - Clear validation and error reporting (Priority: P2)

The creator makes mistakes: forgets the audio, uploads an empty words file, a file that is too
large or too long, or a recording the system cannot read. Mistakes detectable on submit are
reported next to the form and no job is created. Problems found only during processing turn the job
into "failed" with a readable explanation.

**Why this priority**: Required for trust and usability, but builds on the working job flow.

**Independent Test**: Submit each invalid input listed below and confirm an error message appears
and the jobs list does not change; submit a corrupt audio file that passes the upfront checks and
confirm the job ends "failed" with a readable message.

**Acceptance Scenarios**:

1. **Given** no audio file, **When** the user clicks "Mask audio", **Then** an error says an audio
   file is required and no job is created.
2. **Given** no words file, or a words file that is empty or contains only blank lines and `#`
   comments, **When** the user submits, **Then** an error says no forbidden words were found and no
   job is created.
3. **Given** a words file that is not valid UTF-8 text, **When** the user submits, **Then** an error
   says the file must be UTF-8 text and no job is created.
4. **Given** an audio file that is not WAV or MP3, **When** the user submits, **Then** an error
   lists the accepted formats and no job is created.
5. **Given** an audio file larger than 100 MB or longer than 30 minutes, **When** the user submits,
   **Then** an error states the limit that was exceeded and the file's actual size or duration, and
   no job is created.
6. **Given** a job whose processing fails (e.g., the speech model is unavailable, the audio cannot
   be decoded), **When** it stops, **Then** its status is "failed", it shows a readable message
   explaining what went wrong and how to fix it, and its finish time is set.

---

### User Story 4 - Choose and preview the mask sound (Priority: P2)

The creator listens to each of the three built-in mask sounds (classic beep, low tone, noise burst)
in the page before choosing one. Alternatively, they upload their own reference sound, which is
used instead of the selected preset.

**Why this priority**: Improves the result and matches the CLI's mask options, but the default
preset alone already delivers value.

**Independent Test**: Play each preset preview; submit one job with a preset and one with a custom
mask uploaded; confirm each job's "mask used" shows the right mask and its output matches the CLI
run with `--preset` or `--mask` respectively.

**Acceptance Scenarios**:

1. **Given** the form, **When** the user opens it, **Then** each of the three presets has a playable
   preview of about one second, and "classic beep" is selected by default.
2. **Given** a custom mask is uploaded and a preset is selected, **When** the user submits, **Then**
   the custom mask is used, and the job's "mask used" shows the custom file name.
3. **Given** a custom mask that is not a readable WAV or MP3, **When** the user submits, **Then** an
   error explains the problem and no job is created.

---

### User Story 5 - Keep and tidy the jobs list (Priority: P3)

The creator reloads the browser tab or closes and reopens it; the jobs list is still there with
current statuses and downloads. When they no longer need a job, they delete it and it disappears
from the list together with its files.

**Why this priority**: Convenience on top of the core flow; required by the acceptance criteria but
not needed to mask a single file.

**Independent Test**: Submit a job, reload the page, confirm the job and its downloads are still
listed; delete a finished job and confirm it and its result files are gone.

**Acceptance Scenarios**:

1. **Given** jobs in any status, **When** the user refreshes the page, **Then** the same jobs are
   listed with their current status and, for done jobs, working downloads.
2. **Given** the UI was stopped and started again, **When** the user opens the page, **Then**
   previously finished jobs are still listed with working downloads, and jobs that were queued or
   running when it stopped are shown as "failed" with a message saying they were interrupted.
3. **Given** a done, failed or queued job, **When** the user deletes it, **Then** it disappears from
   the list (a queued job will no longer run) and its stored files are removed.
4. **Given** a running job is selected, **When** the user looks at the job details panel, **Then**
   the Delete action is unavailable and a note says the job can be deleted once it finishes; the
   job keeps running to completion.

---

### Edge Cases

- Many jobs queued: all are listed with their status; order of execution is submission order.
- Two uploads with the same file name: each job keeps its own files; downloads never mix them up.
- Downloaded files are named after the original recording (e.g. `interview_masked.wav` and
  `interview_masked.json`) so the user can tell them apart.
- Audio exactly at the limit (100 MB or 30:00): accepted; anything above is rejected.
- Audio far above the size limit (over 110 MB): refused by the upload itself, before the file is
  stored, with a generic "file too large" message that doesn't show the actual size. The audio
  upload always shows "max 100 MB, 30 min", so the limit is visible before uploading. Files between
  100 MB and 110 MB get the full message with the actual size.
- Audio with zero duration or that cannot be inspected at submit time: rejected with a readable
  error.
- The user changes the form while a job runs: queued and running jobs keep the inputs they were
  submitted with.
- The jobs store file is missing or corrupt at start-up: the UI starts with an empty list and shows
  a notice instead of crashing.
- A done job whose result files were removed outside the UI: shown with a message that its files
  are no longer available, and it can still be deleted.
- The browser is closed while jobs run: processing continues; results are there when the page is
  reopened.
- Deleting a job while the list is refreshing: the job disappears and does not reappear.
- The selected job is deleted: the job details panel is cleared and shows that no job is selected.
- Playing a result while other jobs progress: the table refreshes, playback is not interrupted.

## Requirements *(mandatory)*

### Functional Requirements

**Launch & scope**

- **FR-001**: The UI MUST be launched with the `bleeper-ui` command or `python -m bleeper.ui`, and
  MUST print the local address to open in the browser.
- **FR-002**: The UI MUST be reachable only from the local machine by default and MUST make no
  network calls other than the one-time speech-model download already allowed for the CLI.
- **FR-003**: The UI MUST contain no audio logic of its own. All transcription, matching, masking,
  preset generation, decoding and report writing MUST come from the existing core package, which
  MUST be reused with unchanged behavior.

**Form**

- **FR-004**: The form MUST offer: an audio upload (WAV, MP3); a language selector with Auto
  (default), Spanish, English, Portuguese, French, German and Italian; a forbidden-words `.txt`
  upload; a mask selector with three presets (classic beep, low tone, noise burst), each with a
  preview player; an optional custom mask upload; and a "Mask audio" button.
- **FR-005**: Language choices MUST map to the CLI language options (Auto = automatic detection,
  Spanish = `es`, English = `en`, Portuguese = `pt`, French = `fr`, German = `de`, Italian = `it`).
  The three presets MUST map to the CLI presets `beep`, `tone` and `noise`.
- **FR-006**: The words file MUST follow the CLI format exactly: UTF-8, one word or phrase per line,
  blank lines and `#` comment lines ignored.
- **FR-007**: A custom mask, when provided, MUST override the selected preset.

**Submission & validation**

- **FR-008**: On "Mask audio", the system MUST validate synchronously, before creating a job: audio
  present and WAV/MP3; audio ≤ 100 MB and ≤ 30 minutes; words file present, UTF-8 and containing at
  least one usable entry; custom mask (if any) readable as WAV/MP3.
- **FR-009**: If validation fails, the system MUST show a readable error stating what is wrong and
  how to fix it, and MUST NOT create a job.
- **FR-010**: If validation passes, the system MUST create a job with status "queued", show a
  confirmation, and return control to the user within 1 second, without waiting for processing.

**Background processing**

- **FR-011**: Jobs MUST be processed by a single background worker, one at a time, in
  first-in-first-out order.
- **FR-012**: Each job MUST be processed with the same options the CLI would use for the same
  inputs (default model `small`, default padding 80 ms), so its masked audio and report are
  identical to the CLI's.
- **FR-013**: The job's progress percentage MUST be derived from the core's progress updates,
  MUST never decrease, and MUST reach 100% when the job is done.
- **FR-014**: The speech model MUST be loaded at most once per UI session and reused for every
  later job that uses the same model.
- **FR-015**: A failure in one job MUST set that job to "failed" with a readable message and MUST
  NOT stop the worker or affect other jobs.
- **FR-016**: Processing MUST NOT block the interface: while a job runs, the user MUST be able to
  preview masks, submit new jobs, view and delete other jobs.

**Jobs list**

- **FR-017**: Each job MUST record: id, original file name, language, mask used (preset name or
  custom file name), status (`queued`, `running`, `done`, `failed`), progress percent, created time,
  finished time (for done/failed) and error message (for failed).
- **FR-018**: The jobs table MUST show every job, newest first, with its original file name,
  language, mask used, status, progress percent, created and finished time, masked-word count (done
  jobs) and error message (failed jobs), and MUST refresh automatically every 2 seconds.
- **FR-019**: Selecting a job in the table MUST open a job details panel. For a done job the panel
  MUST show an audio player with the masked result, download actions for the masked audio and the
  JSON report, and the number of masked words (the number of report entries). The automatic table
  refresh MUST NOT interrupt playback or reset the panel; the panel updates when the selected job's
  status changes.
- **FR-020**: Failed jobs MUST show their error message in readable form in the table and in the job
  details panel.
- **FR-021**: From the job details panel the user MUST be able to delete a done, failed or queued job; deleting it MUST remove
  it from the list, stop it from running if queued, and delete its stored files. For a running job
  the Delete action MUST be unavailable, with a note that the job can be deleted once it finishes;
  running jobs cannot be cancelled.

**Persistence & files**

- **FR-022**: The jobs list MUST survive a page refresh and the browser being closed.
- **FR-023**: Job metadata MUST be saved to a local JSON file so the list survives restarting the
  UI; jobs that were queued or running at shutdown MUST be marked "failed" as interrupted on the
  next start.
- **FR-024**: Uploaded inputs and job results MUST be stored only in a local data directory; copies
  of uploaded inputs MUST be deleted once their job finishes (successfully or not); results MUST be
  kept until the job is deleted.
- **FR-025**: Audio content and transcripts MUST NOT be written to logs.

### Key Entities

- **Job**: One masking request and its lifecycle: id, original file name, language, mask used,
  status, progress percent, created time, finished time, error message, masked-word count, and the
  locations of its result audio and report.
- **Job Status**: One of `queued` → `running` → `done` | `failed`.
- **Job Queue**: Ordered list of queued jobs, consumed one at a time by the single worker.
- **Jobs Store**: The set of all jobs, kept in memory and mirrored to a local JSON file.
- **Mask Choice**: Either a built-in preset (classic beep, low tone, noise burst) or a custom
  uploaded sound; a custom sound overrides the preset.
- **Job Details Panel**: The view of one selected job; holds the result player, downloads and the
  Delete action, independent of the table refresh.
- **Result**: The masked audio and the JSON report produced by the core for a done job.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Clicking "Mask audio" with valid inputs shows a confirmation and the new job in the
  list within 1 second, regardless of how many jobs are queued or running.
- **SC-002**: When two jobs are submitted back to back, the second is shown as "queued" while the
  first is "running", and both finish "done" with working downloads, in 100% of trials.
- **SC-003**: For identical inputs, the UI's masked audio and report are byte-identical to the
  CLI's in 100% of test cases.
- **SC-004**: Every invalid input in User Story 3 (scenarios 1–5) shows an error and leaves the
  number of jobs unchanged in 100% of trials.
- **SC-005**: After a page refresh, 100% of previously listed jobs are shown with their current
  status and working downloads.
- **SC-006**: Status and progress changes appear in the jobs table within 2 seconds of happening,
  and playback in the job details panel is never interrupted by a table refresh.
- **SC-007**: For the second and later jobs in a session, no model-loading delay occurs; a
  1-minute recording finishes within the same time as the CLI on the reference machine (under 1
  minute, an Apple M-series laptop with 8 GB RAM).
- **SC-008**: A first-time user can submit a job and download its result without instructions in
  under 2 minutes (excluding processing time).
- **SC-009**: After a job is deleted, or after it finishes, no copies of its uploaded input remain on
  disk.

## Assumptions

- Single local user; no authentication, multi-user separation, database, cloud deployment, video or
  real-time processing (per the request and the constitution).
- The UI uses the CLI defaults for options it does not expose: model `small` and 80 ms padding.
  Exposing them in the UI is out of scope for this feature.
- "Masked words" means the number of masked spans in the report (merged neighbouring words count as
  one), matching what the CLI prints.
- Persistence to a local JSON file is required (confirmed in Clarifications); result files live in
  a local data directory next to it.
- Any audio inspection needed for upfront validation (e.g. reading the duration for the 30-minute
  limit) and the preset preview clips are provided by the core package, not implemented in the UI.
- Running jobs cannot be cancelled; only queued and finished jobs can be deleted.
- The 100 MB and 30-minute limits apply to the main audio upload; custom masks and words files are
  small by nature and only checked for readability.
- Gradio is the only new runtime dependency and is used only by the UI, as the constitution allows.
- Recognition accuracy depends on the speech model, as in Feature 1.
