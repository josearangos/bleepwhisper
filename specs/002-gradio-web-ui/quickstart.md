# Quickstart & Validation: Bleeper Web UI

Validation guide proving Feature 2 works end to end. Interfaces are in
[contracts/ui.md](contracts/ui.md) and [contracts/core-additions.md](contracts/core-additions.md);
job fields and states are in [data-model.md](data-model.md).

## Prerequisites

- Feature 1 setup (Python ≥ 3.10, `uv`, `ffmpeg` on `PATH`), plus the `small` model downloaded
  once for the manual checks.
- Short test inputs: `samples/` has example audio and a words file (not committed beyond the
  examples).

## Setup

```bash
uv pip install -e ".[dev,ui]"
bleeper-ui --help
```

## 1. Quality gates (offline, no model)

```bash
ruff format --check . && ruff check .
pytest                    # includes store, worker, submission, parity and app-build tests
```

Expected: all pass with no network access and no Whisper model.

## 2. Automated acceptance checks (in the default `pytest` run)

| Check | Proves |
|-------|--------|
| Two jobs submitted back to back with a slow fake transcriber: the second is `queued` while the first is `running`; both end `done` in order | SC-002, FR-011 |
| Worker and CLI `main()` on the same inputs with the same fake transcriber produce byte-identical WAV and JSON | SC-003, FR-012 |
| Each invalid submission (no audio, wrong type, > 100 MB, > 30 min, no/empty/non-UTF-8 words, bad mask) raises with the contract message and leaves the store unchanged | SC-004, FR-008/009 |
| A store saved and reloaded keeps all jobs; queued/running jobs become `failed` (interrupted); a corrupt file gives an empty store and a notice | FR-022/023 |
| A failing job doesn't stop the next one; input copies are gone after done and failed jobs | FR-015, FR-024, SC-009 |
| One transcriber instance is used for all jobs | FR-014 |
| Deleting a running job raises `JobBusyError`; deleting a queued job means it never runs | FR-021 |
| Submit handler returns in < 1 s while a job is running | SC-001, FR-010 |
| `build_app()` constructs the Blocks without launching | smoke |

## 3. Manual end-to-end check (real model)

1. `bleeper-ui --data-dir /tmp/bleeper-ui-check` and open the printed address.
2. Play each preset preview: about 1 s each, audible, no clicks.
3. Upload `samples/prueba_parcero.wav`, choose Spanish, upload `samples/groserias_colombianas.txt`,
   keep Classic beep, then click **Mask audio**. The confirmation appears at once.
4. Immediately submit `samples/mi_audio.wav` the same way. The table shows the first job `running`
   with rising progress and the second `queued`.
5. When the first is `done`, select it, press play, and wait while the table refreshes a few times:
   playback isn't interrupted. Download both files.
6. Compare with the CLI:
   ```bash
   bleeper samples/prueba_parcero.wav --words samples/groserias_colombianas.txt --preset beep \
     --lang es -o /tmp/cli_masked.wav
   cmp /tmp/cli_masked.wav ~/Downloads/prueba_parcero_masked.wav
   cmp /tmp/cli_masked.json ~/Downloads/prueba_parcero_masked.json
   ```
   Expected: no output (identical).
7. Reload the browser tab: both jobs are still listed with working downloads.
8. Submit with an empty `.txt`: an error appears and no job is added. Submit with no audio: same.
9. Stop the UI with Ctrl+C while a job runs, then start it again: finished jobs are back, and the
   interrupted one is `failed` with the "Interrupted" message.
10. Delete a done job: it disappears and `/tmp/bleeper-ui-check/jobs/<id>/` is gone.
11. Check `/tmp/bleeper-ui-check/jobs/*/`: no `input.*`, `words.txt` or `mask.*` remain for
    finished jobs.
