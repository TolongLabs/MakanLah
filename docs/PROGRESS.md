# Progress

Session checkpoint. **The session-brief hook prints the first twenty lines at every start**, so anything below them may
as well not be written. Rewrite this whenever you finish a unit, make a decision, route around a blocker, or a
`PreCompact` hook tells you to.

Session state only. The backlog lives in GitHub Issues — see [`../AGENTS.md`](../AGENTS.md#how-work-ships).

---

**Updated:** 2026-08-28 · scaffold

**Terminal condition for the next run:** the Xiaohongshu spike returns a number. Can ~50 KL restaurant posts be pulled
with structured fields — name, location, dish, sentiment — into a normalized record? Report the count, not a verdict.

**State:** repo scaffolded, no application code. `docs/PRODUCT.md` and `docs/SWARM.md` are written; `PRD.md` and
`TRD.md` are not, and the docs gate is therefore closed. The spike does not need them and runs first.

**In flight:** nothing.

**Blockers routed around:** none yet.

**Next:**

1. Run `scripts/bootstrap.sh` then `scripts/preflight.sh` on the workstation
2. Run the spike. Orchestrator only, no workers — exploratory work fails in ways no test anticipates
3. Write the finding to `docs/source/` with the date, and the numbers here
4. If it returns usable data, write `TRD.md` around the corpus schema it implies, then `/gsd-new-project`

---

## How To Write This

| Field                  | Holds                                                                             |
| ---------------------- | --------------------------------------------------------------------------------- |
| **Terminal condition** | What "done" means for the current run. Named and checkable, never "make progress" |
| **State**              | Where the work actually is. One paragraph                                         |
| **In flight**          | Started and unfinished. What a resuming session would otherwise redo              |
| **Blockers**           | What you skipped, why, and what you did instead. A silent skip reads as done      |
| **Next**               | The ordered short list. Anything beyond the current push goes to Issues           |

Keep the whole thing under twenty lines. It is a handoff to someone with none of your context, not a log — and a log
that scrolls past the printed head is a log nobody reads.
