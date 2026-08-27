# MakanLah

Find somewhere good to eat nearby, based on what Malaysians actually recommend.

A web and mobile-friendly app that ranks restaurants by personal preference, drawing on real social recommendations —
primarily Xiaohongshu / RedNote, plus other platforms — and showing the posts behind every pick.

|                |                                                                                               |
| -------------- | --------------------------------------------------------------------------------------------- |
| **Status**     | Pre-scaffold. No application code. Scraper stack, corpus store and app framework all unchosen |
| **MVP city**   | Kuala Lumpur                                                                                  |
| **Blocked on** | The Xiaohongshu access spike. Nothing else starts until it returns                            |

---

## The One Rule That Governs Everything

> **No single data source may be load-bearing.** Not for legal cover — for uptime. Any one platform can go dark
> mid-sprint, and an app whose data layer has a single point of failure goes dark with it.

Aggregate across platforms, cache hard, persist a normalized local corpus, and read from the corpus rather than the
platform. Never fetch live on a user request.

---

## Start Here

**The Xiaohongshu spike comes before everything.** RedNote gates content behind login, fingerprints devices, and
rate-limits hard. If structured data cannot be pulled at usable volume, MakanLah has no product — and every hour of
scaffolding spent before that is proven is wasted.

One orchestrator session, timeboxed, no workers. The question it answers:

> Can we pull ~50 KL restaurant posts with structured fields — name, location, dish, sentiment — into a normalized
> record?

Only after that returns does `/gsd-new-project` make sense.

| File                               | What's In It                                                                                                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`PRODUCT.md`](PRODUCT.md)         | What MakanLah is, users, scope, data-source policy, open decisions, risks                                                                                        |
| [`AUTONOMY.md`](AUTONOMY.md)       | **Read this before deciding you are blocked.** Standing authorization, a pre-made default for every open decision, and the four things that genuinely stop a run |
| [`SWARM.md`](SWARM.md)             | How it gets built — GSD orchestration, worker contract, model lanes, measurements                                                                                |
| [`PROGRESS.md`](PROGRESS.md)       | Where the work actually is. Rewritten every session, printed at every start                                                                                      |
| [`CREDENTIALS.md`](CREDENTIALS.md) | Every login a human must do once, before an unattended run starts                                                                                                |
| [`../AGENTS.md`](../AGENTS.md)     | Project instructions for agentic tools, and humans                                                                                                               |

Work in progress lives in the [Issues board](https://github.com/TolongLabs/MakanLah/issues), not in a checklist here.

---

## Getting Started

```bash
scripts/bootstrap.sh         # provision the machine. Idempotent; --check to dry-run
cp .env.example .env         # then fill in what CREDENTIALS.md says you must
scripts/preflight.sh         # will an unattended run get stuck on setup?
```

Before a long unattended run, `scripts/unattended.sh on` allows self-merge on green CI — without it the run stalls at
the first PR, because step 4 of **How Work Ships** has nobody to perform it. Turn it off afterwards.

| Command             | Does                               |
| ------------------- | ---------------------------------- |
| `bun run lint`      | Biome check, then Prettier check   |
| `bun run format`    | Both formatters, writing in place  |
| `bun run typecheck` | `tsc --noEmit`, once `src/` exists |
| `gh issue list`     | The TODO board                     |

Biome covers JS, TS, JSON, CSS and HTML; Prettier covers the Markdown and YAML it cannot, wrapping prose at 120 to match
`biome.json`'s `lineWidth`. There is no `.prettierignore`, so every Markdown file is formatted, `docs/source/` and the
vendored skills included. Only the contents of fenced code blocks are left alone.

**There is no Python stack yet.** The spike is the first thing that creates one. When it does, `uv` and `ruff` are added
here and to `lint-staged` in the same change.

---

## Architecture, Such As It Is

Two agent workloads on **Hermes Agent**, deliberately not sharing a runtime:

| Workload      | Shape                           | Constraint                     |
| ------------- | ------------------------------- | ------------------------------ |
| **Copilot**   | Interactive, one user at a time | Low latency; a user is waiting |
| **Ingestion** | Batch, scheduled, high volume   | Throughput; nobody is waiting  |

Coupling them means a scraping run degrades the interactive experience.

The core loop, and the reason the third step is the product:

```
open → state preference (cuisine, budget, distance, mood)
     → ranked shortlist with the actual social posts behind each pick
     → pick one → directions
```

**Application framework, database, hosting and scraper stack are not chosen.** They get chosen and justified in
`TRD.md`, which does not exist yet. `PRODUCT.md` carries the open-decisions table and when each is due.

---

## Two Dates That Constrain The Plan

| Date           | What Changes                                                       |
| -------------- | ------------------------------------------------------------------ |
| **2026-09-09** | GLM-5.3-Flash promo ends; token pricing doubles                    |
| **2026-09-23** | Devin Pro lapses; the free SWE-1.7 worker tier likely goes with it |

Both land near production. Keep worker dispatch model-agnostic — see [`SWARM.md`](SWARM.md#4-worker-contract). The
`session-brief` hook counts down both at the start of every session.

---

## How Work Ships

**`main` is PR-gated.** Branch as `<type>/<slug>`, open a PR with `gh pr create`, merge with
`gh pr merge --squash --delete-branch`. A human merges; nobody merges their own PR. `.claude/hooks/guard-git.sh`
enforces it.

**Implementation is gated on three docs.** `PRODUCT.md` (who and why), `PRD.md` (what, and what is out of scope) and
`TRD.md` (how) must all exist before build work starts. `DESIGN.md` joins them when frontend work does.

**Workers are gated on tests.** A task belongs to a worker only if a failing test can be written for it first, and no
worker's output is merged on its self-report. `SWARM.md` §4 is the contract.

---

## Layout

```
docs/
  README.md              this file, the GitHub-facing readme
  PRODUCT.md             who, why, scope, open decisions, risks
  AUTONOMY.md            standing authorization, pre-made defaults, what stops a run
  SWARM.md               how it gets built: GSD, workers, model lanes, measurements
  PROGRESS.md            session checkpoint. The only thing that survives compaction
  CREDENTIALS.md         every human-gated login, done once, before an unattended run
  PRD.md                 what: requirements, acceptance criteria, out of scope
  TRD.md                 how: architecture, contracts, corpus schema. Canonical
  DESIGN.md              the design system, once frontend work starts
  coding-guidelines.md   behavioural coding rules, referenced by AGENTS.md
  agent-tooling.md       rtk and graphify, both optional and per-machine
  source/                captured reference material, append-only
  superpowers/research/  cited findings from exploration
makanlah/                the shared library. Both runtimes import it, neither shares runtime state
  config.py              settings from the environment. Names keys, never prints a value
  text.py                venue normalization and language detection. Used by both runtimes
  db.py                  the only module that speaks SQL
  models.py              extract, embed and re-rank clients
  rank.py                the four ranking stages
  migrations/            the corpus schema as Postgres
  research/              measurement scripts whose results live in docs/superpowers/research/
ingest/                  batch, on the workstation. Holds the browser session. Never serves a request
  cdp.py                 CDP client. Every call bounded, because a crashed tab hangs silently
  rednote.py             the primary source. Targets the host, not the brand
  gmaps.py               the second source. No API key; the place URL carries coordinates
  capture_rednote.py     fetch to the raw cache. Separate from extraction on purpose
  pipeline.py            store raw -> extract -> resolve venue -> geocode -> embed
  enrich_gmaps.py        fill coordinates and take Maps reviews as evidence
  geocode.py             Nominatim. Kept as fallback; Maps resolves far more of this corpus
api/main.py              interactive, hosted. Reads the corpus and never scrapes
web/                     the static client. Vite + React, installable, holds no secret
tests/                   pytest, entirely against fixtures. Never touches a live platform
scripts/
  bootstrap.sh           provision a fresh machine. Idempotent
  preflight.sh           will an unattended run get stuck on setup? Ask before it does
  chrome-session.sh      CDP-controllable Chrome carrying the signed-in session
  dev-api.sh             run the API locally against the corpus
  unattended.sh          toggle self-merge-on-green-CI
  dispatch-worker.sh     model-agnostic worker dispatch. SWARM.md §4 as code
.github/workflows/ci.yml lint, typecheck, and the guards. Unattended, this is the reviewer
.agents/skills/          29 skills, the committed source of truth
.claude/skills/          symlinks into .agents/skills/, plus impeccable as a real dir
.claude/hooks/           session brief, env drift, git guard, formatter, checkpoint reminder
```

**Three deployables, one library.** `ingest/` and `api/` share `makanlah/` and share nothing at runtime: separate
processes, separate hosts, separate failure domains. `api/` must never import from `ingest/` — that is where the browser
session and the scrapers live, and the API host has neither.

**Fetching and extraction are separate commands on purpose.** Fetching is slow, rate-limited and can fail halfway;
extraction is fast and replayable. Raw captures live on disk, so a schema or prompt change costs nothing to re-run,
where re-scraping costs a rate limit and possibly a session.

The day-0 spike's own runner has been folded into `ingest/` now that it is the production path. What it proved is
recorded in [`TRD.md`](TRD.md#what-the-spike-changed), and its redacted capture is in [`source/`](source/).

Skill provenance: [`../.agents/skills/VENDORED.md`](../.agents/skills/VENDORED.md).

The repo root deliberately has **no README**. It lives here.
