# MakanLah

Find somewhere good to eat nearby, based on what Malaysians actually recommend.

A web and mobile-friendly app that ranks restaurants by personal preference, drawing on
real social recommendations — primarily Xiaohongshu / RedNote, plus other platforms —
and showing the posts behind every pick.

> **Status: pre-scaffold.** No code yet. These documents state intent and the plan for
> building it, so later work can be checked against them.

## Documents

| Doc | What it covers |
|---|---|
| [`PRODUCT.md`](./PRODUCT.md) | What MakanLah is, users, scope, data-source policy, open decisions, risks |
| [`SWARM.md`](./SWARM.md) | How it gets built — GSD orchestration, worker contract, model lanes, measurements |

## Start here

**The Xiaohongshu spike comes before everything.** RedNote gates content behind login,
fingerprints devices, and rate-limits hard. If structured data cannot be pulled at
usable volume, MakanLah has no product — and every hour of scaffolding spent before
that is proven is wasted.

One orchestrator session, timeboxed, no workers. The question it answers:

> Can we pull ~50 KL restaurant posts with structured fields (name, location, dish,
> sentiment) into a normalized record?

Only after that returns does `/gsd-new-project` make sense.

## Stack

- **Agent runtime** — Hermes Agent, split into two workloads: interactive copilot and
  batch ingestion. Separate runtimes; see `PRODUCT.md`.
- **Scraping** — undecided. Scrapling and Firecrawl are both candidates; the spike
  decides.
- **Orchestration** — GSD (`npm i -g get-shit-done`), Claude Opus 5 `xhigh`.
- **Workers** — SWE-1.7 via Devin CLI (free until 2026-09-23), GLM-5.3-Flash via
  OpenRouter as fallback.

## Two dates that constrain the plan

| Date | What changes |
|---|---|
| **2026-09-09** | GLM-5.3-Flash promo ends; token pricing doubles |
| **2026-09-23** | Devin Pro lapses; free SWE-1.7 worker tier likely goes with it |

Both land near production. Keep worker dispatch model-agnostic — see `SWARM.md` §4.

## Design principle

No single data source may be load-bearing. Not for legal cover, for uptime: any one
platform can go dark mid-sprint, and an app whose data layer has a single point of
failure goes dark with it. Aggregate across platforms, cache hard, persist a normalized
local corpus, and read from the corpus rather than the platform.
