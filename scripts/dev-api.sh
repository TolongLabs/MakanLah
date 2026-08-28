#!/usr/bin/env bash
# Run the API locally against the Neon corpus.
#
# The API is not deployed: Fly.io has no free allowance and the owner's card is
# unfunded, so this is how the app is served until that changes. See fly.toml —
# the deploy is one command once it is.

set -uo pipefail
root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 1; }
cd "$root" || exit 1

PORT="${PORT:-8000}"

exec uv run --quiet python -m uvicorn api.main:app --host 127.0.0.1 --port "$PORT" "$@"
