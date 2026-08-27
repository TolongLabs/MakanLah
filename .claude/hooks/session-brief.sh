#!/usr/bin/env bash
# SessionStart: one line of orientation, plus the gate state. Exits 0 on any
# internal failure so a broken brief never wedges a session.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[[ -d "${root:-}" ]] || exit 0
cd "$root" || exit 0

# Hardcoded epochs: `date -d` is GNU-only and fails on macOS.
# 2026-09-09 00:00 MYT — GLM-5.3-Flash promo pricing ends, token cost doubles.
# 2026-09-23 00:00 MYT — Devin Pro lapses, the free SWE-1.7 worker tier with it.
now=$(date +%s)
glm=$(( (1788883200 - now) / 86400 ))
devin=$(( (1790092800 - now) / 86400 ))

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')
dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

# The docs gate. Implementation does not start until all three exist.
missing=()
for f in docs/PRODUCT.md docs/PRD.md docs/TRD.md; do
  [[ -f "$f" ]] || missing+=("$(basename "$f")")
done

echo "MakanLah | branch=$branch | uncommitted=$dirty | GLM promo ${glm}d | Devin free ${devin}d"

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "GATE: docs/${missing[*]} missing. No implementation until all three exist (AGENTS.md)."
fi

if [[ ! -d src && ! -d ingest ]]; then
  echo "Pre-scaffold. The Xiaohongshu spike gates everything — see docs/README.md."
fi

# Unattended runs self-merge on green CI; attended ones do not. Which is live
# changes whether a PR is the end of the work or the middle of it.
if [[ -f .claude/settings.local.json ]] \
   && grep -q 'gh pr merge' .claude/settings.local.json 2>/dev/null; then
  echo "MODE: unattended — self-merge allowed on green CI. Nobody is reviewing behind you."
fi

# The only thing that survives compaction. Print it so a fresh session reads it
# without having to know it exists.
if [[ -f docs/PROGRESS.md ]]; then
  echo "--- docs/PROGRESS.md ---"
  sed -e 's/^/  /' docs/PROGRESS.md | head -20
else
  echo "No docs/PROGRESS.md. Create it before doing anything a later session must know."
fi

echo "Blocked? Read docs/AUTONOMY.md before deciding you are. TODOs: gh issue list."
