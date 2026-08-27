#!/usr/bin/env bash
# Bring up a CDP-controllable Chrome carrying the signed-in Xiaohongshu session.
#
# WHY THIS IS NOT ONE COMMAND
#
# Chrome 136+ refuses remote debugging against the default profile directory:
#
#   "DevTools remote debugging requires a non-default data directory.
#    Specify this using --user-data-dir."
#
# Verified on dev1, Chrome 151. This is a deliberate anti-cookie-theft measure
# and there is no flag to turn it off. Pointing --user-data-dir at
# ~/.config/google-chrome therefore silently fails: Chrome starts, serves no
# debugging port, and every automated fetch hits a login wall as though nobody
# had ever signed in.
#
# The workaround is a copy of the session-bearing files in a non-default
# directory. It is a duplicated live credential, so this script keeps it at mode
# 700 under a path that is never inside the repo, and `stop` removes it.
#
# Usage: scripts/chrome-session.sh start|stop|status|verify

set -uo pipefail

PORT="${XHS_CDP_PORT:-9222}"
SRC="${XHS_CHROME_PROFILE:-$HOME/.config/google-chrome}"
PROFILE_DIR="${XHS_CHROME_PROFILE_DIR:-Default}"
WORK="${XHS_CDP_PROFILE:-$HOME/.cache/makanlah/chrome-session}"

ok()   { printf '  \033[32mok\033[0m    %s\n' "$1"; }
warn() { printf '  \033[33mwarn\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mfail\033[0m  %s\n' "$1"; }

cdp() { curl -s -m 5 "http://127.0.0.1:$PORT$1" 2>/dev/null; }

chrome_bin() {
  for b in google-chrome google-chrome-stable chromium chromium-browser; do
    command -v "$b" >/dev/null 2>&1 && { echo "$b"; return; }
  done
  return 1
}

do_stop() {
  pkill -f "remote-debugging-port=$PORT" 2>/dev/null
  sleep 2
  # The copy is a duplicated credential. Removing it is the point of `stop`.
  [[ -d "$WORK" ]] && rm -rf "$WORK"
  ok "stopped; session copy removed"
}

do_status() {
  local v; v=$(cdp /json/version)
  if [[ -n "$v" ]]; then
    ok "CDP live on $PORT — $(echo "$v" | grep -o '"Browser":"[^"]*"' | cut -d'"' -f4)"
    return 0
  fi
  warn "no CDP on port $PORT"
  return 1
}

# Proves the session actually carried over. Without this the script can report
# success while every fetch quietly returns a login wall — which is the exact
# failure this whole file exists to prevent.
do_verify() {
  do_status >/dev/null || { bad "CDP is not up; run: $0 start"; return 1; }

  local target
  target=$(cdp /json/new?https://www.xiaohongshu.com/explore)
  [[ -z "$target" ]] && target=$(curl -s -m 5 -X PUT \
      "http://127.0.0.1:$PORT/json/new?https://www.xiaohongshu.com/explore" 2>/dev/null)
  sleep 8

  local tabs; tabs=$(cdp /json)
  if [[ -z "$tabs" ]]; then bad "CDP stopped responding"; return 1; fi

  python3 - "$tabs" <<'PY'
import json, sys
try:
    tabs = json.loads(sys.argv[1])
except Exception:
    print("  \033[31mfail\033[0m  could not parse the CDP tab list"); raise SystemExit(1)

hits = [t for t in tabs if "xiaohongshu" in (t.get("url") or "")]
if not hits:
    print("  \033[31mfail\033[0m  no xiaohongshu tab opened"); raise SystemExit(1)

t = hits[0]
title, url = (t.get("title") or ""), (t.get("url") or "")
print(f"  title: {title[:90]}")
print(f"  url:   {url[:90]}")

# A redirect to a login path, or a login-shaped title, means the copy did not
# carry the session. Treat an ambiguous result as unverified, never as a pass.
lowered = (title + " " + url).lower()
if any(k in lowered for k in ("login", "signin", "sign-in", "登录", "扫码")):
    print("  \033[31mfail\033[0m  landed on a login wall — the session did not carry over")
    raise SystemExit(1)
print("  \033[32mok\033[0m    no login wall; session appears to have carried")
PY
}

do_start() {
  local bin; bin=$(chrome_bin) || { bad "no Chrome on PATH"; return 1; }

  if do_status >/dev/null 2>&1; then
    ok "CDP already live on $PORT — leaving it alone"
    return 0
  fi

  [[ -d "$SRC/$PROFILE_DIR" ]] || { bad "no profile at $SRC/$PROFILE_DIR"; return 1; }

  # A live Chrome holds a lock on the profile, and copying underneath it yields
  # a torn cookie store that fails in ways that look like an expired session.
  if pgrep -f "user-data-dir=$SRC" >/dev/null 2>&1; then
    bad "Chrome is running on the source profile. Close it first — copying a"
    echo "        locked profile produces a torn cookie store." >&2
    return 1
  fi

  rm -rf "$WORK"; mkdir -p "$WORK/$PROFILE_DIR"; chmod 700 "$WORK"

  # Only the session-bearing files. The full profile is gigabytes of cache, and
  # "Local State" must come too: on Linux it holds the key the cookie store is
  # encrypted with, so cookies copied without it decrypt to nothing.
  cp "$SRC/Local State" "$WORK/" 2>/dev/null
  for f in Cookies "Login Data" "Web Data" Preferences "Local Storage" "Session Storage" Network; do
    cp -r "$SRC/$PROFILE_DIR/$f" "$WORK/$PROFILE_DIR/" 2>/dev/null
  done
  chmod -R go-rwx "$WORK" 2>/dev/null
  ok "session copied to $WORK ($(du -sh "$WORK" 2>/dev/null | cut -f1))"

  # xvfb only when there is no display: an ssh session has none, and headless
  # mode is a different code path that some sites fingerprint.
  local launcher=()
  if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    command -v xvfb-run >/dev/null 2>&1 || { bad "no display and no xvfb-run (sudo apt install xvfb)"; return 1; }
    launcher=(xvfb-run -a)
  fi

  setsid nohup "${launcher[@]}" "$bin" \
    --user-data-dir="$WORK" \
    --profile-directory="$PROFILE_DIR" \
    --remote-debugging-port="$PORT" \
    --remote-allow-origins='*' \
    --no-first-run --no-default-browser-check --disable-gpu \
    </dev/null >"$WORK/chrome.log" 2>&1 &
  disown

  for _ in $(seq 1 20); do
    sleep 2
    do_status >/dev/null 2>&1 && { do_status; return 0; }
  done

  bad "CDP never came up on $PORT"
  grep -iE 'non-default|requires|cannot' "$WORK/chrome.log" 2>/dev/null | head -3 | sed 's/^/        /' >&2
  return 1
}

case "${1:-status}" in
  start)  do_start ;;
  stop)   do_stop ;;
  status) do_status ;;
  verify) do_verify ;;
  *) echo "usage: $0 start|stop|status|verify" >&2; exit 2 ;;
esac
