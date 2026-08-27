# Progress

Session checkpoint. **The session-brief hook prints the first twenty lines at every start**, so anything below them may
as well not be written. Rewrite this whenever you finish a unit, make a decision, route around a blocker, or a
`PreCompact` hook tells you to.

Session state only. The backlog lives in GitHub Issues — see [`../AGENTS.md`](../AGENTS.md#how-work-ships).

---

**Updated:** 2026-08-28 · pre-spike

**Terminal condition for this run:** the Xiaohongshu spike returns a number. Can ~50 KL restaurant posts be pulled with
name, location, dish and sentiment into records matching the `source_post` / `venue` / `mention` schema in
[`TRD.md`](TRD.md)? **Report counts, not a verdict** — "34 of 50, 6 missing location" is the shape of the answer.

**State:** repo scaffolded, no application code. `PRODUCT.md`, `SWARM.md`, `AUTONOMY.md` and `TRD.md` are written.
**`PRD.md` is the one gate document still missing** — write it after the spike, do not stop for it.

**Do this first, before anything else:**

```bash
scripts/chrome-session.sh start && scripts/chrome-session.sh verify
```

Chrome 136+ refuses CDP against the default profile, so the naive approach fails **silently** — it serves no debugging
port and every fetch returns a login wall indistinguishable from an expired session. The script works around it;
`verify` is what proves the session carried. **Nobody has yet confirmed it end to end.** If `verify` fails, that is a
real finding: record it, fall through to the open-web sources via Firecrawl, and keep going.

**In flight:** nothing.

**Blockers routed around:** none yet.

**Next:**

1. `scripts/preflight.sh` — confirm keys and mode before starting
2. Chrome session up and **verified**
3. Spike. **Orchestrator only, no workers, no GSD** — `SWARM.md` §3 rules the spike out of fan-out, because exploratory
   work fails in ways no test anticipates
4. Raw captures to `docs/source/`, dated. Numbers here
5. Treat the TRD schema as a hypothesis. If real posts do not fit it, change the TRD and say what changed
6. Then, and only then: `PRD.md`, and `/gsd-new-project` for the scaffold phase

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
