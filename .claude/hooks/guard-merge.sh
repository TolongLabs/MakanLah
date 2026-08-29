#!/usr/bin/env bash
# PreToolUse(Bash): allow `gh pr merge` ONLY when CI is verifiably green.
#
# This implements issue #4. The blanket `Bash(gh pr merge:*)` deny was correct
# in intent -- an agent must not merge unreviewed work -- and wrong in effect:
# deny outranks allow, so `scripts/unattended.sh on` could report success while
# doing nothing, and every unattended run stalled at its first PR.
#
# UNLIKE THE OTHER HOOKS IN THIS REPO, THIS ONE FAILS CLOSED. The others exit 0
# on internal failure so a broken guard never wedges a session. Here, failing
# open would permit exactly the merge the guard exists to prevent, and the
# fallback -- a human merges -- is the status quo rather than a broken session.
set -uo pipefail

deny() { echo "BLOCKED: $1" >&2; exit 2; }

# A read that fails is not a check that failed, and the difference matters in an
# unattended run: a momentary API blip denied a merge whose CI was green and
# whose branch resolved fine one second later, which stalls exactly the runs #23
# exists to keep moving.
#
# Retrying the READ is not retrying the VERDICT. If every attempt fails we still
# deny, so nothing is loosened -- an unreadable state stays an unmerged PR.
read_thrice() {
  local out
  for _ in 1 2 3; do
    if out=$("$@" 2>/dev/null) && [[ -n "$out" ]]; then
      printf '%s' "$out"
      return 0
    fi
    sleep 1
  done
  return 1
}

command -v jq >/dev/null 2>&1 || deny "jq is unavailable, so CI state cannot be verified."
cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null) || deny "could not read the command."
[[ -n "$cmd" ]] || exit 0

# Not a merge: nothing to say.
grep -Eq 'gh[[:space:]]+pr[[:space:]]+merge\b' <<<"$cmd" || exit 0

command -v gh >/dev/null 2>&1 || deny "gh is unavailable, so CI state cannot be verified."

pr=$(grep -Eo 'gh[[:space:]]+pr[[:space:]]+merge[[:space:]]+[0-9]+' <<<"$cmd" | grep -Eo '[0-9]+$' || true)
# Deliberately matched against the whole command string rather than at a command
# position. Prose that merely mentions the phrase -- a doc edit, a commit message,
# an issue body, all of which this repo writes constantly -- trips the guard too.
# That is the safe side of the trade: narrowing to a real command position needs
# shell parsing a hook cannot do, and a miss here is an UNGUARDED MERGE, because
# the settings deny was removed in #23. A false positive costs one retry; a false
# negative costs the reviewer.
# More than one PR named in one command. Taking the first would verify that one
# and wave the rest through, so this must deny rather than pick. It denied before
# only by accident -- the multi-line value made the API read fail -- which is the
# right outcome reached for the wrong reason and with a baffling message.
if [[ $(grep -c . <<<"$pr") -gt 1 ]]; then
  deny "more than one PR number in this command. Merge them one at a time, so each one's checks are verified."
fi

[[ -n "$pr" ]] || deny "no PR number found. If you are merging, name it explicitly so its checks can be verified. \
If this is prose that only mentions the phrase, keep the three words non-adjacent in the command itself -- build the \
string in two pieces, or write the file from a script that does not contain them together."

# --admin bypasses branch protection. Never from an agent.
grep -Eq '(^|[[:space:]])--admin([[:space:]]|$)' <<<"$cmd" \
  && deny "--admin bypasses branch protection. A human does that, not an agent."

state=$(read_thrice gh pr view "$pr" --json mergeStateStatus,state \
  --jq '"\(.state) \(.mergeStateStatus)"') || deny "could not read PR #$pr from GitHub after three attempts."

read -r pr_state merge_state <<<"$state"
[[ "$pr_state" == "OPEN" ]] || deny "PR #$pr is $pr_state, not OPEN."

# The rollup, counted rather than trusted. AUTONOMY.md: "No checks reported" is
# not "green" -- to a caller that only looks for failures, nothing looks exactly
# like success, so an absent verifier must block.
checks=$(gh pr checks "$pr" --json state --jq '.[].state' 2>/dev/null || true)
if [[ -z "$checks" ]]; then
  # gh pr checks needs a token scope this repo's CI does not always grant; fall
  # back to the run list for the PR's head branch before concluding anything.
  branch=$(read_thrice gh pr view "$pr" --json headRefName --jq '.headRefName') \
    || deny "no checks reported for #$pr and its branch could not be read after three attempts."
  checks=$(read_thrice gh run list --branch "$branch" --limit 1 --json conclusion --jq '.[].conclusion' || true)
fi

[[ -n "$checks" ]] || deny "no checks reported for #$pr. An absent verifier is not a pass (AUTONOMY.md)."

while read -r c; do
  [[ -z "$c" ]] && continue
  case "$c" in
    SUCCESS | success | SKIPPED | skipped | NEUTRAL | neutral) ;;
    *) deny "#$pr has a check in state '$c'. Green CI is the only gate that stands in for a reviewer." ;;
  esac
done <<<"$checks"

case "$merge_state" in
  CLEAN | HAS_HOOKS) ;;
  UNSTABLE) deny "#$pr is UNSTABLE — checks are still running. Wait for them." ;;
  *) deny "#$pr mergeStateStatus is $merge_state, not CLEAN." ;;
esac

exit 0
