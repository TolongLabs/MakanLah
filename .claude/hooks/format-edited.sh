#!/usr/bin/env bash
# PostToolUse(Edit|Write|MultiEdit): format the edited file. Exits 0 on any failure.
set -uo pipefail

command -v jq >/dev/null 2>&1 && command -v bunx >/dev/null 2>&1 || exit 0
file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[[ -f "${file:-}" ]] || exit 0

case "$file" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.json|*.jsonc|*.css|*.html)
    bunx --bun biome check --write --no-errors-on-unmatched "$file" >/dev/null 2>&1
    ;;
  *.md|*.markdown|*.yaml|*.yml)
    bunx prettier --write "$file" >/dev/null 2>&1
    ;;
esac
exit 0
