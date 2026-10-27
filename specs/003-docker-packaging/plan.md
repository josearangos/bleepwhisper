# Implementation Plan: Run Bleeper Anywhere with Docker

**Branch**: `003-docker-packaging` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-docker-packaging/spec.md`

## Summary

Package the existing CLI and Gradio UI into one CPU-only image so anyone with Docker can mask audio
with no local Python, ffmpeg or model download. A three-stage Dockerfile (`builder` → `model` →
`runtime`) on a digest-pinned `python:3.11-slim-trixie` installs dependencies from a hash-locked
`requirements.lock`, bakes the Whisper model (`WHISPER_MODEL`, default `small`) into a Hugging Face
cache at `/opt/hf`, and runs as UID 1000 with `HF_HUB_OFFLINE=1`. `docker-compose.yml` exposes a
one-shot `cli` service (`./data` ↔ `/data`) and a `ui` service bound to `127.0.0.1:7860` with a
health check and a named volume. The only Python changes are in the interface layer: a new
`bleeper/settings.py` makes model, UI host, port and upload limit env-configurable (native defaults
unchanged), plus a clearer offline error in `load_model`. `scripts/smoke.sh` proves it end-to-end
(espeak-ng speech → offline masking → checks), and a GitHub Actions workflow runs it on every push
and pull request. See [research.md](research.md) for each decision.

## Technical Context

**Language/Version**: Python 3.11 in the image (project supports 3.10+; dev venv is 3.12); Bash for
scripts; Dockerfile + Compose spec.

**Primary Dependencies**: Existing only — faster-whisper 1.2.1 (ctranslate2, onnxruntime, av<19),
numpy, soundfile, Gradio 6.x (ui extra), ffmpeg (apt). Build/dev tools: Docker + buildx, `uv` (lock
generation), espeak-ng (smoke test only, in a throwaway container).

**Storage**: Files only — host bind mount `./data`, named volume `bleeper-ui-data` for the UI's
existing `jobs.json` + job directories, baked HF model cache `/opt/hf`.

**Testing**: pytest (new unit tests for `settings.py`, updated UI launcher/submit tests, offline
error test); `scripts/smoke.sh` end-to-end; GitHub Actions running the smoke script.

**Target Platform**: Linux containers on linux/amd64 and linux/arm64 hosts (Docker Desktop on
macOS/Windows, Docker Engine on Linux). CPU only.

**Project Type**: CLI tool + local web UI (single Python package) with container packaging.

**Performance Goals**: Smoke script < 15 min on a laptop excluding base-image pull (SC-007); cached
CI re-runs dominated by the masking step (~1 min).

**Constraints**: Image < 2 GB (FR-008, est. ~1.4 GB); zero network at run time; non-root; native
behavior unchanged when no env vars are set; no new runtime dependencies.

**Scale/Scope**: Single user on a local machine; ~10 new/changed files; fits the ~2 h budget.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I. Core-First | No audio logic added or moved. `settings.py` lives outside `core`; CLI and UI read it. The only `core` change is the wording of `load_model`'s error when offline. CLI ≡ UI ≡ container output for the same inputs. | ✅ Pass |
| II. Offline, CPU-Only, Private | Model baked at build; `HF_HUB_OFFLINE=1` and Gradio analytics off at run time; smoke runs with `--network none`; CPU image only; default model `small`, overridable at build. No audio or transcripts logged. Gradio temp dir still wiped on start. | ✅ Pass |
| III. Audio Correctness | Pipeline untouched; smoke verifies duration/rate/channels preserved and that only the reported span changes; parity check V3 compares byte-for-byte with native. Input never overwritten (unchanged CLI rule). | ✅ Pass |
| IV. Code Quality | New Python (`settings.py`, `smoke_check.py`) typed, ruff-clean; no dead code; no bundled audio (speech generated at test time). Container runs Python 3.11 ≥ 3.10. | ✅ Pass |
| V. Testing | `settings.py` gets unit tests; changed UI modules keep their tests green; default `pytest` stays offline/model-free. Smoke test uses generated audio, nothing large committed. `smoke_check.py` is covered by `tests/unit/test_smoke_check.py`. | ✅ Pass |
| VI. User Experience | Same CLI flags/exit codes in the container; UI jobs stay non-blocking; invalid env vars and missing baked model give actionable errors; smoke prints which check failed. | ✅ Pass |
| VII. Simplicity & Scope | No new runtime dependency (uv, Docker, espeak-ng are build/test tools outside the image's Python env). No GPU, Kubernetes, registry or cloud. ~2 h. | ✅ Pass |

**Post-design re-check (after Phase 1)**: ✅ All principles still pass. The one design adjustment —
naming the UID override `BLEEPER_UID`/`BLEEPER_GID` because `UID` is read-only in bash — changes no
principle. No entries needed in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-docker-packaging/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R10
├── data-model.md        # Phase 1: image, lock, data folder, UI volume, settings
├── quickstart.md        # Phase 1: validation scenarios V1–V7
├── contracts/
│   ├── container-interface.md   # build, cli/ui services, env vars, guarantees
│   └── smoke-script.md          # smoke.sh inputs, steps, exit codes
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
Dockerfile                         # NEW: builder → model → runtime, non-root, offline env
.dockerignore                      # NEW: allow-list (pyproject, README, lock, src)
docker-compose.yml                 # NEW: cli (profile, ./data) + ui (127.0.0.1:7860, healthcheck, volume)
requirements.lock                  # NEW: uv universal, hashed, py3.11, ui extra
.gitignore                         # CHANGED: add data/
README.md                          # CHANGED: "Run with Docker" section + CI badge + env var table
.github/workflows/docker-smoke.yml # NEW: buildx + GHA cache + scripts/smoke.sh on push/PR

scripts/
├── lock.sh                        # NEW: regenerate requirements.lock
├── smoke.sh                       # NEW: build → size → tts → mask (--network none) → verify → non-root
└── smoke_check.py                 # NEW: output/report checks run inside the image

src/bleeper/
├── settings.py                    # NEW: env-backed model/host/port/upload-limit with validation
├── cli.py                         # CHANGED: --model default from settings
├── core/transcribe.py             # CHANGED: actionable error when HF_HUB_OFFLINE is set and model not cached (reads env, no huggingface_hub import)
└── ui/
    ├── __main__.py                # CHANGED: host/port/max_file_size from settings; validate env
    ├── submit.py                  # CHANGED: MODEL, MAX_BYTES from settings
    └── app.py                     # CHANGED: upload label shows configured limit

tests/
├── unit/test_settings.py          # NEW
├── unit/test_smoke_check.py       # NEW: smoke_check.py checks on generated audio
├── unit/test_transcribe.py        # CHANGED: offline-missing-model message
├── unit/test_ui_submit.py         # unchanged behavior (monkeypatches MAX_BYTES)
└── integration/test_ui_main.py    # CHANGED: host/port from env, invalid env → exit 1
```

**Structure Decision**: Keep the existing single-package layout (`src/bleeper`, `tests/`). Container
and CI files live at the repository root where Docker, Compose and GitHub expect them; helper
scripts go in a new `scripts/` folder. No new Python package.

## Complexity Tracking

No constitution violations; nothing to justify.
