# Contract: Container Interface

The user-facing surface of this feature. Anything here is a promise documented in the README;
changing it is a breaking change.

## Build

```bash
docker compose build                                   # default model: small
docker compose build --build-arg WHISPER_MODEL=base    # any faster-whisper model name
```

- Network is needed only during the build.
- `docker compose build` builds the shared image via the `ui` service; `docker compose run` activates
  the `cli` profile automatically.
- Result: one image `bleeper:local` used by both services.

## Service `cli` (one-shot)

```bash
mkdir -p data          # once, before the first run
docker compose run --rm cli /data/input.wav --words /data/words.txt --preset beep -o /data/output.wav
```

- Arguments after `cli` are passed verbatim to `bleeper`; flags, help text, outputs and exit codes
  are identical to the native CLI (`0` success, `1` invalid input, `2` processing error).
- `docker compose run --rm cli` with no args prints `bleeper --help` and exits `0`.
- Only `./data` is visible, at `/data`. Paths must be given as `/data/...`. `./data` must exist;
  Compose never creates it (`create_host_path: false`), so a missing folder fails before the run.
- Runs as `${BLEEPER_UID:-1000}:${BLEEPER_GID:-1000}`. Linux users with another ID:
  `BLEEPER_UID=$(id -u) BLEEPER_GID=$(id -g) docker compose run --rm cli …` (or put `BLEEPER_UID=`/`BLEEPER_GID=` in `.env`).
- `--model` defaults to the baked model. Requesting another model fails with exit `2` and:
  `error: Whisper model '<name>' is not available offline (HF_HUB_OFFLINE is set). In Docker this image contains '<baked>'; rebuild with: docker compose build --build-arg WHISPER_MODEL=<name>. …`
  (wording may vary, but it MUST name the requested model and the rebuild command).
- Works with all networking disabled, e.g.
  `docker run --rm --network none -v "$PWD/data:/data" bleeper:local /data/in.wav …`.
- Not started by `docker compose up` (Compose profile `cli`).

## Service `ui`

```bash
docker compose up -d ui        # then open http://localhost:7860
docker compose logs -f ui
docker compose down            # keeps jobs; `down -v` deletes them
```

- Listens on `0.0.0.0:7860` inside the container; published on the host as
  `127.0.0.1:${BLEEPER_UI_HOST_PORT:-7860}` only. Change the host port with
  `BLEEPER_UI_HOST_PORT=8080 docker compose up -d ui`.
- Health: `healthy` once `GET /` returns 200 (checked every 15 s, 60 s start period).
- Jobs, uploads and results persist in the named volume `bleeper-ui-data`.
- Runs as UID 1000. Restart policy `unless-stopped`.

## Environment variables

| Variable | Default in image | Effect |
|----------|------------------|--------|
| `BLEEPER_MODEL` | baked model | Default model for CLI and UI |
| `BLEEPER_UI_HOST` | `0.0.0.0` | UI bind address inside the container |
| `BLEEPER_UI_PORT` | `7860` | UI port inside the container |
| `BLEEPER_UI_MAX_UPLOAD_MB` | `100` | Max audio upload size in the UI |
| `BLEEPER_UI_DATA` | `/var/lib/bleeper` | UI jobs/results directory |
| `BLEEPER_UI_HOST_PORT` | `7860` | (Compose only) host port bound on `127.0.0.1` |
| `BLEEPER_UID` / `BLEEPER_GID` | `1000` | (Compose only) user the `cli` service runs as |

Natively (outside Docker) the same variables apply, with defaults `small`, `127.0.0.1`, `7860`,
`100`, `~/.bleeper/ui`.

## Guarantees

- No process runs as root (`docker compose exec ui id -u` ≠ 0).
- No network access at run time (`HF_HUB_OFFLINE=1`, Gradio analytics off).
- Same version + model + options + CPU architecture ⇒ byte-identical `output.wav` and identical
  report as a native run.
