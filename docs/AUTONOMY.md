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

Three rules that make this hold:

1. **Never claim something works without having run it and read the output.** The `verification-before-completion` skill
   is not optional here — a self-report is not evidence, and [`SWARM.md`](SWARM.md#7-measurements) measured a worker
   producing confident output that failed hidden tests
2. **Never merge a worker's output on its self-report.** Assert the artifact exists, then run the test the worker never
   saw
3. **Never disable a check to go green.** Narrowing the change is always available; silencing the check is not

### Unattended Mode

`main` is PR-gated and agents are denied `gh pr merge`, which is correct when a human is present and **will stall an
unattended run at the first PR**.

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
