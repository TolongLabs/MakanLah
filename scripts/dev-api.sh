#!/usr/bin/env bash
# Run the API locally against the Neon corpus.
#
# For development. The API IS deployed -- Vercel, sin1 -- and shipping a change
# is `scripts/deploy-api.sh`, which asserts /health reports the sha it just sent.
# This script exists so you can run against the corpus without deploying.

set -uo pipefail
root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 1; }
cd "$root" || exit 1

PORT="${PORT:-8000}"

exec uv run --quiet python -m uvicorn api.main:app --host 127.0.0.1 --port "$PORT" "$@"
