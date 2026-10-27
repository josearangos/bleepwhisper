#!/usr/bin/env bash
# End-to-end proof: build the image, make speech, mask a word offline, verify the result.
# Knobs: SMOKE_IMAGE (default bleeper:smoke), SMOKE_BUILD_ARGS (extra `docker buildx build` args).
set -euo pipefail
cd "$(dirname "$0")/.."

SMOKE_IMAGE="${SMOKE_IMAGE:-bleeper:smoke}"
SMOKE_BUILD_ARGS="${SMOKE_BUILD_ARGS:-}"
WORD=fox
PHRASE="The quick brown fox jumps over the lazy dog."
TTS_IMAGE="debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
chmod 777 "$WORK"

STEP=start
step() { STEP="$1"; echo "==> $1"; }
fail() { echo "smoke: FAIL ($STEP): $1" >&2; exit 1; }

step build
# shellcheck disable=SC2086
docker buildx build --load -t "$SMOKE_IMAGE" $SMOKE_BUILD_ARGS . || fail "docker build failed"

step size
size=$(docker image inspect -f '{{.Size}}' "$SMOKE_IMAGE")
[ "$size" -lt 2000000000 ] || fail "image is $size bytes, the limit is 2000000000"

step tts
docker run --rm -v "$WORK:/work" "$TTS_IMAGE" sh -c \
    "apt-get update -qq && apt-get install -y -qq --no-install-recommends espeak-ng >/dev/null \
     && espeak-ng -v en-us -s 140 -w /work/input.wav '$PHRASE'" || fail "could not generate speech"
printf '%s\n' "$WORD" > "$WORK/words.txt"

step mask
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$WORK:/data" \
    "$SMOKE_IMAGE" /data/input.wav --words /data/words.txt --preset beep --lang en \
    -o /data/output.wav || fail "masking failed offline"

step verify
docker run --rm --network none --user "$(id -u):$(id -g)" -v "$WORK:/data" \
    -v "$PWD/scripts/smoke_check.py:/smoke_check.py:ro" --entrypoint python "$SMOKE_IMAGE" \
    /smoke_check.py /data/input.wav /data/output.wav /data/output.json "$WORD" \
    || fail "output did not pass the checks"

step non-root
uid=$(docker run --rm --entrypoint id "$SMOKE_IMAGE" -u)
[ "$uid" != "0" ] || fail "container runs as root"

echo "smoke: OK"
