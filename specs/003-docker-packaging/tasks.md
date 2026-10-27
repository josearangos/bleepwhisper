---

description: "Task list for 003-docker-packaging"
---

# Tasks: Run Bleeper Anywhere with Docker

**Input**: Design documents from `/specs/003-docker-packaging/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. Constitution Principle V requires pytest tests for every new or changed module.
The spec also requires an end-to-end smoke test (US3). Default `pytest` MUST stay offline and run without a model.

**Organization**: Tasks are grouped by user story so each story can be implemented and verified on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 = CLI from a fresh clone (P1), US2 = Web UI in a container (P2), US3 = Automated
  reproducibility proof (P3)

## Path Conventions

Single package: `src/bleeper/`, `tests/` at repo root. Container files (`Dockerfile`,
`docker-compose.yml`, `.dockerignore`, `requirements.lock`) and `scripts/` at repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Lock file, build-context rules and git hygiene that every later task builds on.

- [X] T001 [P] Add a `data/` line under a new `# Docker` comment in `.gitignore` (the host folder shared with the `cli` service must never be committed)
- [X] T002 [P] Create `scripts/lock.sh` (bash, `set -euo pipefail`, executable, `cd` to repo root) that runs exactly: `uv pip compile pyproject.toml --extra ui --universal --python-version 3.11 --generate-hashes -o requirements.lock`; header comment: "Regenerate whenever pyproject.toml dependencies change" (research R2)
- [X] T003 Run `scripts/lock.sh` to generate `requirements.lock`; confirm it pins `faster-whisper==1.2.1`, `av<19` (e.g. `av==18.x`), `gradio==6.x`, has `--hash=sha256:` lines for every package, and does NOT list `bleeper` itself (data-model "Lock file")
- [X] T004 [P] Create `.dockerignore` as an allow-list (research R10): first line `*`, then `!pyproject.toml`, `!README.md`, `!requirements.lock`, `!src/`, then re-exclude `**/__pycache__`, `**/*.egg-info`, `**/*.pyc`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Env-backed settings, used by the CLI (US1) and the UI (US2), and the image that all three stories run.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Write `tests/unit/test_settings.py` (use `monkeypatch.setenv`/`delenv`): with all vars unset → `default_model()=="small"`, `ui_host()=="127.0.0.1"`, `ui_port()==7860`, `max_upload_mb()==100`; set values are returned (`BLEEPER_MODEL=base`, `BLEEPER_UI_HOST=0.0.0.0`, `BLEEPER_UI_PORT=8080`, `BLEEPER_UI_MAX_UPLOAD_MB=5`); empty string `BLEEPER_MODEL`/`BLEEPER_UI_HOST` → default; `BLEEPER_UI_PORT` of `abc`, `0`, `65536` and `BLEEPER_UI_MAX_UPLOAD_MB` of `0`, `-1`, `x` raise `SettingsError` whose message contains the variable name and the accepted range ("1–65535" / "an integer ≥ 1")
- [X] T006 Create `src/bleeper/settings.py` (interface layer, NOT in `core`; fully typed; no Gradio import) so T005 passes: `class SettingsError(ValueError)`; functions that read `os.environ` at call time: `default_model() -> str` (`BLEEPER_MODEL`, default `"small"`), `ui_host() -> str` (`BLEEPER_UI_HOST`, default `"127.0.0.1"`), `ui_port() -> int` (`BLEEPER_UI_PORT`, int 1–65535, default `7860`), `max_upload_mb() -> int` (`BLEEPER_UI_MAX_UPLOAD_MB`, int ≥ 1, default `100`); empty strings mean "unset"; module docstring lists the variables and says native defaults equal pre-feature behavior (FR-014, FR-015)
- [X] T007 Resolve the pinned base image: run `docker buildx imagetools inspect python:3.11-slim-trixie` and record the exact patch tag and the multi-arch index digest, e.g. `python:3.11.X-slim-trixie@sha256:…`, for use in T008 (research R1). Requires a running Docker daemon.
- [X] T008 Create `Dockerfile` (research R1, R3–R5; data-model "Image") with:
  - `ARG PYTHON_IMAGE=<pinned ref from T007>`
  - stage `builder` (`FROM ${PYTHON_IMAGE}`): `python -m venv /opt/venv`; `COPY requirements.lock`; `pip install --no-cache-dir --require-hashes --no-deps -r requirements.lock`; `COPY pyproject.toml README.md src/`; `pip install --no-cache-dir --no-deps .`
  - stage `model` (`FROM builder`): `ARG WHISPER_MODEL=small`; `ENV HF_HOME=/opt/hf`; `RUN python -c "from faster_whisper import download_model; download_model('${WHISPER_MODEL}')"`
  - stage `runtime` (`FROM ${PYTHON_IMAGE}`): `apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*`; `groupadd --gid 1000 bleeper && useradd --uid 1000 --gid 1000 --create-home bleeper`; `COPY --from=builder /opt/venv /opt/venv`; `COPY --from=model /opt/hf /opt/hf`; `chmod -R a+rX /opt/hf /opt/venv`; `mkdir -p /var/lib/bleeper && chown 1000:1000 /var/lib/bleeper`
  - Re-declare `ARG WHISPER_MODEL=small` in runtime. Set the ENV exactly as listed in data-model "Image": `PATH=/opt/venv/bin:$PATH HF_HOME=/opt/hf HF_HUB_OFFLINE=1 BLEEPER_MODEL=${WHISPER_MODEL} BLEEPER_UI_HOST=0.0.0.0 BLEEPER_UI_PORT=7860 BLEEPER_UI_MAX_UPLOAD_MB=100 BLEEPER_UI_DATA=/var/lib/bleeper GRADIO_ANALYTICS_ENABLED=False PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`
  - `LABEL org.opencontainers.image.source=… org.opencontainers.image.version=0.1.0 bleeper.whisper-model=${WHISPER_MODEL}`
  - `USER 1000:1000`, `WORKDIR /home/bleeper`, `ENTRYPOINT ["bleeper"]`, `CMD ["--help"]`
  - No `HEALTHCHECK` in the Dockerfile (research R7)
- [X] T009 Build and sanity-check the image: `docker build -t bleeper:local .`; then `docker run --rm bleeper:local` prints help and exits 0; `docker run --rm --entrypoint id bleeper:local -u` prints `1000`; `docker image inspect -f '{{.Size}}' bleeper:local` < 2 000 000 000 (FR-008); `docker run --rm --network none --entrypoint python bleeper:local -c "from bleeper.core.transcribe import load_model; load_model('small')"` succeeds offline. Fix `Dockerfile` until all pass.

**Checkpoint**: The image builds, is under 2 GB, runs as UID 1000 and loads the model offline. Settings tests pass.

---

## Phase 3: User Story 1 - Mask a file from a fresh clone with one command (Priority: P1) 🎯 MVP

**Goal**: `docker compose run --rm cli /data/input.wav --words /data/words.txt --preset beep -o /data/output.wav` works offline, behaves like the native CLI, and writes host-owned files.

**Independent Test**: quickstart V2, V3 and V4: fresh clone → `docker compose build` → CLI command → `data/output.wav` + `data/output.json`; works with `--network none`; output byte-identical to native on the same architecture.

### Tests for User Story 1

- [X] T010 [P] [US1] In `tests/unit/test_transcribe.py`, add `test_offline_missing_model_explains_rebuild`: `monkeypatch.setenv("HF_HUB_OFFLINE", "1")` and `monkeypatch.setenv("BLEEPER_MODEL", "small")`, and make `WhisperModel` raise for `local_files_only=True`. Assert `load_model("tiny")` raises `ProcessingError` whose message contains `'tiny'`, "not available offline", `'small'` (the baked model) and `--build-arg WHISPER_MODEL=tiny`. Do not import `huggingface_hub` in the test. Assert no second (download) attempt is made. Call `load_model.cache_clear()` around the test, as the existing tests do.
- [X] T011 [P] [US1] In `tests/integration/test_cli.py`, add `test_model_default_comes_from_env`: with `BLEEPER_MODEL=base` set, assert `build_parser().parse_args([...required args...]).model == "base"`. With it unset, assert the default is `"small"`. Also assert the `--help` output still documents `--model`.

### Implementation for User Story 1

- [X] T012 [US1] Update `load_model` in `src/bleeper/core/transcribe.py` so T010 passes and `test_downloads_only_when_not_cached` / `test_load_failure_raises_processing_error` still pass. After the `local_files_only=True` attempt fails, if `os.environ.get("HF_HUB_OFFLINE", "").lower() in {"1", "true", "yes", "on"}`, raise `ProcessingError` without trying to download. The message is: `f"Whisper model '{name}' is not available offline (HF_HUB_OFFLINE is set). In Docker this image contains '{os.environ.get('BLEEPER_MODEL', 'its build-time model')}'; rebuild with: docker compose build --build-arg WHISPER_MODEL={name}. Natively, unset HF_HUB_OFFLINE once so it can be downloaded."`. Read the environment variable directly; do NOT import `huggingface_hub` in `core` (Principle VII). Otherwise keep today's behavior. This changes an error message only, not audio logic (contract container-interface "Service cli").
- [X] T013 [US1] In `src/bleeper/cli.py`, change `--model` to `default=settings.default_model()` (import `from bleeper import settings`). Keep the help text as "faster-whisper model name or local path" and add "(env: BLEEPER_MODEL)", so T011 passes.
- [X] T014 [US1] Create `docker-compose.yml` containing:
  - A top-level `name: bleeper`.
  - A `cli` service with `build: .`, `image: bleeper:local`, `profiles: ["cli"]`, `init: true` and `user: "${BLEEPER_UID:-1000}:${BLEEPER_GID:-1000}"`.
  - On `cli`: `environment: { HOME: /tmp }` and `working_dir: /data`. Mount `./data` with the long syntax so Compose never creates it (on Linux it would be root-owned): `volumes: [{ type: bind, source: ./data, target: /data, bind: { create_host_path: false } }]`. Running without `./data` must fail immediately with Docker's "bind source path does not exist" error. Leave the entrypoint as the image default, `bleeper`.
  - Per contract container-interface "Service cli", running `docker compose run --rm cli` with no args prints help.
- [X] T015 [US1] Verify quickstart V2 and V4 on this machine:
  - Before creating `data/`, run `docker compose run --rm cli --help` and expect a "bind source path does not exist" error (I3).
  - Run `docker compose --profile cli build`, then `mkdir -p data`, and copy `samples/mi_audio.wav` to `data/input.wav`. Until T023 adds `ui`, plain `docker compose build` builds nothing, because `cli` is in a profile.
  - Write the words file from `samples/groserias_colombianas.txt`.
  - Run the documented CLI command and expect exit 0, `data/output.wav` and `data/output.json`.
  - Run it again via `docker run --rm --network none -v "$PWD/data:/data" bleeper:local …` and expect exit 0.
  - A missing input exits 1 with a readable error. `--model tiny` exits 2 with the T012 message.
  - Running with `BLEEPER_UID=$(id -u) BLEEPER_GID=$(id -g)` produces files owned by you.
- [X] T016 [US1] Verify quickstart V3 (SC-002): sync the native env to the lock (`uv pip sync requirements.lock && uv pip install --no-deps -e .` in a Python 3.11 venv). Run native and container on the same input, words and options, then `cmp` the WAVs and `diff` the JSON reports. Record the result, plus any architecture caveat, in `specs/003-docker-packaging/quickstart.md` under V3.
- [X] T017 [US1] Add a "Run with Docker" section to `README.md`, after "Usage", with these subsections from contract container-interface:
  - **Build:** `docker compose build`, plus the `--build-arg WHISPER_MODEL=base` variant and the note that switching models requires a rebuild.
  - **Prepare data:** `mkdir -p data`, and that paths are given as `/data/...`.
  - **CLI:** the exact example command, the `--network none` variant, and that exit codes match the native CLI.
  - **Linux file ownership:** the `BLEEPER_UID=$(id -u) BLEEPER_GID=$(id -g)` prefix or a `.env` file, and why `UID` itself can't be used.

**Checkpoint**: US1 is fully functional. The MVP can be demoed from a fresh clone.

---

## Phase 4: User Story 2 - Use the web UI from a container (Priority: P2)

**Goal**: `docker compose up -d ui` serves `http://localhost:7860` (loopback only) and reports itself healthy. Jobs persist across restarts. The upload limit is configurable.

**Independent Test**: quickstart V5. Start `ui` and check that it becomes healthy. Submit a job and restart the service; the job is still listed. Confirm the port can't be reached from the LAN, the container user id is 1000, and an oversize upload is rejected with the configured limit.

### Tests for User Story 2

- [X] T018 [P] [US2] Extend `tests/integration/test_ui_main.py` using the existing `launches` fixture:
  - With no env, `launch()` gets `server_name="127.0.0.1"`, `server_port=7860` and `max_file_size="110mb"`, so native behavior is unchanged (FR-015).
  - `BLEEPER_UI_HOST=0.0.0.0`, `BLEEPER_UI_PORT=8081` and `BLEEPER_UI_MAX_UPLOAD_MB=5` give `server_name="0.0.0.0"`, `server_port=8081` and `max_file_size="15mb"`.
  - An explicit `--port 9000` beats `BLEEPER_UI_PORT`.
  - `BLEEPER_UI_PORT=abc` makes `main()` return 1 and print an `error:` line that names `BLEEPER_UI_PORT`.
  - The printed URL uses the configured host and port.
- [X] T019 [P] [US2] Extend `tests/unit/test_ui_submit.py`:
  - Add `test_limits_and_model_follow_settings`. Set `BLEEPER_UI_MAX_UPLOAD_MB=5` and `BLEEPER_MODEL=base`, then `importlib.reload(submit)`. Assert `submit.MAX_BYTES == 5 * 1024 * 1024` and `submit.MODEL == "base"`. Restore the module with `delenv` + reload afterwards.
  - Assert that the oversize error message states the configured limit in MB, e.g. "the limit is 5 MB".

### Implementation for User Story 2

- [X] T020 [US2] In `src/bleeper/ui/submit.py`:
  - Replace `MODEL = "small"` with `MODEL = settings.default_model()`.
  - Replace `MAX_BYTES = 100 * 1024 * 1024` with `MAX_UPLOAD_MB = settings.max_upload_mb()` and `MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024`.
  - Make the oversize message use `MAX_BYTES / 1024**2` rather than the literal "100 MB". `worker.py` keeps importing `MODEL`, unchanged.
  - This must make T019 pass and keep the existing tests that monkeypatch `MAX_BYTES` green.
- [X] T021 [US2] In `src/bleeper/ui/app.py`, build the audio label from `submit.MAX_UPLOAD_MB`, as `f"Audio (.wav or .mp3, max {MAX_UPLOAD_MB} MB, 30 min)"`, replacing the hard-coded "max 100 MB".
- [X] T022 [US2] In `src/bleeper/ui/__main__.py`:
  - Remove the `HOST` constant.
  - In `main()`, before `build_parser()` and inside `try/except settings.SettingsError as exc`, print `error: {exc}` to stderr and return 1. Read `host = settings.ui_host()`, the port default via `settings.ui_port()`, and `upload_mb = settings.max_upload_mb()`.
  - Make the `--port` default `settings.ui_port()`, with help "(env: BLEEPER_UI_PORT)".
  - Pass `server_name=host`, `server_port=args.port` and `max_file_size=f"{upload_mb + 10}mb"`, keeping today's +10 MB slack.
  - Print `Bleeper UI running at http://{host}:{args.port}`.
  - This must make T018 pass while the existing tests still pass.
- [X] T023 [US2] Add the `ui` service to `docker-compose.yml`:
  - Image and build: `build: .`, `image: bleeper:local`, `init: true`, `entrypoint: ["bleeper-ui"]`, `restart: unless-stopped`.
  - Network and storage: `ports: ["127.0.0.1:${BLEEPER_UI_HOST_PORT:-7860}:7860"]` and `volumes: ["bleeper-ui-data:/var/lib/bleeper"]`.
  - Health check, per research R7: `test: ["CMD", "python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/' % os.environ.get('BLEEPER_UI_PORT','7860'), timeout=3)"]` with `interval: 15s`, `timeout: 5s`, `start_period: 60s` and `retries: 3`.
  - Add a top-level `volumes: { bleeper-ui-data: {} }`.
  - Do not set `user:`, so the service runs as image UID 1000.
- [X] T024 [US2] Run `docker compose build`, then verify quickstart V5:
  - `docker compose up -d ui` reaches `(healthy)` within about 60 s.
  - `http://localhost:7860` serves the UI. Submit `samples/mi_audio.wav` with the words file, wait for "done" and download the result.
  - `docker compose exec ui id -u` prints `1000`.
  - After `docker compose restart ui`, and again after `down && up -d ui`, the job and its result are still listed.
  - `curl -m 3 http://<LAN-IP>:7860` fails.
  - Plain `docker compose build` now builds `bleeper:local` via the `ui` service, and `docker compose run --rm cli --help` uses it.
  - No outbound network (FR-006): create a temporary `docker-compose.offline.yml` override that gives `ui` only `networks: [offline]`, with `networks: { offline: { internal: true } }`. `docker compose -f docker-compose.yml -f docker-compose.offline.yml up -d ui` must reach `(healthy)`, and a job submitted from inside the container (`docker compose exec ui …`, since ports on an internal network aren't reachable from the host) must complete. If that is impractical, fall back to checking `docker compose logs ui` for connection errors and that `docker compose exec ui env` shows `GRADIO_ANALYTICS_ENABLED=False` and `HF_HUB_OFFLINE=1`. Delete the override afterwards; do not commit it.
  - `BLEEPER_UI_MAX_UPLOAD_MB=1` rejects a larger file with the 1 MB message. For this, add `environment: { BLEEPER_UI_MAX_UPLOAD_MB: "${BLEEPER_UI_MAX_UPLOAD_MB:-100}" }` to the `ui` service if it isn't already there.
- [X] T025 [US2] Add a "Web UI" subsection to the README's "Run with Docker" section in `README.md` covering:
  - `docker compose up -d ui` and opening `http://localhost:7860`.
  - `docker compose logs -f ui` and `docker compose down`, which keeps jobs, versus `down -v`, which deletes them.
  - That the UI is reachable only from this machine, and changing the host port with `BLEEPER_UI_HOST_PORT=8080`.
  - The env var table from contract container-interface "Environment variables". Also add `BLEEPER_MODEL`, `BLEEPER_UI_HOST`, `BLEEPER_UI_PORT` and `BLEEPER_UI_MAX_UPLOAD_MB` to the existing native UI section, with their native defaults.

**Checkpoint**: US1 and US2 both work independently. Native `bleeper-ui` with no env still binds `127.0.0.1:7860`.

---

## Phase 5: User Story 3 - Prove reproducibility automatically (Priority: P3)

**Goal**: `scripts/smoke.sh` proves build → offline masking → correct output end-to-end.

**Independent Test**: quickstart V1. `scripts/smoke.sh` exits 0 on a clean machine. A broken build exits non-zero and names the failed step.

### Implementation for User Story 3

- [X] T026 [P] [US3] Create `scripts/smoke_check.py` (typed, ruff-clean, uses only numpy, soundfile, json and argparse from the image) with usage `python smoke_check.py INPUT OUTPUT REPORT WORD`. Checks, per contract smoke-script step 5:
  - (a) OUTPUT and REPORT exist.
  - (b) `sf.info` frames, samplerate and channels are equal.
  - (c) at least one report entry's `word`, lowercased with punctuation stripped, equals WORD.
  - (d) inside `[start, end]` of that entry, converted to frames, `not np.array_equal(in_seg, out_seg)`.
  - Each failure prints `FAIL: <check>: <detail>` to stderr and exits 1. Success prints `verify: OK` and exits 0.
  - Expose `main(argv: list[str] | None = None) -> int` and end with `if __name__ == "__main__": raise SystemExit(main())`, so it can be tested.
- [X] T027 [P] [US3] Create `tests/unit/test_smoke_check.py`. Load `scripts/smoke_check.py` with `importlib.util.spec_from_file_location` and call its `main(argv)` on short audio generated in code (1 s sine written with soundfile in `tmp_path`, plus a JSON report). It must pass when the output differs inside the report span, and exit 1 with `FAIL: (b)` on a frame-count mismatch, `FAIL: (c)` when the word is missing from the report, and `FAIL: (d)` when the output equals the input. No Docker or model needed (Principle V).
- [X] T028 [US3] Resolve the digest of `debian:trixie-slim` with `docker buildx imagetools inspect` for the TTS step (research R8).
- [X] T029 [US3] Create `scripts/smoke.sh` (bash, `set -euo pipefail`, executable, `cd` to repo root) per contract smoke-script:
  - **Setup:** knobs `SMOKE_IMAGE` (default `bleeper:smoke`) and `SMOKE_BUILD_ARGS` (default empty). Constants `WORD=fox` and `PHRASE="The quick brown fox jumps over the lazy dog."`. Set `WORK=$(mktemp -d)` with `trap 'rm -rf "$WORK"' EXIT`, and `chmod 777 "$WORK"` so container UIDs can write. Add a `step()` helper that prints `==> name`, and `fail()` that prints `smoke: FAIL (<step>): <reason>` and exits 1.
  - **build:** `docker buildx build --load -t "$SMOKE_IMAGE" $SMOKE_BUILD_ARGS .`
  - **size:** < 2000000000 bytes.
  - **tts:** `docker run --rm -v "$WORK:/work" debian:trixie-slim@sha256:<T028> sh -c "apt-get update -qq && apt-get install -y -qq --no-install-recommends espeak-ng >/dev/null && espeak-ng -v en-us -s 140 -w /work/input.wav '$PHRASE'"`, then `printf '%s\n' "$WORD" > "$WORK/words.txt"`.
  - **mask:** `docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$WORK:/data" "$SMOKE_IMAGE" /data/input.wav --words /data/words.txt --preset beep --lang en -o /data/output.wav`.
  - **verify:** `docker run --rm --network none --user "$(id -u):$(id -g)" -v "$WORK:/data" -v "$PWD/scripts/smoke_check.py:/smoke_check.py:ro" --entrypoint python "$SMOKE_IMAGE" /smoke_check.py /data/input.wav /data/output.wav /data/output.json "$WORD"`.
  - **non-root:** `docker run --rm --entrypoint id "$SMOKE_IMAGE" -u` must not print `0`.
  - **Finish:** print `smoke: OK`.
- [X] T030 [US3] Run `scripts/smoke.sh` and confirm it exits 0. If the `verify` step's check (c) fails because Whisper doesn't hear "fox", apply research R8's mitigation in `scripts/smoke.sh` and re-run: first try `-s 120`, then change `PHRASE`/`WORD` (e.g. "elephant"). Also confirm the negative case: `SMOKE_BUILD_ARGS="--build-arg WHISPER_MODEL=does-not-exist" scripts/smoke.sh` exits non-zero with `smoke: FAIL (build)`.
- [X] T031 [US3] ~~CI workflow~~ Dropped: no GitHub Actions workflow in this feature.
- [X] T032 [US3] Add a short "Verify your setup" note in "Run with Docker" that shows `scripts/smoke.sh` and what it checks.

**Checkpoint**: All three stories are independently functional and covered automatically.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T033 Run `ruff format --check`, `ruff check` and `pytest` in the dev venv. All must pass, and the default run must stay offline with no Whisper model (constitution quality gates).
- [X] T034 [P] Native regression check (quickstart V6): with no `BLEEPER_*` env, `bleeper-ui` prints `http://127.0.0.1:7860` and `bleeper --help` shows the `--model` default `small`.
- [X] T035 [P] Record the measured image size and the TTS phrase/word finally used in `specs/003-docker-packaging/research.md` (R4 estimate → actual; R8 outcome).
- [X] T036 Run the full quickstart (V1–V5) once more from a fresh clone in a temp dir (`git clone . /tmp/bleeper-fresh`) to confirm nothing depends on untracked local files.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T003 depends on T002.
- **Foundational (Phase 2)**: depends on Setup (T008 needs T003 and T004). Within the phase, T006 depends on T005, T008 on T007, and T009 on T008. **Blocks all stories.**
- **US1 (Phase 3)**: depends on Phase 2.
- **US2 (Phase 4)**: depends on Phase 2. T023 edits `docker-compose.yml`, which T014 creates, so do T014 before T023, or have T023 create the file if US2 is built first.
- **US3 (Phase 5)**: depends on Phase 2. The CLI in the image is enough to run it; T012's error message isn't needed. Best done after US1 so the smoke test exercises the final CLI.
- **Polish (Phase 6)**: after all desired stories.

### User Story Dependencies

- **US1 (P1)**: independent after Phase 2.
- **US2 (P2)**: independent after Phase 2. It shares `docker-compose.yml` and `README.md` with US1, so edits there are sequential.
- **US3 (P3)**: independent after Phase 2. It shares `README.md` with US1 and US2.

### Within Each User Story

- Tests (T010/T011, T018/T019) are written first and must fail before the implementation tasks.
- Python changes → image rebuild → compose → manual verification → README.

### Parallel Opportunities

- Phase 1: T001, T002 and T004 in parallel.
- Phase 2: T005 in parallel with T007.
- US1: T010 and T011 in parallel. T012 and T013 touch different files and can run in parallel after their tests.
- US2: T018 and T019 in parallel. T020 → T021 run in sequence because `app.py` reads `submit.MAX_UPLOAD_MB`. T022 can run in parallel with T020.
- US3: T026, T027 and T031 in parallel with each other and with T028.
- After Phase 2, US1, US2 and US3 can proceed in parallel, with the shared-file caveats above.

---

## Parallel Example: User Story 1

```bash
# Tests first, together:
Task: "T010 offline-missing-model test in tests/unit/test_transcribe.py"
Task: "T011 BLEEPER_MODEL default test in tests/integration/test_cli.py"
# Then implementation, together:
Task: "T012 offline error in src/bleeper/core/transcribe.py"
Task: "T013 --model default from settings in src/bleeper/cli.py"
```

## Parallel Example: User Story 2

```bash
Task: "T018 launcher env tests in tests/integration/test_ui_main.py"
Task: "T019 submit settings tests in tests/unit/test_ui_submit.py"
# then
Task: "T020 submit.py MODEL/MAX_BYTES from settings"
Task: "T022 __main__.py host/port/max_file_size from settings"
```

## Parallel Example: User Story 3

```bash
Task: "T026 scripts/smoke_check.py"
Task: "T027 tests/unit/test_smoke_check.py"
Task: "T028 resolve debian:trixie-slim digest"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (T001–T004) → Phase 2 (T005–T009): the image builds, is < 2 GB and loads the model offline.
2. Phase 3 (T010–T017): the CLI via Compose, offline, with parity to native.
3. **Stop and validate** with quickstart V2–V4. This is demoable: "clone, build, one command".

### Incremental Delivery

1. Setup + Foundational → image ready.
2. US1 → CLI demo (MVP).
3. US2 → browser demo with persistent jobs.
4. US3 → smoke script, which turns "runs anywhere" into something checkable.
5. Polish → full quickstart from a fresh clone.

---

## Notes

- Every task needing Docker (T007, T009, T015, T016, T024, T028, T030, T036) requires a running
  Docker daemon. It is not running on the planning machine as of 2026-10-27.
- Never commit audio. `data/` is git-ignored, and the smoke test generates its speech at run time.
- `BLEEPER_UID`/`BLEEPER_GID`, not `UID`/`GID` (bash read-only variable; see research R5).
- Commit after each phase checkpoint.
