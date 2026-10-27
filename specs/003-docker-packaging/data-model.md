# Data Model: Run Bleeper Anywhere with Docker

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This feature adds no new application data. Its "entities" are build and runtime artifacts; the
job and report formats are unchanged from features 001/002.

## Image `bleeper:<tag>`

| Attribute | Value / rule |
|-----------|--------------|
| Base | `python:3.11.<patch>-slim-trixie@sha256:…` (one `ARG PYTHON_IMAGE`) |
| Build arg `WHISPER_MODEL` | default `small`; any faster-whisper model name |
| Contents | `/opt/venv` (deps from lock + bleeper), `/opt/hf` (HF cache with the baked model), ffmpeg |
| User | `bleeper`, UID/GID 1000; image never switches back to root |
| Env | `PATH=/opt/venv/bin:…`, `HF_HOME=/opt/hf`, `HF_HUB_OFFLINE=1`, `BLEEPER_MODEL=$WHISPER_MODEL`, `BLEEPER_UI_HOST=0.0.0.0`, `BLEEPER_UI_PORT=7860`, `BLEEPER_UI_MAX_UPLOAD_MB=100`, `BLEEPER_UI_DATA=/var/lib/bleeper`, `GRADIO_ANALYTICS_ENABLED=False`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1` |
| Entrypoint | `["bleeper"]`, `CMD ["--help"]` |
| Labels | `org.opencontainers.image.source`, `…version` (= project version), `bleeper.whisper-model` |
| Size | < 2 GB with the default model (asserted by smoke test) |

Validation: `/opt/venv` and `/opt/hf` readable by any UID; `/var/lib/bleeper` owned by 1000.

## Lock file `requirements.lock`

- Generated from `pyproject.toml` with the `ui` extra, universal (amd64 + arm64), Python 3.11,
  with `--hash` lines for every package.
- Does not contain the `bleeper` project itself (installed separately with `--no-deps`).
- Rule: must be regenerated (`scripts/lock.sh`) whenever `pyproject.toml` dependencies change;
  the build fails on a missing hash.

## Data folder (`./data` on host ↔ `/data` in `cli`)

- Bind mount, created by the user (`mkdir -p data`). Compose is configured with `create_host_path: false` so it never creates it (on Linux that would make it root-owned); a missing folder stops the run before the container starts.
- Holds user inputs (`*.wav`, `*.mp3`, words files, custom masks) and outputs (`*.wav` + `*.json`).
- Files written by the container are owned by `${BLEEPER_UID:-1000}:${BLEEPER_GID:-1000}`.
- `data/` is git-ignored and excluded from the build context.

## UI volume `bleeper-ui-data` (↔ `/var/lib/bleeper` in `ui`)

- Named volume, initialized from the image directory (owner 1000).
- Contents are the existing UI layout: `jobs.json`, `jobs/<id>/…` (input, words, mask, output, report),
  `tmp/` (Gradio upload cache, wiped on start).
- Lifecycle: survives `docker compose down`/`up` and container re-creation; removed only by
  `docker compose down -v`. A missing/empty volume → UI starts with an empty job list.
- Job state transitions are unchanged; on start, `queued`/`running` jobs become `failed`
  ("interrupted") — existing `JobStore.load()` behavior.

## Settings (environment)

| Variable | Type / range | Native default | Invalid → |
|----------|--------------|----------------|-----------|
| `BLEEPER_MODEL` | non-empty string | `small` | empty → default |
| `BLEEPER_UI_HOST` | host/IP string | `127.0.0.1` | empty → default |
| `BLEEPER_UI_PORT` | int 1–65535 | `7860` | exit 1, message names variable |
| `BLEEPER_UI_MAX_UPLOAD_MB` | int ≥ 1 | `100` | exit 1, message names variable |
| `BLEEPER_UI_DATA` | path | `~/.bleeper/ui` | (existing behavior) |

Precedence: explicit CLI flag (`--model`, `--port`, `--data-dir`) > environment variable > default.

## Smoke run (transient)

`$WORK = mktemp -d` containing `input.wav` (espeak-ng, 22.05 kHz mono), `words.txt` (`fox`),
`output.wav`, `output.json`; deleted by `trap` on exit, success or failure.
