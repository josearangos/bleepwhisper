# Quickstart & Validation: Run Bleeper Anywhere with Docker

**Feature**: [spec.md](spec.md) | Contracts: [container-interface](contracts/container-interface.md),
[smoke-script](contracts/smoke-script.md)

Prerequisites: Docker with the Compose plugin and buildx; internet for the build only; ~3 GB free
disk.

## V1. Smoke test (SC-007, US3)

```bash
scripts/smoke.sh; echo "exit=$?"
```

Expected: steps `build`, `size`, `tts`, `mask`, `verify`, `non-root` all pass; `smoke: OK`;
`exit=0`.
Negative: `SMOKE_BUILD_ARGS="--build-arg WHISPER_MODEL=does-not-exist" scripts/smoke.sh` fails in
`build` with a non-zero exit.

## V2. CLI from a fresh clone (US1, SC-001, SC-003)

```bash
git clone <repo> bleeper && cd bleeper
docker compose build
mkdir -p data && cp /path/to/input.wav data/ && printf 'darn\nheck\n' > data/words.txt
docker compose run --rm cli /data/input.wav --words /data/words.txt --preset beep -o /data/output.wav
ls -l data/output.wav data/output.json           # owned by you
```

Offline: `docker run --rm --network none -v "$PWD/data:/data" bleeper:local /data/input.wav --words /data/words.txt --preset beep -o /data/output.wav` → exit `0`.

Errors (same as native): `docker compose run --rm cli /data/missing.wav --words /data/words.txt --preset beep -o /data/o.wav; echo $?` → readable error, `1`.
Wrong model: `… --model tiny …` → error naming `tiny` and the rebuild command, exit `2`.

## V3. Parity with the native run (SC-002)

On the same machine (same CPU architecture), with the native install from the README:

```bash
bleeper data/input.wav --words data/words.txt --preset beep -o /tmp/native.wav
docker compose run --rm cli /data/input.wav --words /data/words.txt --preset beep -o /data/docker.wav
cmp /tmp/native.wav data/docker.wav && diff /tmp/native.json data/docker.json && echo IDENTICAL
```

Expected: `IDENTICAL`. (Run `scripts/lock.sh`-pinned versions natively for a strict comparison:
`uv pip sync requirements.lock && uv pip install --no-deps -e .`.)

**Result (2026-10-27, Apple Silicon Mac, native macOS arm64 vs Linux arm64 container, lock-synced
Python 3.11 env, `samples/mi_audio.wav` + Colombian word list):** NOT byte-identical. Both runs
masked 5 spans, but two span starts differ by 20 ms (5.62 vs 5.64 s, 10.94 vs 10.96 s), so the WAVs
differ. The container is deterministic (two runs are `cmp`-identical). Cause is most likely the
different ctranslate2 builds on macOS and Linux producing slightly different Whisper timestamps;
strict parity holds only between Linux containers/hosts of the same architecture, which the smoke
test (T029) covers. SC-002 was therefore not met on this macOS machine.

## V4. Linux UID override (FR-007)

```bash
BLEEPER_UID=$(id -u) BLEEPER_GID=$(id -g) docker compose run --rm cli /data/input.wav --words /data/words.txt --preset beep -o /data/output.wav
stat -c '%u' data/output.wav    # equals $(id -u)
```

## V5. Web UI (US2, SC-004, SC-005, SC-006)

```bash
docker compose up -d ui
docker compose ps ui                       # STATUS shows (healthy) within ~60 s
open http://localhost:7860                 # submit a job, wait for "done", download result
docker compose exec ui id -u               # non-zero (1000)
docker compose restart ui                  # or: down && up -d ui
# reload the page: the job and its download are still listed
curl -m 3 http://<this-machine-LAN-IP>:7860 || echo "not reachable from LAN (expected)"
BLEEPER_UI_MAX_UPLOAD_MB=1 docker compose up -d ui   # upload a >1 MB file → readable size error
docker compose down                        # jobs kept; `down -v` deletes them
```

## V6. Native behavior unchanged (FR-015)

```bash
uv run pytest && uv run ruff format --check && uv run ruff check
bleeper-ui    # prints http://127.0.0.1:7860 — still loopback-only by default
```

## V7. Fresh clone

`git clone . /tmp/bleeper-fresh`, then repeat V1–V5 in the clone to confirm nothing depends on
untracked local files. (The CI workflow was dropped from this feature.)
