# Research: Run Bleeper Anywhere with Docker

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-10-27

Current state that drives these decisions (read from the code on 2026-10-27):

- `bleeper.core.transcribe.load_model` tries `local_files_only=True` first and falls back to a
  download; its error message says "connect to the internet once".
- The UI hard-codes `HOST = "127.0.0.1"` (`ui/__main__.py`), `MODEL = "small"` and
  `MAX_BYTES = 100 MB` (`ui/submit.py`), `max_file_size="110mb"` (`ui/__main__.py`) and the label
  "max 100 MB" (`ui/app.py`). `BLEEPER_UI_DATA` already selects the data dir.
- `JobStore.load()` already marks queued/running jobs as failed ("interrupted") on start-up, so the
  container-restart edge case needs no new code.
- ffmpeg is invoked as a subprocess for mp3 decoding and mask resampling (`core/audio_io.py`).
- Local versions: faster-whisper 1.2.1, ctranslate2 4.8.4, gradio 6.30.0; `uv` is installed.

---

## R1. Base image and its pin

- **Decision**: `python:3.11-slim-trixie`, pinned as `python:3.11.<patch>-slim-trixie@sha256:<digest>`
  in a single `ARG PYTHON_IMAGE` at the top of the Dockerfile. The exact patch and digest are
  resolved at implementation time with `docker buildx imagetools inspect python:3.11-slim-trixie`.
- **Rationale**: The spec mandates 3.11 slim. A tag alone can be re-pushed; the digest makes the
  base byte-identical across builds while the tag stays human-readable. Trixie (Debian 13) is the
  current Debian release, so ffmpeg comes from a supported archive.
- **Alternatives**: Alpine (musl breaks the ctranslate2/onnxruntime wheels); `python:3.11` full
  (~1 GB larger); a distroless image (no apt for ffmpeg, no shell for the healthcheck).

## R2. Lock file

- **Decision**: `requirements.lock`, generated with
  `uv pip compile pyproject.toml --extra ui --universal --python-version 3.11 --generate-hashes -o requirements.lock`.
  The image installs it with `pip install --require-hashes --no-deps -r requirements.lock`, then
  installs the project itself with `pip install --no-deps .`. A `scripts/lock.sh` wraps the
  compile command so regenerating is one step.
- **Rationale**: `--universal` produces one file valid for both linux/amd64 and linux/arm64 (Apple
  Silicon); hashes make tampered or re-uploaded wheels fail the build; `--no-deps` guarantees nothing
  outside the lock is resolved. `uv` is already the documented dev tool and is never installed in the
  image, so no runtime dependency is added (Principle VII).
- **Alternatives**: `pip-tools` (one more dev tool, platform-specific output); `uv.lock` + `uv sync`
  (would require `uv` inside the build stage — acceptable but adds a tool to the image recipe for no
  gain); Poetry (new project tooling).

## R3. Baking the Whisper model and staying offline

- **Decision**: In a `model` build stage, set `HF_HOME=/opt/hf` and run
  `python -c "from faster_whisper import download_model; download_model('${WHISPER_MODEL}')"`,
  then copy `/opt/hf` into the runtime stage (world-readable). The runtime stage sets
  `HF_HOME=/opt/hf`, `HF_HUB_OFFLINE=1`, `BLEEPER_MODEL=${WHISPER_MODEL}`.
- **Rationale**: Using the Hugging Face cache layout means the existing name-based load
  (`WhisperModel("small", local_files_only=True)`) finds the model with no code change.
  `HF_HUB_OFFLINE=1` makes huggingface_hub refuse any network call, so `--network none` cannot hang
  or retry. A separate stage keeps the download cacheable independently of source changes.
- **Error for a non-baked model** (spec edge case): `load_model` is changed so that when the
  `HF_HUB_OFFLINE` environment variable is truthy (read directly, so `core` doesn't import
  huggingface_hub) it raises `ProcessingError` saying the model is not available
  offline and how to rebuild (`docker compose build --build-arg WHISPER_MODEL=<name>`), instead of
  the "connect to the internet" hint. This is an error-message change only; no audio logic moves.
- **Alternatives**: `download_model(..., output_dir=/opt/models/small)` + passing a path (would force
  every caller to know the path and break `--model small`); downloading on first run into a volume
  (violates "fully offline" and SC-003).

## R4. Image layout and size

- **Decision**: Three stages: `builder` (venv at `/opt/venv` from the lock), `model` (reuses the
  builder venv to download the model), `runtime` (`python` slim + `apt-get install
  --no-install-recommends ffmpeg`, copies `/opt/venv` and `/opt/hf`, no pip cache, no build tools).
- **Estimate**: base ~150 MB + ffmpeg and libs ~250 MB + venv (ctranslate2, onnxruntime, av,
  tokenizers, gradio and its deps) ~550 MB + `small` model ~480 MB ≈ 1.4 GB < 2 GB (FR-008).
  The smoke script asserts the size so drift is caught.
- **Alternatives**: static ffmpeg binary (smaller but an unpinned download from a third party);
  separate CLI and UI images (spec requires a single Dockerfile/image; Gradio is ~150 MB).

## R5. Non-root user and file ownership

- **Decision**: `useradd --uid 1000 --gid 1000 --create-home bleeper`; `USER 1000:1000`.
  `/opt/venv` and `/opt/hf` are root-owned but world-readable, so any UID can run the tool.
  `/var/lib/bleeper` (UI data) is created and owned by 1000 in the image, so a fresh named volume
  inherits that ownership. The `cli` service sets `user: "${BLEEPER_UID:-1000}:${BLEEPER_GID:-1000}"`; the `ui`
  service stays at 1000 (it writes only to its named volume). `HOME=/tmp` is set for the `cli`
  service so an arbitrary UID has a writable home.
- **Rationale**: Clarification Q1. Docker Desktop (macOS/Windows) maps bind-mount ownership itself,
  so only Linux users with UID ≠ 1000 need the override. The override variables are named
  `BLEEPER_UID`/`BLEEPER_GID`, not `UID`/`GID`: `UID` is read-only in bash (and special in zsh) and
  is not exported, so `UID=$(id -u) docker compose …` fails. The README shows
  `BLEEPER_UID=$(id -u) BLEEPER_GID=$(id -g) docker compose run …` or an `.env` file.
- **Alternatives**: build-time UID args (one image per user; breaks "build once"); `gosu`/entrypoint
  chown (runs as root at start; extra binary).

## R6. Configuration via environment

- **Decision**: A small interface-layer module `src/bleeper/settings.py` (not in `core`) reads, at
  call time, with validation:

  | Variable | Default (native) | Image default | Used by |
  |----------|------------------|---------------|---------|
  | `BLEEPER_MODEL` | `small` | `${WHISPER_MODEL}` | CLI `--model` default, UI worker |
  | `BLEEPER_UI_HOST` | `127.0.0.1` | `0.0.0.0` | UI launcher |
  | `BLEEPER_UI_PORT` | `7860` | `7860` | UI launcher (`--port` default) |
  | `BLEEPER_UI_MAX_UPLOAD_MB` | `100` | `100` | UI validation, Gradio `max_file_size` (+10 MB slack, as today), upload label |
  | `BLEEPER_UI_DATA` (exists) | `~/.bleeper/ui` | `/var/lib/bleeper` | UI launcher |

  Invalid values (non-integer port, port outside 1–65535, upload MB < 1) exit with code `1` and a
  message naming the variable and the accepted range.
- **Rationale**: FR-014/FR-015: unchanged native behavior when unset. One module keeps env parsing
  out of `core` (Principle I) and out of three scattered files.
- **Alternatives**: Gradio's own `GRADIO_SERVER_NAME`/`GRADIO_SERVER_PORT` (ignored because the app
  passes `server_name`/`server_port` explicitly, and they cannot drive our validation limit).

## R7. Compose services, health check and signals

- **Decision**:
  - Both services `build: .` and share `image: bleeper:local`; `init: true` (tini from Docker) so
    Ctrl-C/stop is delivered promptly.
  - Image `ENTRYPOINT ["bleeper"]`, `CMD ["--help"]`. `cli` uses it as-is (`profiles: ["cli"]` so
    `docker compose up` doesn't start it), mounts `./data:/data`. `ui` overrides
    `entrypoint: ["bleeper-ui"]`, `ports: ["127.0.0.1:${BLEEPER_UI_HOST_PORT:-7860}:7860"]`,
    volume `bleeper-ui-data:/var/lib/bleeper`, `restart: unless-stopped`.
  - Healthcheck (no curl in slim): `python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/' % os.environ.get('BLEEPER_UI_PORT','7860'), timeout=3)"`,
    `interval: 15s`, `timeout: 5s`, `start_period: 60s`, `retries: 3`.
- **Rationale**: Matches FR-010–FR-013 and the documented example command verbatim. The port binding
  to `127.0.0.1` is what makes the UI unreachable from the LAN (SC-005), independent of the
  in-container `0.0.0.0` bind.
- **Alternatives**: `HEALTHCHECK` in the Dockerfile (would also fire for one-shot CLI containers);
  installing curl (+ size, + package).

## R8. Smoke test speech source and checks

- **Decision**:
  - TTS: `docker run --rm -v "$WORK:/work" debian:trixie-slim@sha256:<digest> sh -c "apt-get update
    && apt-get install -y --no-install-recommends espeak-ng && espeak-ng -v en-us -s 140 -w
    /work/input.wav 'The quick brown fox jumps over the lazy dog.'"` — known word **`fox`**,
    `--lang en`. Clarification Q3.
  - Masking: `docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$WORK:/data"
    bleeper:smoke /data/input.wav --words /data/words.txt --preset beep --lang en -o /data/output.wav`.
  - Checks run in the same image (`--entrypoint python`, `--network none`) with a small
    `scripts/smoke_check.py` using numpy + soundfile already in the image: (a) output exists;
    (b) same frames, sample rate, channels; (c) report has a span whose word normalizes to `fox`;
    (d) output differs from input inside that span; plus (e) image size < 2 GB via
    `docker image inspect`. Clarification Q2. Each failure prints `FAIL: <check>` and exits 1.
  - `set -euo pipefail`, a `trap` removes the temp dir, `SMOKE_IMAGE` (default `bleeper:smoke`) and
    `SMOKE_BUILD_ARGS` (extra args for `docker buildx build`, used by CI for the GHA cache) are the
    only knobs.
- **Risk & mitigation**: espeak's voice is robotic. "The quick brown fox…" is the most common English
  test sentence; Whisper `small` with `--lang en` must transcribe "fox" — verify once during
  implementation. If it does not, slow the voice (`-s 120`) and/or use a pangram with a longer known
  word (e.g. "elephant"); the known word is a single variable in the script.
- **Alternatives**: committed fixture / existing sample (rejected in Q3).

## R9. CI workflow

- **Decision**: `.github/workflows/docker-smoke.yml`, `on: [push, pull_request]`, `ubuntu-latest`
  (x86), `docker/setup-buildx-action`, then `SMOKE_BUILD_ARGS="--cache-from type=gha --cache-to
  type=gha,mode=max --load" scripts/smoke.sh`. Actions pinned by major version; `permissions:
  contents: read`; nothing pushed. README badge points at this workflow. Clarification Q4.
- **Rationale**: The runner's UID is 1001, so CI exercises the UID override path from Q1 for free.
  The GHA cache keeps the model layer warm, so repeat runs skip the ~480 MB download.
- **Alternatives**: duplicate build steps in YAML (two sources of truth with `smoke.sh`).

## R10. Build context

- **Decision**: `.dockerignore` as an allow-list: `*`, then `!pyproject.toml`, `!README.md`
  (setuptools reads it as `readme`), `!requirements.lock`, `!src/`, and re-exclude
  `**/__pycache__`, `**/*.egg-info`.
- **Rationale**: Robust to new untracked files (audio in `samples/`, `out/`, `.venv`, `.git`,
  `.specify`, `data/`) — nothing enters the context unless named. Context stays < 1 MB.
- **Alternatives**: deny-list (silently grows as people add files).
