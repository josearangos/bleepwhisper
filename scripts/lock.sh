#!/usr/bin/env bash
# Regenerate whenever pyproject.toml dependencies change.
set -euo pipefail
cd "$(dirname "$0")/.."
uv pip compile pyproject.toml --extra ui --universal --python-version 3.11 --generate-hashes -o requirements.lock
