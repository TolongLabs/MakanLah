#!/usr/bin/env bash
# Toggle unattended mode: allow an agent to merge its own PR once CI is green.
#
# `main` is PR-gated and .claude/settings.json denies `gh pr merge`, which is
# right when a human is present and stalls an unattended run at the first PR.
#
# This writes .claude/settings.local.json, which is gitignored, so the committed
# posture never changes and nothing here reaches a teammate's checkout. The git
# guard is untouched: every change still goes through a branch and a PR. What
# changes is who presses merge, and only on green CI.
#
# Usage: scripts/unattended.sh on|off|status

set -uo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 1; }
cd "$root" || exit 1

LOCAL='.claude/settings.local.json'
mkdir -p .claude

command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }

is_on() { [[ -f "$LOCAL" ]] && jq -e '.permissions.allow // [] | index("Bash(gh pr merge:*)")' "$LOCAL" >/dev/null 2>&1; }

case "${1:-status}" in
  on)
    [[ -f "$LOCAL" ]] || echo '{}' > "$LOCAL"
    tmp=$(mktemp)
    # A local allow overrides the committed deny for this checkout only.
    jq '.permissions.allow = ((.permissions.allow // []) + ["Bash(gh pr merge:*)"] | unique)' \
      "$LOCAL" > "$tmp" && mv "$tmp" "$LOCAL"
    echo "unattended: ON — self-merge allowed, gated on green CI."
    echo "  Every change still branches and opens a PR. A red check is a human saying no."
    echo "  Turn off after the run: scripts/unattended.sh off"
    ;;
  off)
    if [[ -f "$LOCAL" ]]; then
      tmp=$(mktemp)
      jq '(.permissions.allow) |= (. // [] | map(select(. != "Bash(gh pr merge:*)")))' \
        "$LOCAL" > "$tmp" && mv "$tmp" "$LOCAL"
    fi
    echo "unattended: OFF — a human merges. An unattended run will stall at the first PR."
    ;;
  status)
    if is_on; then
      echo "unattended: ON (self-merge allowed on green CI)"
    else
      echo "unattended: OFF (human merges)"
    fi
    ;;
  *)
    echo "usage: scripts/unattended.sh on|off|status" >&2
    exit 2
    ;;
esac
