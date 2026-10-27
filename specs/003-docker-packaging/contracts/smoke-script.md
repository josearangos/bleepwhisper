# Contract: `scripts/smoke.sh`

## Invocation

```bash
scripts/smoke.sh
SMOKE_IMAGE=bleeper:test SMOKE_BUILD_ARGS="--build-arg WHISPER_MODEL=base" scripts/smoke.sh
```

| Input | Default | Meaning |
|-------|---------|---------|
| `SMOKE_IMAGE` | `bleeper:smoke` | Tag to build and test |
| `SMOKE_BUILD_ARGS` | empty | Extra args appended to `docker buildx build` |

Host requirements: bash, Docker with buildx, internet for the build and TTS steps only.

## Steps (in order; stop at the first failure)

1. `build` — `docker buildx build --load -t $SMOKE_IMAGE $SMOKE_BUILD_ARGS .`
2. `size` — image size < 2 GB (`docker image inspect -f '{{.Size}}'`).
3. `tts` — espeak-ng in a pinned throwaway Debian container writes `input.wav` saying
   "The quick brown fox jumps over the lazy dog."; `words.txt` contains `fox`.
4. `mask` — CLI in `$SMOKE_IMAGE` with `--network none`, `--user $(id -u):$(id -g)`,
   `--preset beep --lang en`; must exit `0`.
5. `verify` — `scripts/smoke_check.py` in `$SMOKE_IMAGE` (`--network none`) checks:
   - (a) `output.wav` and `output.json` exist;
   - (b) same frame count, sample rate and channel count as `input.wav`;
   - (c) the report has ≥ 1 span whose `word` is `fox` (after lowercasing/stripping punctuation);
   - (d) at least one output sample inside that span differs from the input.
6. `non-root` — `docker run --rm --entrypoint id $SMOKE_IMAGE -u` prints a non-zero UID.

## Output and exit codes

- Each step prints `==> <step>`; success ends with `smoke: OK` and exit `0`.
- Any failure prints `smoke: FAIL (<step>): <reason>` to stderr and exits `1`.
- The temporary work directory is always removed.
