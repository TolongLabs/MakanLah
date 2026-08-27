#!/usr/bin/env bash
# Pre-run self-check. Answers "will an unattended run get stuck on setup?"
# before it gets stuck on setup, four hours in, with nobody watching.
#
# Never exits non-zero on a warning — a missing optional tool is information,
# not a blocker (docs/AUTONOMY.md). Exits 1 only when something required is
# genuinely absent.
#
# Usage: scripts/preflight.sh

set -uo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 1; }
cd "$root" || exit 1

# A non-interactive shell (ssh cmd, cron, an agent's Bash tool) does not source
# .profile or .bashrc, so PATH is the bare system default and every user-installed
# tool reads as missing. Normalise before probing, or this script confidently
# reports a fully provisioned machine as empty.
for d in "$HOME/.bun/bin" "$HOME/.local/bin" "$HOME/.npm-global/bin" "$HOME/.fly/bin" "$HOME/bin"; do
  [[ -d "$d" && ":$PATH:" != *":$d:"* ]] && PATH="$d:$PATH"
done
export PATH

fail=0
ok()   { printf '  \033[32mok\033[0m    %s\n' "$1"; }
warn() { printf '  \033[33mwarn\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mMISS\033[0m  %s\n' "$1"; fail=1; }

echo
echo "Required"
for t in git bun node jq; do
  command -v "$t" >/dev/null 2>&1 && ok "$t" || bad "$t — an unattended run cannot proceed without it"
done
[[ -d node_modules ]] && ok "node_modules — run \`bun install\` after any dependency change" \
                      || bad "node_modules — run: bun install"

echo
echo "Optional (absence changes nothing, it is only reported)"
for t in gh graphify rtk devin codex uv timeout xvfb-run neonctl wrangler flyctl; do
  command -v "$t" >/dev/null 2>&1 && ok "$t" || warn "$t — not installed"
done
command -v gsd >/dev/null 2>&1 && ok "gsd" \
  || warn "gsd — \`/gsd-config --profile\` hard-stops without it: bun add -g get-shit-done"

echo
echo "Repository"
[[ -x .claude/hooks/guard-git.sh ]] && ok "guard-git.sh executable" || bad "guard-git.sh not executable"
for h in session-brief.sh format-edited.sh checkpoint-reminder.sh; do
  [[ -x ".claude/hooks/$h" ]] && ok "$h executable" || warn "$h not executable"
done
jq -e . .claude/settings.json >/dev/null 2>&1 && ok "settings.json parses" \
  || bad "settings.json is not valid JSON — a comment or trailing comma breaks it"

broken=$(find .claude/skills -maxdepth 1 -xtype l 2>/dev/null | wc -l | tr -d ' ')
[[ "$broken" == "0" ]] && ok "skill symlinks all resolve" || bad "$broken broken skill symlink(s) in .claude/skills"
[[ -f .claude/skills/impeccable/scripts/hook.mjs ]] && ok "impeccable hook present" \
  || warn "impeccable hook missing — the PostToolUse design check is inert"

echo
echo "Gates"
[[ -f docs/PRODUCT.md ]] && ok "docs/PRODUCT.md" || bad "docs/PRODUCT.md missing"
for d in PRD TRD; do
  [[ -f "docs/$d.md" ]] && ok "docs/$d.md" \
    || warn "docs/$d.md missing — write it, do not stop (AGENTS.md, the gate is not a stopping point)"
done
[[ -f docs/PROGRESS.md ]] && ok "docs/PROGRESS.md — the checkpoint the next session reads" \
                          || warn "docs/PROGRESS.md missing — nothing survives compaction without it"

echo
echo "Credentials (.env is never read, only key presence is checked)"
if [[ -f .env ]]; then
  ok ".env present"
  for k in DATABASE_URL MODELSCOPE_API_KEY FIRECRAWL_API_KEY OPENROUTER_API_KEY HERMES_API_KEY; do
    if grep -qE "^${k}=.+" .env 2>/dev/null; then ok "$k set"
    else warn "$k empty — stub the boundary and continue on fixtures (AUTONOMY.md)"; fi
  done
else
  warn ".env missing — cp .env.example .env. Work on fixtures until then, do not stop"
fi

echo
echo "Mode"
bash scripts/unattended.sh status 2>/dev/null | sed 's/^/  /' || warn "unattended.sh not runnable"

# Model cliffs from docs/SWARM.md §4. Hardcoded epochs: `date -d` is GNU-only.
now=$(date +%s)
echo "  GLM-5.3-Flash promo ends in $(( (1788883200 - now) / 86400 ))d (2026-09-09)"
echo "  Devin free tier ends in $(( (1790092800 - now) / 86400 ))d (2026-09-23) — keep dispatch model-agnostic"

echo
if [[ $fail -eq 0 ]]; then
  echo "Preflight clean. Warnings above are informational — none of them stops a run."
else
  echo "Something required is missing (MISS above). Install it and re-run." >&2
fi
exit $fail
