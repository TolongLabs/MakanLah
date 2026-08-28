#!/usr/bin/env bash
# The merge guard decides whether an agent may merge. A guard nobody tests is a
# guard nobody has, so these run in CI.
#
# Cases needing GitHub are skipped when gh is absent or unauthenticated, and the
# skip is reported rather than counted as a pass -- a check that reports success
# because it did not run is the failure mode AUTONOMY.md rule 4 is about.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
HOOK=.claude/hooks/guard-merge.sh
pass=0 fail=0 skip=0

run() { echo "{\"tool_input\":{\"command\":\"$1\"}}" | bash "$HOOK" >/dev/null 2>&1; echo $?; }

want() { # want <expected-exit> <command> <description>
  local got; got=$(run "$2")
  if [[ "$got" == "$1" ]]; then pass=$((pass + 1)); else
    fail=$((fail + 1)); echo "  FAIL: $3 (wanted exit $1, got $got)"
  fi
}

echo "merge guard"

# Passes through anything that is not a merge.
want 0 "git status" "a non-merge command is untouched"
want 0 "gh pr view 1" "a non-merge gh command is untouched"
want 0 "echo gh pr mergeable" "a substring that is not the command is untouched"

# Blocks on its own terms, no network needed.
want 2 "gh pr merge --merge" "a merge with no PR number"
want 2 "gh pr merge 21 --merge --admin" "--admin, which bypasses branch protection"
want 2 "rtk gh pr merge 21 --merge" "an rtk-prefixed merge is still matched"

if gh auth status >/dev/null 2>&1; then
  want 2 "gh pr merge 999999 --merge" "a PR that does not exist"
  merged=$(gh pr list --state merged --limit 1 --json number --jq '.[0].number' 2>/dev/null || true)
  if [[ -n "$merged" ]]; then
    want 2 "gh pr merge $merged --merge" "an already-merged PR"
  else
    skip=$((skip + 1)); echo "  SKIP: no merged PR to test against"
  fi
else
  skip=$((skip + 2)); echo "  SKIP: gh unauthenticated, 2 network cases not run"
fi

# Fails CLOSED. Every other hook in this repo exits 0 on internal failure so a
# broken guard cannot wedge a session; this one must not, because failing open
# permits exactly the merge it exists to prevent.
BASH_ABS=$(command -v bash)
got=$(echo '{"tool_input":{"command":"gh pr merge 1 --merge"}}' \
  | env -i PATH=/nonexistent "$BASH_ABS" "$HOOK" >/dev/null 2>&1; echo $?)
if [[ "$got" == "2" ]]; then pass=$((pass + 1)); else
  fail=$((fail + 1)); echo "  FAIL: with no tools on PATH the guard must DENY, got exit $got"
fi

echo "  $pass passed, $fail failed, $skip skipped"
[[ "$fail" -eq 0 ]]
