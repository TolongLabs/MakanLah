#!/usr/bin/env bash
# Provision a fresh machine to run this project unattended. Idempotent: safe to
# re-run, and every step skips if already satisfied.
#
# Written against dev1 (Qubes StandaloneVM, Ubuntu 26.04, passwordless sudo).
# `qubesdb-read /qubes-vm-persistence` returns `full` there, so apt installs
# persist across reboots. On a Qubes *AppVM* it returns `rw-only` and apt
# installs are lost — this script refuses in that case rather than appearing to
# work until the next reboot.
#
# Usage: scripts/bootstrap.sh [--check]
#   --check   report what is missing and change nothing

set -uo pipefail

CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

# A non-interactive shell (ssh cmd, cron, an agent's Bash tool) does not source
# .profile or .bashrc, so PATH is the bare system default and every user-installed
# tool reads as missing. Normalise before probing, or this script confidently
# reports a fully provisioned machine as empty.
for d in "$HOME/.bun/bin" "$HOME/.local/bin" "$HOME/.npm-global/bin" "$HOME/.fly/bin" "$HOME/bin"; do
  [[ -d "$d" && ":$PATH:" != *":$d:"* ]] && PATH="$d:$PATH"
done
export PATH

ok()   { printf '  \033[32mok\033[0m    %s\n' "$1"; }
act()  { printf '  \033[36m..\033[0m    %s\n' "$1"; }
warn() { printf '  \033[33mwarn\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mMISS\033[0m  %s\n' "$1"; }

have() { command -v "$1" >/dev/null 2>&1; }

# Qubes: an AppVM loses / on reboot. Provisioning one is a trap.
if have qubesdb-read; then
  persist=$(qubesdb-read /qubes-vm-persistence 2>/dev/null || echo unknown)
  case "$persist" in
    full)     ok "Qubes persistence=full — apt installs persist" ;;
    rw-only)  bad "Qubes AppVM (persistence=rw-only). apt installs are LOST on reboot."
              echo "        Provision the TEMPLATE instead, or convert this to a StandaloneVM." >&2
              exit 1 ;;
    *)        warn "Qubes persistence unknown ($persist) — verify apt installs survive a reboot" ;;
  esac
fi

echo
echo "System packages"
APT_WANT=(jq curl git build-essential ca-certificates
          libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libgbm1 libnss3
          libxkbcommon0 libxdamage1 libpango-1.0-0 libasound2t64)
missing=()
for p in "${APT_WANT[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
if [[ ${#missing[@]} -eq 0 ]]; then
  ok "all present (headless Chromium deps included — the scrape spike needs them)"
elif [[ $CHECK -eq 1 ]]; then
  bad "would install: ${missing[*]}"
else
  act "installing: ${missing[*]}"
  sudo apt-get update -qq && sudo apt-get install -y -qq "${missing[@]}" \
    && ok "installed" || warn "apt failed — headless browser work may not launch"
fi

echo
echo "Global package manager"
if have bun; then
  ok "bun — global CLIs install with \`bun add -g\` into ~/.bun/install/global"
else
  warn "bun absent; globals will fall back to npm. Installing bun below fixes that"
fi

echo
echo "Toolchain"

install_or_report() { # name check_cmd install_cmd note
  local name="$1" cmd="$2" install="$3" note="${4:-}"
  if have "$cmd"; then ok "$name"; return; fi
  if [[ $CHECK -eq 1 ]]; then bad "$name missing${note:+ — $note}"; return; fi
  act "installing $name"
  if eval "$install" >/dev/null 2>&1 && have "$cmd"; then ok "$name installed"
  else warn "$name install failed${note:+ — $note}"; fi
}

# Bun: package manager and script runner for the whole repo. Not optional.
install_or_report "bun" bun 'curl -fsSL https://bun.sh/install | bash' \
  "the repo's lint/format/typecheck all run through it"

# Claude Code: the orchestrator itself. Native installer, no sudo, lands in ~/.local/bin.
install_or_report "claude" claude 'curl -fsSL https://claude.ai/install.sh | bash' \
  "nothing runs without it"

# uv: the Python lane the scrape spike will need. Also solves the Python version
# problem — dev1 ships 3.14, which is ahead of most scraping wheels, and uv can
# pin an older interpreter per project without touching the system one.
install_or_report "uv" uv 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
  "the scrape spike needs it; system python is 3.14 and too new for most wheels"

# GSD: the orchestration spine. `/gsd-config --profile` hard-stops without it.
install_or_report "gsd" gsd 'bun add -g get-shit-done || npm i -g get-shit-done' \
  "docs/SWARM.md's whole workflow depends on it"

# Optional accelerants. Absence changes nothing about whether the project runs.
for pair in "rtk:token-filtering proxy" "graphify:codebase knowledge graph"; do
  n="${pair%%:*}"; d="${pair##*:}"
  have "$n" && ok "$n" || warn "$n missing ($d) — optional, per-machine"
done

echo
echo "Worker lanes (docs/SWARM.md §5)"
if have devin; then
  ok "devin — free SWE-1.7 lane, until 2026-09-23"
else
  warn "devin missing. Install it from Cognition's own instructions; this script"
  echo "        will not guess the command. Until then the OpenRouter lane covers it —"
  echo "        SWARM.md §5 already designates GLM-5.3-Flash as primary after 2026-09-23,"
  echo "        so an absent devin degrades cost, not capability. Set OPENROUTER_API_KEY."
fi
have codex && ok "codex — second-opinion lane + image generation" \
            || warn "codex missing (optional): bun add -g @openai/codex"

echo
echo "Repository"
if [[ -f package.json ]]; then
  if [[ -d node_modules ]]; then ok "node_modules present"
  elif [[ $CHECK -eq 1 ]]; then bad "would run: bun install"
  else act "bun install"; bun install >/dev/null 2>&1 && ok "dependencies + husky hooks" || warn "bun install failed"; fi
else
  warn "not in the repo root — clone it, then re-run from inside"
fi

echo
echo "Memory"
total_mb=$(free -m | awk '/^Mem:/{print $2}')
swap_mb=$(free -m | awk '/^Swap:/{print $2}')
echo "  RAM ${total_mb}MB, swap ${swap_mb}MB"
if (( total_mb < 8000 )); then
  warn "under 8GB. Each parallel agent is a separate process, and a headless"
  echo "        browser is another. Cap GSD waves rather than discovering this as"
  echo "        an OOM kill four hours in:  /gsd-execute-phase --wave 2"
  (( swap_mb < 4000 )) && echo "        Consider more swap:  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile"
fi

echo
if [[ $CHECK -eq 1 ]]; then
  echo "Check only, nothing changed. Re-run without --check to provision."
else
  echo "Done. Open a new LOGIN shell so PATH picks up ~/.bun/bin and ~/.local/bin,"
  echo "then: scripts/preflight.sh"
fi
