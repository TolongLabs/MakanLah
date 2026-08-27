#!/usr/bin/env bash
# PreCompact: context is about to be summarised. Conversation history does not
# survive it; docs/PROGRESS.md does. This is the last moment to write it down.
#
# SWARM.md §6 ranks context exhaustion third among the things that stop a long
# run, and the fix it names is checkpointing to files. Exits 0 always.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[[ -d "${root:-}" ]] || exit 0
cd "$root" || exit 0

stale=''
if [[ -f docs/PROGRESS.md ]]; then
  # Anything committed since PROGRESS.md was last touched is work it does not describe.
  last=$(git log -1 --format=%ct -- docs/PROGRESS.md 2>/dev/null || echo 0)
  head=$(git log -1 --format=%ct 2>/dev/null || echo 0)
  [[ "$head" -gt "$last" ]] && stale=' It is older than the most recent commit, so it is behind.'
else
  stale=' It does not exist yet — create it.'
fi

cat <<MSG
{"hookSpecificOutput":{"hookEventName":"PreCompact","additionalContext":"Context is about to be compacted. Rewrite docs/PROGRESS.md BEFORE continuing.${stale} Record: what you just finished, what is in flight, any blocker you routed around and how, and the terminal condition for this run. The next session starts with none of your context and reads only that file. Keep it under twenty lines — the session brief prints the head. The backlog stays in GitHub Issues, not here."}}
MSG
exit 0
