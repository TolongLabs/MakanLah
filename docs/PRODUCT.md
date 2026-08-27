# MakanLah — Product Definition

> Status: pre-scaffold. Nothing is built yet. This document states intent and the decisions that are still open, so that
> later work can be checked against it.

## What it is

A web and mobile-friendly app that recommends restaurants near the user, ranked by personal preference, drawing on real
recommendations that Malaysians actually write — primarily Xiaohongshu / RedNote, plus other social platforms.

The bet: Malaysians already decide where to eat by scrolling social recommendations. That signal is richer than star
ratings but it is unstructured, in mixed English/Malay/Chinese, and scattered. MakanLah's job is to turn it into
something queryable and local.

## Users and the core loop

A user in Kuala Lumpur, hungry, deciding in under two minutes.

```
open → state preference (cuisine, budget, distance, mood)
     → ranked shortlist with the actual social posts behind each pick
     → pick one → directions
```

The differentiator is the third step: **show the evidence**. A recommendation that cites the post it came from is
trustworthy in a way a generated blurb is not.

## Agent surface

Hermes Agent powers two distinct workloads. They are listed separately because they have opposite characteristics and
should not share a runtime:

| Workload  | Shape                           | Constraint                    |
| --------- | ------------------------------- | ----------------------------- |
| Copilot   | Interactive, one user at a time | Low latency; user is waiting  |
| Ingestion | Batch, scheduled, high volume   | Throughput; nobody is waiting |

Coupling these means a scraping run degrades the interactive experience. Separate them from the start.

## Data sources

Xiaohongshu is the primary target and the primary risk. It gates most content behind login, fingerprints devices, and
rate-limits aggressively. Its terms prohibit automated collection.

**Design rule: no single source may be load-bearing.** Not for legal cover — for uptime. Any one platform can go dark
mid-sprint, and an app whose data layer has a single point of failure will go dark with it.

Practical consequences:

- Aggregate across several platforms so the app degrades rather than dies
- Cache aggressively; never fetch live on a user request
- Persist a normalized local corpus — the app reads the corpus, not the platform
- Treat freshness as a background concern, not a request-path concern

Tooling is undecided. Scrapling is installed locally; Firecrawl credits (~20k) are available. Firecrawl likely bounces
off login-walled content; Scrapling with an authenticated session is more plausible but fiddly. **Resolve this with a
spike, not a discussion** — see Risks.

## Scope

**MVP** — one city (KL), one primary source plus one fallback, preference input, ranked results with source citations,
directions handoff.

**Not MVP** — accounts, reviews, bookings, social features, multi-city, real-time availability.

## Open decisions

| Decision        | Options                                       | Resolve by                    |
| --------------- | --------------------------------------------- | ----------------------------- |
| Scraper stack   | Scrapling vs Firecrawl vs both                | Day-0 spike                   |
| Corpus store    | Flat files vs SQLite vs hosted DB             | After spike shows data volume |
| Ranking         | Embedding similarity vs LLM re-rank vs hybrid | After corpus exists           |
| Mobile delivery | PWA vs native shell                           | Before UI work starts         |

## Risks, ordered

1. **Xiaohongshu access is the whole project's risk.** If structured data cannot be pulled at usable volume, MakanLah
   has no product and every hour of scaffolding before that is proven is wasted. Spike first, scaffold second.
2. **Evasion is an arms race with someone else's release schedule.** Techniques break without warning. Multi-source
   aggregation and caching are the durable answers; evasion is at best a stopgap.
3. **Language mix.** Posts are English/Malay/Chinese, often within one sentence. Extraction and ranking must handle this
   or results will be silently biased toward whichever language the pipeline handles best.
4. **Free worker tier expires 2026-09-23** with the Devin Pro plan. See `SWARM.md`.

## Definition of done for the MVP

A user in KL can state a preference and receive a ranked shortlist where every entry cites a real post, sourced from a
locally persisted corpus, with the app functioning normally while its primary source is unreachable.
