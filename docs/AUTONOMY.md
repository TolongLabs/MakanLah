# Autonomy Charter

MakanLah is built mostly unattended. **Nobody is watching, and a session that stops to ask has failed the task**, not
paused it.

This file exists because [`SWARM.md`](SWARM.md#6-unattended-long-runs) names unmade decisions as the most common reason
a long run stops, "by a distance". Every decision below is therefore **pre-made**. Take the default, record what you
took, and keep going.

> **Standing authorization.** The repository owner has authorized, in advance, that an agent may resolve blockers on its
> own judgment and proceed without confirmation, within the boundaries in **What Still Stops You** at the end of this
> file. You do not need to ask. Asking when you could have decided is the failure mode this file exists to prevent.

---

## The Rule

**Never end a session on a blocker you could have routed around.** A run ends for exactly two reasons: the terminal
condition is met, or you hit one of the four hard stops. Everything else is work.

When something blocks you, walk this ladder in order and stop at the first rung that moves:

| Rung | Do                                                                                                         |
| ---- | ---------------------------------------------------------------------------------------------------------- |
| 1    | **Take the pre-authorized default** below, if the blocker is a listed decision                             |
| 2    | **Reduce scope.** Ship the narrower thing that works. A KL-only, one-source, 30-record version is progress |
| 3    | **Stub and continue.** Fake the boundary, mark it `TODO(blocked): <what and why>`, open an issue, move on  |
| 4    | **Skip and continue the batch.** One failed unit never halts the rest. Record it, keep going               |
| 5    | **Change approach.** The second-best approach that runs beats the best one that is blocked                 |
| 6    | **Park it.** Write the blocker to `PROGRESS.md`, open a GitHub Issue, pick up the next independent task    |

Rung 6 is not "stop". There is always another independent task, because [`PRODUCT.md`](PRODUCT.md) describes a whole
product and you are never working on all of it.

---

## Pre-Authorized Defaults

These close every open row in [`PRODUCT.md`](PRODUCT.md#open-decisions). **Take them without asking.** They are
reversible, and a reversible decision made now beats a correct one made after a conversation that cannot happen because
nobody is at the keyboard.

| Decision            | Take This                                                                                       | Why, And When To Revisit                                                                                                                                                                                           |
| ------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Scraper stack**   | Firecrawl first, Scrapling with an authenticated session as fallback, both behind one interface | Firecrawl is cheap and already paid for; Scrapling is the only plausible path through a login wall. Revisit if Firecrawl yields <20% on open-web sources                                                           |
| **Corpus store**    | **Neon** — Postgres + pgvector, region near KL. SQLite only for the spike and local fixtures    | One store for rows, full-text and vectors. Chosen over SQLite because the app reads remotely while ingestion writes locally, which is the concurrent-writer case                                                   |
| **Ranking**         | **Hybrid** — embedding retrieval to top-50, LLM re-rank to top-10                               | Cheap recall, good precision, and the re-rank pass is where citations get attached. Revisit once a metric exists to compare against                                                                                |
| **Mobile delivery** | **PWA.** Responsive web, installable, no app store                                              | The product promises a decision in under two minutes; an app store install is a five-minute tax before first use. Revisit only if retention data demands push                                                      |
| **App framework**   | **Vite + React** SPA for the client, **FastAPI** for the API                                    | Ingestion is already Python, so the corpus layer, embedding client and model clients are written once and shared as libraries by two separate processes. Next.js would mean reimplementing all three in TypeScript |
| **Hosting**         | Static client on Cloudflare Pages or Vercel; API on Fly.io, Singapore region                    | Both free-tier, both near KL. **Never host from the workstation** — see below                                                                                                                                      |

### The Workstation Is Never Publicly Reachable

Ingestion runs on the workstation because that is where the authenticated browser session lives. **It must never accept
an inbound connection.** With a hosted corpus it does not need to: it makes outbound connections only — to the platforms
it scrapes, and to Neon to write what it found. Nothing routes back.

That means no port forwarding, no tunnel, no dynamic-DNS entry, and no hostname anywhere in a config that ships. If a
future change appears to need inbound access to the workstation, it is the change that is wrong. The alternative is
always to put the thing being reached behind the API instead.

### Standing Operational Defaults

Not from `PRODUCT.md`, but the same principle — decided once, here, so no session decides them again:

| Situation                                 | Default                                                                                                |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **A source is unreachable**               | Log it, fall through to the next source, continue. Never fail the run on one platform                  |
| **A scrape yields less than asked**       | Take what came back. Report the number. 34 of 50 is a result, not a failure                            |
| **A record fails schema validation**      | Drop the record, count it, continue the batch. Never abort a batch on one bad row                      |
| **A worker times out or returns nothing** | Retry up to 3. Then mark failed, **continue the batch**, and open an issue. Never wait out a straggler |
| **A dependency is missing**               | Install it. It is a reversible decision with a lockfile behind it                                      |
| **A credential is missing**               | Stub the boundary, mark `TODO(blocked)`, continue with fixtures. Do not stop                           |
| **Lint or typecheck fails**               | Fix it. If genuinely unfixable, narrow the change until it passes rather than disabling the check      |
| **A test is flaky**                       | Quarantine it with a named issue, keep the suite green, continue. Never delete a test to go green      |
| **Language handling is ambiguous**        | Handle all three of EN/MS/ZH or handle none. Never ship a path that silently works for one             |
| **Two approaches look equal**             | Take the one with fewer moving parts. Say which you took                                               |
| **Usage limits are close**                | Pace with `/gsd-execute-phase --wave N`. Checkpoint first, so the next session resumes cleanly         |

---

## Checkpointing

**Context exhaustion is stopper #3, and files are the only thing that survives it.** Conversation history does not
survive compaction; [`PROGRESS.md`](PROGRESS.md) does.

Rewrite `PROGRESS.md` **whenever any of these is true**, not on a timer:

- You finished a unit of work, however small
- You made a decision a later session would otherwise remake
- You hit a blocker and routed around it — record what you skipped and why
- You are about to start something that will take a while
- A `PreCompact` hook just told you to

Keep it short. It is a handoff to a session with none of your context, not a log. **The session-brief hook prints its
head at every session start**, so anything below the first twenty lines may as well not be written.

**`PROGRESS.md` is session state, not the backlog.** Anything that outlives the current push goes to GitHub Issues, as
[`../AGENTS.md`](../AGENTS.md#how-work-ships) requires. The two do not overlap: `PROGRESS.md` answers "where was I",
Issues answer "what is left".

---

## Verification Replaces The Human

The reviewer is not there. **CI is what stands in for them**, and it is the only reason autonomous merging is safe.

`.github/workflows/ci.yml` runs lint and typecheck on every PR. Treat a red check exactly as you would treat a human
saying no.

> **"No checks reported" is not "green".** GitHub registers a workflow only once it exists on the default branch, so a
> repo that has not yet merged one reports nothing at all — and to a caller that only looks for failures, nothing looks
> exactly like success. **Confirm a check actually ran before treating it as a pass:** `gh pr checks <n> --watch`. An
> absent verifier is the one case where self-merge is not authorized.

Four rules that make this hold:

1. **Never claim something works without having run it and read the output.** The `verification-before-completion` skill
   is not optional here — a self-report is not evidence, and [`SWARM.md`](SWARM.md#7-measurements) measured a worker
   producing confident output that failed hidden tests
2. **Never merge a worker's output on its self-report.** Assert the artifact exists, then run the test the worker never
   saw
3. **Never disable a check to go green.** Narrowing the change is always available; silencing the check is not
4. **Never verify a fix with the fix's own definition, and confirm the check can fail at all.** A check that defines its
   own success will agree with itself perfectly and prove nothing. Confirm against something the check does not own

### A Check That Owns Its Own Definition Of Success

**Rule 4 is the one that keeps happening**, and it does not look like a mistake while you are making it — the number
comes back clean, so the work looks done. Three instances on 2026-08-28, two of them in the same session:

| What Was Checked      | Why It Agreed With Itself                                                                            | What Actually Caught It        |
| --------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------ |
| **Ranking relevance** | The "wrong result" rule counted only the opposite cuisine, and the reported failure was same-cuisine | The owner, on a screen         |
| **A text strip**      | Completeness was counted with the same regex that did the stripping, so it reported 0 with 295 left  | A deliberately different regex |
| **Colour contrast**   | The checker misparsed `color-mix()`, reading 0-to-1 floats as 0-to-255                               | Probing computed values        |

Each reported success. Each was wrong. **The thing that caught all three was checking against something the check did
not own** — a different pattern, a direct probe, or a human looking at the rendered result.

So when a check reports clean, ask what would have to be true for it to report clean _and_ be wrong. If the answer is
"nothing, by construction", the check is measuring its own definition. **Write the second check first, from a different
angle, before believing the first.**

#### The Merge Case, Because It Is Invisible And Recurs

A fourth instance, the same day, and the worst-behaved: **a merge silently reverted a commit, and CI stayed green
because the commit's tests went out with its code.** A suite cannot fail on a test that is not there.

It arose from a rebase reconstructed as a merge — a legitimate workaround for the force-push deny — where the rebase had
been onto a stale base, so the merge encoded a revert. The author verified `tree == rebased-tip`, which passed, and
proved only that a tree built on the wrong base had been faithfully reproduced. **The second parent was the whole
question and was never asked.**

Two checks, cheapest first, after any merge you did not produce by fast-forward:

```bash
git diff --stat <merge> <second-parent> -- <paths the merge should not touch>   # must be empty
git diff --diff-filter=D --name-only <pre-merge-tip> <merge>                    # what did it delete?
```

and compare the **test count** across the merge. A green suite with fewer tests in it is not a green suite.

**`git merge-base --is-ancestor` is not evidence the content arrived.** It returned true for the reverted commit, which
is exactly why the revert was durable: git considered it merged and would never re-apply it, so it sat latent on the
branch and would have travelled into the next PR.

#### The Check That Cannot Fail, And The Only Thing That Detects It

A sixth instance, found by a peer **in their own work** rather than in someone else's: an agreement test written as
`expect(phase, ...)` instead of `expect(phase(), ...)`. A function reference is never equal to `'idle'`, so the
assertion could not fail for any input. It passed, as it would have passed against any implementation whatsoever.

This one is worse than a check that owns its definition, because it does not even consult the thing it names. Reading it
does not reveal the fault — the line looks like an assertion, and the suite is green.

**What caught it was mutation: the component was pinned to always return `'idle'`, and the test stayed green.** That is
the general remedy, and it is cheap:

> **Break the thing on purpose and confirm the check goes red.** A check that stays green against a deliberately broken
> subject is measuring nothing, whatever it appears to assert.

Do this once, at the moment a check is written, for anything whose result will be trusted without a human looking at it.
The peer's own framing is the one to keep: **a check is trusted the moment it is green, and nothing except mutating the
thing under it distinguishes green-because-correct from green-because-blind.**

Six instances across three sessions in a single day says this is not carelessness. It is the default failure mode of
verification written by the same party that wrote the fix.

#### Twelve, And The Two Kinds Are Not Equally Expensive

The run closed at **twelve instrument failures. Every one was caught by somebody running a control, and none by the
check itself.** That is the finding, not the tally: green is trusted on sight, so nothing inside the check ever
questions it.

They split into two kinds, and the cheaper-looking one is the cheaper one:

|                     | What it does                                        | What it costs                                                     |
| ------------------- | --------------------------------------------------- | ----------------------------------------------------------------- |
| **False all-clear** | Reports clean while measuring nothing               | Caught eventually — somebody notices the thing is broken          |
| **False alarm**     | Reports a defect in code that is behaving correctly | **Acted on.** Somebody spends a cycle fixing what was never wrong |

Ten of the twelve were false all-clears. The two that nearly reached a person were both false alarms: an "Ask returns
nothing" report that was the reader truncating DOM text, and a "320px overflow" that was a closed off-canvas drawer
parked off-screen. `chrome_check` reading `/discover` before its redirect had rendered is the same shape — **the app was
right and the check blamed it.**

So when a check reports a defect, the first question is not "how do I fix the code". It is:

> **Does the defect reproduce outside the instrument that found it?** A direct probe, a second tool, a human looking at
> the screen. If it does not reproduce, the instrument is the finding.

**Fix the class, not the instance.** Three separate probes failed the same way — a geometry assertion that never
established the element was on screen. A `.option` matched hidden step panels, a right-edge check measured a parked
drawer, and a clipping check measured `sr-only` nodes. One shared gate retires all three: flag an element only if the
**document** actually overflows and the element is visible at all. That gate was then mutation-tested by injecting a
real 1900px element, because **a gate that can only ever say "none" is worse than the false positive it replaced.**

### Unattended Mode

**Agents may merge, but only onto green CI.** `.claude/hooks/guard-merge.sh` permits `gh pr merge` and denies it unless
the PR is OPEN, its checks have actually reported, every one of them passed, and `mergeStateStatus` is clean. It refuses
`--admin`, refuses a merge that does not name its PR number, and — **unlike every other hook here — it fails closed**:
the others exit 0 on internal failure so a broken guard cannot wedge a session, but failing open here would permit
exactly the merge the guard exists to prevent, and the fallback is only that a human merges.

This replaced a blanket `Bash(gh pr merge:*)` deny, which was right in intent and wrong in effect: **deny outranks
allow**, so `scripts/unattended.sh on` reported success while doing nothing and every unattended run stalled at its
first PR. That was issue #4.

```bash
scripts/unattended.sh on     # allow self-merge, gated on green CI
scripts/unattended.sh off    # restore the human merge gate
scripts/unattended.sh status
```

This writes `.claude/settings.local.json`, which is gitignored, so the committed posture never changes. **Every change
still goes through a branch and a PR** — the guard hook is untouched and the PR record stays complete. What changes is
who presses merge, and only when CI is green.

**Turn it on before an unattended run and off after.** `scripts/preflight.sh` reports which mode is active.

---

## Terminal Conditions

**A run needs somewhere to stop, or it will not.** Stopper #5.

The MVP is done when [`PRODUCT.md`](PRODUCT.md#definition-of-done-for-the-mvp) is satisfied:

> A user in KL can state a preference and receive a ranked shortlist where every entry cites a real post, sourced from a
> locally persisted corpus, with the app functioning normally while its primary source is unreachable.

Point every run at a **named, checkable** subset of that, never at "make progress". Good: _"ingest 200 KL posts into the
corpus schema with ≥80% carrying a location field."_ Bad: _"work on ingestion."_

Before starting an unattended run, write the terminal condition into `PROGRESS.md`. On waking, check it first.

---

## What Still Stops You

Four things, and nothing else. These are not blockers to route around — they are the boundary of the standing
authorization.

1. **Spending real money** beyond credentials already in `.env` — a paid plan, a new subscription, an upgrade
2. **Anything irreversible outside this repo** — deleting or renaming the GitHub repo, force-pushing published history,
   revoking a key, deploying to a domain someone else uses, sending anything to a third party in the owner's name
3. **A legal or platform-terms question that a technical default cannot answer.** Rate-limiting harder, caching longer
   and collecting less are always available and always authorized; deciding whether to collect a category of data at all
   is not
4. **Evidence the product premise is dead** — the spike shows Xiaohongshu data cannot be pulled at usable volume _and_
   no fallback source carries enough signal. Do not scaffold around a corpus that cannot exist. Write the finding up,
   open an issue, stop

For all four: write the finding to `PROGRESS.md`, open a GitHub Issue with what you tried, and **continue with any
independent work that remains**. Stopping the run entirely is only for #4.

**Everything else is authorized.** If you are reading this file to decide whether to ask, the answer is no — decide,
record it, keep going.
