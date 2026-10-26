# UI Contract: `bleeper-ui`

## Launch

```text
bleeper-ui [--port PORT] [--data-dir DIR]
python -m bleeper.ui [--port PORT] [--data-dir DIR]
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--port` | `7860` | Local port to listen on |
| `--data-dir` | `$BLEEPER_UI_DATA` or `~/.bleeper/ui` | Where `jobs.json` and job files live (created if missing) |

- Binds to `127.0.0.1` only, with no share link and no analytics. Gradio's cache is
  `<data-dir>/tmp` (`GRADIO_TEMP_DIR`), emptied at start-up. It prints
  `Bleeper UI running at http://127.0.0.1:<port>` and runs until Ctrl+C.
- If Gradio isn't installed, it exits with code 1 and prints:
  `error: the web UI needs Gradio. Install it with: pip install "bleeper[ui]"`.
- If the port is in use, it exits with code 1 and asks for a different `--port`.
- Model and padding are fixed to the CLI defaults (`small`, 80 ms).

## Form

| Control | Component | Values |
|---------|-----------|--------|
| Audio | `gr.File`, `.wav` `.mp3`, label `Audio (.wav or .mp3, max 100 MB, 30 min)` | required |
| Language | `gr.Dropdown` | Auto (default), Spanish, English, Portuguese, French, German, Italian |
| Forbidden words | `gr.File`, `.txt` | required; CLI format |
| Mask | `gr.Radio` + one `gr.Audio` preview per preset | Classic beep (default), Low tone, Noise burst |
| Custom mask | `gr.File`, `.wav` `.mp3` | optional; overrides the preset |
| Mask audio | `gr.Button` | submits |
| Status | `gr.Markdown` under the button | confirmation or error |

**Submit result** (always within 1 s; it never waits for processing):

- Success: `✅ Job <id> queued: <filename> (<N> forbidden words, mask: <mask>).` The table
  refreshes immediately. The uploaded files are deleted from Gradio's cache and the three upload
  fields are cleared; language and preset keep their values.
- Failure: `❌ <message>` and no job is created. The uploads stay in the form, so the user can fix
  one field and submit again. Messages, in check order:

| Condition | Message |
|-----------|---------|
| No audio | `Please upload an audio file (.wav or .mp3).` |
| Wrong audio type | `Unsupported audio format '<ext>'. Use a .wav or .mp3 file.` |
| > 100 MB (up to the 110 MB upload guard) | `'<name>' is <X.X> MB; the limit is 100 MB. Trim or compress the file and try again.` |
| > 110 MB | Gradio's own upload error (the file is never stored); see the spec's edge cases |
| Unreadable audio | core `probe_audio` message |
| Duration 0 | `'<name>' contains no audio. Check the file.` |
| > 30 min | `'<name>' is <M:SS> long; the limit is 30:00. Split the file and try again.` |
| No words file | `Please upload a forbidden words file (.txt, one word or phrase per line).` |
| Empty / not UTF-8 | core `load_words` message, with the file's display name |
| Bad custom mask | core `probe_audio` message, prefixed `Custom mask: ` |

## Jobs table

A `gr.Dataframe` (read-only, newest first), refreshed every 2 s and on page load.

| Column | Content |
|--------|---------|
| ID | job id |
| File | original file name |
| Language | label |
| Mask | `beep` / `tone` / `noise` / `custom: <name>` |
| Status | `queued` / `running` / `done` / `failed` |
| Progress | `NN%` |
| Masked | count (done jobs), otherwise empty |
| Created | `YYYY-MM-DD HH:MM:SS` |
| Finished | `YYYY-MM-DD HH:MM:SS` or empty |
| Error | message (failed jobs), otherwise empty |

When there are no jobs, it shows the hint "No jobs yet. Submit an audio file above." If the jobs file
was corrupt at start-up, a one-time notice appears above the table.

## Job details panel

Selecting a row opens the panel for that job (the selection is per browser tab). The job is
identified by the row's ID cell, not by its position, so a refresh or a new job between rendering
and clicking can't open the wrong job. Clicking the "No jobs yet" hint row does nothing.

| Job status | Panel shows |
|------------|-------------|
| none selected | "Select a job in the table to see its result." |
| `queued` / `running` | Summary (status, progress); Delete enabled only for `queued`; for `running`, the note "This job can be deleted once it finishes." |
| `done` | Player with the masked WAV; download `<stem>_masked.wav`; download `<stem>_masked.json`; "N masked words"; Delete |
| `done`, files missing | "The result files for this job are no longer available."; Delete |
| `failed` | Error message; Delete |

- The panel re-renders only when the selected job's id or status changes. The table refresh never
  resets the player.
- Delete removes the job and its directory, clears the panel and refreshes the table. If the job
  started running in the meantime, the panel shows the refusal note and the job stays.
