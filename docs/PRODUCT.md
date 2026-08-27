# MakanLah — Product Definition

> **Status: built and running, 2026-08-27.** This document states intent; [`PROGRESS.md`](PROGRESS.md) states where the
> work actually is. It is still the spine — everything downstream cites it — so the intent below has not been rewritten
> to match what got built. Where they differ, that is a finding, not a typo.

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

**Resolved by the spike.** Two sources, neither load-bearing:

| Source          | Carries                                           | Auth                             |
| --------------- | ------------------------------------------------- | -------------------------------- |
| **RedNote**     | Long-form posts, often naming many venues at once | A signed-in Chrome profile, CDP  |
| **Google Maps** | Per-venue reviews, coordinates, `place_id`        | **None.** No API key, no billing |

**The host is the identity, not the brand.** `xiaohongshu.com` was logged out on the build machine while `rednote.com`,
serving the same content, was signed in. An adapter written against the brand would have concluded the source was dead.

Firecrawl stays configured for open-web fallbacks and has not been needed yet. Scrapling was not used: CDP against the
signed-in browser covers the same ground with fewer moving parts.

## Scope

**MVP** — one city (KL), one primary source plus one fallback, preference input, ranked results with source citations,
directions handoff.

**Not MVP** — accounts, reviews, bookings, social features, multi-city, real-time availability.

## Decisions, Now Closed

Every row below was open on day zero. The reasoning for each is in [`TRD.md`](TRD.md).

| Decision            | Taken                                                           | Decided By                                                     |
| ------------------- | --------------------------------------------------------------- | -------------------------------------------------------------- |
| **Scraper stack**   | CDP against a signed-in Chrome, for both sources                | The spike                                                      |
| **Corpus store**    | Neon, Postgres + pgvector, `ap-southeast-1`                     | Concurrent writers: app reads remotely, ingest writes locally  |
| **Ranking**         | Hybrid — filter, pgvector retrieve, model re-rank, attach cites | Filter before retrieve, so distance is not wasted on the index |
| **Mobile delivery** | PWA. Responsive, installable, no app store                      | An install is a five-minute tax on a two-minute promise        |
| **Embedding model** | DashScope `text-embedding-v3`, 1024-dim                         | **Measured**: en 8/8, ms 7/8, zh 8/8                           |
| **Geocoding**       | Google Maps over CDP; Nominatim as fallback                     | **Measured**: Nominatim resolved 34%                           |

**Still open:** which further platforms carry enough KL signal, and how often ingestion should run.

## Risks, ordered

1. ~~**Xiaohongshu access is the whole project's risk.**~~ **Retired.** The spike pulled 50 posts into 137 venues and
   150 mentions with zero extraction failures, and a second keyless source now carries more posts than the first. The
   risk that replaced it is narrower: **both sources are scraped, so both can change shape without warning.** Caching
   hard and keeping the corpus local is what makes that survivable.
2. **Evasion is an arms race with someone else's release schedule.** Techniques break without warning. Multi-source
   aggregation and caching are the durable answers; evasion is at best a stopgap.
3. **Language mix.** Posts are English/Malay/Chinese, often within one sentence. Extraction and ranking must handle this
   or results will be silently biased toward whichever language the pipeline handles best.
4. **Free worker tier expires 2026-09-23** with the Devin Pro plan. See `SWARM.md`.

## Definition of done for the MVP

A user in KL can state a preference and receive a ranked shortlist where every entry cites a real post, sourced from a
locally persisted corpus, with the app functioning normally while its primary source is unreachable.
