#!/usr/bin/env bash
# Deploys the API to Vercel with the commit it is built from.
#
# The project is deliberately NOT git-connected -- merging updates the client via
# Cloudflare CI and leaves the function alone, so a deploy is an explicit act.
# The cost is that Vercel never sets VERCEL_GIT_COMMIT_SHA, so /health reported
# `commit: null` and "is the fix deployed?" stayed unanswerable from outside.
# Two sessions burned seven minutes on exactly that question.
#
# Passing the SHA by hand works and will be forgotten. This will not.
set -euo pipefail
cd "$(dirname "$0")/.."

SHA=$(git rev-parse HEAD)
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "refusing: working tree is dirty, so $SHA would not describe what ships" >&2
  exit 1
fi

echo "deploying $SHA"
vercel deploy --prod -e GIT_COMMIT_SHA="$SHA" "$@"

# Assert the running process agrees, rather than trusting the deploy reported
# READY. A deploy that succeeds and serves the previous build is the failure
# this whole endpoint exists to make visible.
for _ in $(seq 1 10); do
  sleep 3
  got=$(curl -fsS https://makanlah-api.vercel.app/health | python3 -c 'import json,sys;print(json.load(sys.stdin).get("commit") or "")' || true)
  [ "$got" = "$SHA" ] && { echo "verified: /health reports $got"; exit 0; }
done
echo "DEPLOYED BUT UNVERIFIED: /health reports '${got:-null}', expected $SHA" >&2
exit 1
