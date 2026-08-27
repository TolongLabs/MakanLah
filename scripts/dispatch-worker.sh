#!/usr/bin/env bash
# Model-agnostic worker dispatch. Implements the contract in docs/SWARM.md §4.
#
# The two failure modes this exists to catch, both measured (SWARM.md §7):
#   - silent death: 1 of 8 concurrent workers produced no output, no error, no log
#   - plausible-but-wrong: output that reads correctly and fails hidden tests
# Neither is visible in a worker's self-report, so this script never reads one.
# It asserts the artifact exists, then runs a test the worker never saw.
#
# Model-agnostic on purpose. SWARM.md §4: hardcoding `devin -p` buys a rewrite on
# 2026-09-23 when the free tier lapses. Override with WORKER_CMD.
#
# Usage:
#   scripts/dispatch-worker.sh --task "<prompt>" --artifact <path> --test "<cmd>"
#                              [--timeout 120] [--retries 3] [--label name]
#
# Exit: 0 the hidden test passed. 1 exhausted retries. 2 bad usage.
# A non-zero exit is a failed *unit*, never a reason to halt a batch — see
# docs/AUTONOMY.md. The caller records it and continues.

set -uo pipefail

TASK='' ARTIFACT='' TEST_CMD='' LABEL='' TIMEOUT=120 RETRIES=3

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)     TASK="${2:-}";     shift 2 ;;
    --artifact) ARTIFACT="${2:-}"; shift 2 ;;
    --test)     TEST_CMD="${2:-}"; shift 2 ;;
    --timeout)  TIMEOUT="${2:-}";  shift 2 ;;
    --retries)  RETRIES="${2:-}";  shift 2 ;;
    --label)    LABEL="${2:-}";    shift 2 ;;
    -h|--help)  sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

die() { echo "dispatch: $1" >&2; exit 2; }

[[ -n "$TASK" ]]     || die "--task is required"
[[ -n "$ARTIFACT" ]] || die "--artifact is required (step 4: catches silent death)"
[[ -n "$TEST_CMD" ]] || die "--test is required. SWARM.md §1: if you cannot write
       the failing test, it is not a worker task. Do it yourself."

LABEL="${LABEL:-$(basename "$ARTIFACT")}"

# The one seam where a model is named. Swap the whole command, not a flag, so a
# different provider needs no change here.
WORKER_CMD="${WORKER_CMD:-devin --model swe-1-7 --permission-mode dangerous --respect-workspace-trust false -p --}"

# `timeout` is GNU; macOS needs coreutils. Without it the 271s measured tail can
# stall a wave, so refuse rather than silently dropping the bound.
TIMEOUT_BIN=$(command -v timeout || command -v gtimeout || true)
[[ -n "$TIMEOUT_BIN" ]] || die "no timeout(1) on PATH. brew install coreutils, or set --timeout 0 deliberately."

log() { printf '[%s] %s\n' "$LABEL" "$1" >&2; }

# The test must run against the state the worker left behind, not against its
# own claims. Run it in a fresh shell so nothing the worker exported leaks in.
run_hidden_test() { env -i PATH="$PATH" HOME="$HOME" bash -c "$TEST_CMD" >/dev/null 2>&1; }

before=''
[[ -f "$ARTIFACT" ]] && before=$(sha256sum "$ARTIFACT" 2>/dev/null | cut -d' ' -f1)

attempt=1
while (( attempt <= RETRIES )); do
  log "attempt $attempt/$RETRIES (timeout ${TIMEOUT}s)"

  if [[ "$TIMEOUT" == "0" ]]; then
    # shellcheck disable=SC2086
    $WORKER_CMD "$TASK" >/dev/null 2>&1
    rc=$?
  else
    # shellcheck disable=SC2086
    "$TIMEOUT_BIN" "${TIMEOUT}s" $WORKER_CMD "$TASK" >/dev/null 2>&1
    rc=$?
  fi
  [[ $rc -eq 124 ]] && log "timed out — not waiting out a straggler (SWARM.md §7)"

  # Step 4. A worker exiting 0 having written nothing is the measured silent death.
  if [[ ! -f "$ARTIFACT" ]]; then
    log "no artifact at $ARTIFACT — silent death or refusal (worker exit $rc)"
    (( attempt++ )); continue
  fi
  after=$(sha256sum "$ARTIFACT" 2>/dev/null | cut -d' ' -f1)
  if [[ -n "$before" && "$before" == "$after" ]]; then
    log "artifact unchanged — worker did nothing (worker exit $rc)"
    (( attempt++ )); continue
  fi

  # Step 5. The only evidence that counts.
  if run_hidden_test; then
    log "PASS on attempt $attempt"
    exit 0
  fi
  log "artifact written but hidden test failed — plausible-but-wrong (SWARM.md §7)"
  (( attempt++ ))
done

# 3 attempts took the measured GLM failure rate from ~73% to 15/15 for +13% calls.
log "FAILED after $RETRIES attempts. Record it, open an issue, CONTINUE THE BATCH."
exit 1
