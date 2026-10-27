# Feature Specification: Run Bleeper Anywhere with Docker

**Feature Branch**: `003-docker-packaging`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Containerize bleeper (CLI and Gradio UI) so anyone can run it with identical results on any machine. As a developer or recruiter, I clone the repo and run bleeper with one Docker command, without installing Python, ffmpeg or Whisper dependencies. Single multi-stage Dockerfile, CPU-only, pinned python:3.11-slim base with ffmpeg; dependencies from a pinned lock file; Whisper model (default small, build arg WHISPER_MODEL) baked in at build time so the container runs fully offline; non-root user; docker-compose.yml with a one-shot `cli` service (./data mounted at /data) and a `ui` service (bound to 0.0.0.0 inside, published only on 127.0.0.1:7860, healthcheck, volume for jobs and results); .dockerignore; environment variables for model name, port and max upload size; scripts/smoke.sh that builds, generates synthetic audio with a known word, runs the CLI with --network none and checks the output exists with the same duration; optional GitHub Actions workflow running the smoke test on every push; README section 'Run with Docker'; image under 2 GB. Out of scope: GPU/CUDA images, Kubernetes, registry publishing, cloud deployment."

## Clarifications

### Session 2026-10-27

- Q: When the container writes masked files into `./data`, whose user ID should own them? → A: Fixed non-root user with UID/GID 1000 by default; the `cli` service can be run as the host user's ID by setting `BLEEPER_UID`/`BLEEPER_GID` environment variables, documented in the README. (Named `BLEEPER_UID`/`BLEEPER_GID` rather than `UID`/`GID` during planning, because `UID` is read-only in bash.)
- Q: Besides output existence and duration, should the smoke script verify the known word was actually masked? → A: Yes: the report must list at least one span for the known word, and the output must differ from the input inside that span (no reference checksum).
- Q: Where does the smoke test get real speech containing the known word? → A: Generated at test time with an open-source text-to-speech engine (espeak-ng) in a throwaway container; no audio is committed and nothing is added to the runtime image.
- Q: Should this feature ship the GitHub Actions workflow? → A: Yes, in scope: `.github/workflows/docker-smoke.yml` runs `scripts/smoke.sh` on every push and pull request with build caching, plus a README status badge.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mask a file from a fresh clone with one command (Priority: P1)

A developer or recruiter who has only Docker installed clones the repository, builds the image once,
drops an audio file and a word list into the `data` folder, and runs a single documented command.
They get a masked audio file and its JSON report in the same folder, without installing Python,
ffmpeg or any speech-recognition dependency on their machine, and without the container reaching
the internet.

**Why this priority**: This is the whole point of the feature: zero-setup, reproducible use of the
core tool. Without it there is no value; with only this story the feature is already a usable MVP.

**Independent Test**: On a machine with Docker and no Python toolchain, clone, build, place
`input.wav` and `words.txt` in `./data`, run the documented CLI command with networking disabled,
and confirm `./data/output.wav` and its report appear.

**Acceptance Scenarios**:

1. **Given** a fresh clone and a completed build, **When** the user runs the documented CLI command
   on `./data/input.wav` with `./data/words.txt` and the `beep` preset, **Then** `./data/output.wav`
   and its JSON report are created, and the output is identical (same samples, same report) to what
   a native run of the same version with the same model and options produces.
2. **Given** a completed build, **When** the CLI is run with all container networking disabled,
   **Then** the run succeeds, because the speech model is already inside the image.
3. **Given** the user's output files are written to the mounted folder, **When** the user inspects
   them on the host, **Then** they are readable and deletable by the host user without elevated
   privileges.
4. **Given** an invalid input (missing file, missing word list), **When** the CLI runs in the
   container, **Then** it prints the same actionable error and returns the same exit code as the
   native CLI (`1` invalid input, `2` processing error).

---

### User Story 2 - Use the web UI from a container (Priority: P2)

The same person starts the web UI with one command, opens `http://localhost:7860` in their browser,
submits jobs exactly as in the native UI, and finds their job list and results still there after
stopping and restarting the container. The UI is reachable only from their own machine.

**Why this priority**: The UI is the friendliest way to demo the tool, but it builds on the image
delivered in Story 1.

**Independent Test**: Start the UI service, open `http://localhost:7860`, submit a job and wait for
it to finish, restart the service, and confirm the job and its downloadable result are still listed.
From another machine on the same network, confirm the port is not reachable.

**Acceptance Scenarios**:

1. **Given** a completed build, **When** the user starts the UI service, **Then** the UI is served at
   `http://localhost:7860` and the service reports itself healthy once it accepts requests.
2. **Given** completed jobs, **When** the UI service is stopped and started again, **Then** the jobs
   list and result files are still available, because they live in a persistent volume.
3. **Given** the UI service is running, **When** another device on the local network tries to open
   port 7860 on the host, **Then** the connection is refused (the port is published on the host's
   loopback interface only).
4. **Given** a configured maximum upload size, **When** the user uploads a larger file, **Then** the
   UI rejects it with a readable message stating the limit.

---

### User Story 3 - Prove reproducibility automatically (Priority: P3)

A maintainer (or CI on every push and pull request) runs one script that builds the image, creates a short
synthetic audio clip containing a known word, masks it inside the container with networking
disabled, and verifies the result. The script exits `0` on success and non-zero with a clear
message on any failure.

**Why this priority**: It guards Stories 1–2 against regressions, but users get value without it.

**Independent Test**: On a clean machine with Docker, run `scripts/smoke.sh` and check it exits `0`;
break the image (e.g. remove the model) and check it exits non-zero with a readable reason.

**Acceptance Scenarios**:

1. **Given** a clean machine with Docker, **When** the smoke script runs, **Then** it builds the
   image, runs the CLI with networking disabled, confirms the masked output exists, has the same
   duration as the input, reports the known word, and differs from the input inside the reported
   span, and exits `0`.
2. **Given** any step fails (build, run, missing output, duration mismatch, known word not
   reported or not masked), **When** the smoke
   script runs, **Then** it stops, prints which check failed, and exits non-zero.
3. **Given** a push or pull request, **When** the CI workflow runs, **Then** it builds the image and
   runs the smoke script, failing the check if the script fails.

---

### Edge Cases

- The `./data` folder does not exist → the run stops before the container starts, with an error
  saying the bind source is missing; the README tells the user to `mkdir -p data` first. An empty
  `./data` → the CLI reports the missing input clearly (exit `1`).
- The output path points at the input file → refused exactly as in the native CLI (input never
  overwritten).
- The host user's ID differs from 1000 → the user sets `BLEEPER_UID`/`BLEEPER_GID` (e.g. `BLEEPER_UID=$(id -u) BLEEPER_GID=$(id -g)`)
  when running the `cli` service, so outputs in `./data` are owned by them; the README shows this.
- The user requests a different model at run time than the one baked into the image → the run fails
  with an actionable error naming the baked model and how to rebuild with another one, rather than
  silently trying to download.
- Port 7860 is already in use on the host → the start-up error is visible, and the documentation
  shows how to change the published port.
- The jobs volume is removed → the UI starts with an empty job list rather than failing.
- The container is stopped mid-job → after restart, the interrupted job is shown as failed/interrupted
  as the native UI already does, never as silently "running" forever.
- Build machine is ARM (e.g. Apple Silicon) vs x86 → the image builds and runs on both; masked
  output may differ only where the native runs on those architectures would also differ.

## Requirements *(mandatory)*

### Functional Requirements

**Packaging**

- **FR-001**: The project MUST provide a single container build definition that produces one CPU-only
  image containing the CLI, the web UI, ffmpeg and all runtime dependencies.
- **FR-002**: The image MUST be built from a base image pinned to an exact version (Python 3.11 slim
  variant), so the same source produces the same environment on every build.
- **FR-003**: Python dependencies MUST be installed from a committed lock file with exact pinned
  versions; builds MUST NOT resolve dependencies freshly.
- **FR-004**: The build MUST use separate build and runtime stages so build-only tools do not ship in
  the final image.
- **FR-005**: The speech model MUST be downloaded during the build and stored inside the image. The
  model MUST default to `small` and MUST be selectable at build time (`WHISPER_MODEL`).
- **FR-006**: At run time the container MUST work with networking fully disabled and MUST NOT attempt
  any network access (including model downloads or UI telemetry).
- **FR-007**: The container process MUST run as a dedicated non-root user in both the CLI and UI
  modes. The image's user MUST have UID/GID 1000. The `cli` service MUST run as
  `${BLEEPER_UID:-1000}:${BLEEPER_GID:-1000}` so a host user with another ID can own the files it writes to `./data`;
  the model and application files in the image MUST be readable by any UID.
- **FR-008**: The final image MUST be smaller than 2 GB with the default model.
- **FR-009**: A build-context exclusion file MUST keep audio files, caches, virtual environments,
  version-control data, spec-kit files and local outputs out of the build context.

**Orchestration**

- **FR-010**: The project MUST provide a compose file with two services built from the same image:
  `cli` and `ui`.
- **FR-011**: The `cli` service MUST be one-shot, MUST mount the host `./data` folder at `/data`, and
  MUST accept the same arguments as the native `bleeper` command, e.g.
  `docker compose run --rm cli /data/input.wav --words /data/words.txt --preset beep -o /data/output.wav`.
- **FR-012**: The `ui` service MUST run the web UI listening on all interfaces inside the container,
  MUST be published on the host only at `127.0.0.1:7860`, and MUST define a health check that passes
  only when the UI responds.
- **FR-013**: The `ui` service MUST store its jobs list, uploaded inputs and results in a persistent
  volume so they survive container restarts and re-creation.

**Configuration**

- **FR-014**: The following settings MUST be configurable through environment variables, each with a
  documented default: model name (default `small`), UI listen address (default loopback when run
  natively, all interfaces in the container), UI port (default `7860`), maximum upload size (default
  100 MB, matching the native UI), and UI data folder.
- **FR-015**: Native (non-container) behavior MUST remain unchanged when none of these variables are
  set: the native UI still binds only to loopback, uses `small`, and keeps the 100 MB limit.

**Verification & documentation**

- **FR-016**: The project MUST provide `scripts/smoke.sh` that builds the image, generates a short
  synthetic speech clip containing a known word using an open-source text-to-speech engine
  (espeak-ng) inside a throwaway container (so the host needs only Docker, no audio is committed, and
  the engine never enters the runtime image), runs the CLI in the container with networking
  disabled, and verifies that: (a) the output exists; (b) it has the same duration, sample rate and
  channel count as the input; (c) the JSON report lists at least one masked span for the known word;
  and (d) the output samples differ from the input inside that span. It MUST NOT compare against a
  stored checksum. It MUST exit `0` only if every check passes and print which check failed otherwise.
- **FR-017**: The project MUST provide a CI workflow (`.github/workflows/docker-smoke.yml`) that runs
  the smoke script on every push and pull request, reuses a build cache between runs, fails the
  check when the script fails, and never publishes the image. The README MUST show its status badge.
- **FR-018**: The README MUST contain a "Run with Docker" section covering: building the image
  (including choosing another model), preparing `./data`, the CLI command, starting/stopping the UI,
  where UI data persists, and changing the published port.

### Key Entities

- **Image**: the single built artifact; identified by the project version and the baked model name;
  contains the runtime, ffmpeg, dependencies, the model and a non-root user.
- **Data folder (`./data` ↔ `/data`)**: host folder shared with the one-shot CLI; holds the user's
  inputs, word lists, masked outputs and reports.
- **UI volume**: persistent storage for the UI's jobs list, uploads and results.
- **Lock file**: the exact, committed list of dependency versions used by every build.
- **Smoke test**: the scripted end-to-end check of build + offline masking.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person with only Docker installed can go from a fresh clone to a masked audio file
  using the README's commands alone, with at most 3 commands after cloning and no other software
  installed.
- **SC-002**: For the same input, word list, options and model, the container's masked audio and
  report are identical to the native run's (100% sample and report match on the reference sample).
- **SC-003**: 100% of CLI runs succeed with networking disabled after the build.
- **SC-004**: After a restart of the UI service, 100% of previously listed jobs and their results are
  still available.
- **SC-005**: The UI is reachable from the host machine and unreachable from any other machine on
  the network.
- **SC-006**: No process in either service runs with administrator (root) privileges.
- **SC-007**: The smoke script exits `0` on a clean machine and completes (excluding first-time base
  image download) in under 15 minutes on a typical laptop.
- **SC-008**: The final image with the default model is under 2 GB.

## Assumptions

- Users have Docker with the Compose plugin installed and a machine able to run the `small` model on
  CPU (roughly 2 GB RAM free); internet access is needed only for the build.
- "Identical results" is judged against a native run of the same project version with the same model
  and options on the same CPU architecture; tiny floating-point differences between CPU
  architectures in transcription are outside this feature's control.
- Python 3.11 in the container satisfies the constitution's Python 3.10+ requirement.
- The native UI currently hard-codes its listen address, model and upload limit; making them
  configurable via environment variables (with today's values as defaults) is part of this feature
  and is an interface-layer change only — no audio logic moves out of the core.
- The lock-file generator and the container tooling are development/build tools, not runtime
  dependencies, so no constitution amendment is needed (Principle VII). Docker packaging is local
  distribution, not the out-of-scope "cloud deployment".
- Only the model chosen at build time is available at run time; switching models requires a rebuild.
- The jobs volume is a named volume managed by Compose; the CLI uses a bind mount of `./data`.
- The smoke script needs internet only while building the image and preparing the text-to-speech
  container; the masking step itself runs with networking disabled.
- The CI workflow runs on GitHub-hosted x86 runners and does not publish images anywhere.
- Out of scope: GPU/CUDA images, Kubernetes, publishing to a registry, cloud deployment.
