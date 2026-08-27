# TRD — Technical Reference

**How MakanLah is built.** Canonical over `AGENTS.md` on anything technical. Cites [`PRODUCT.md`](PRODUCT.md) for what
and why, and never restates [`README.md`](README.md) — that is the outside reader's document, this one is for whoever
implements against it.

> **Status: pre-spike.** The corpus schema below is written against what a Xiaohongshu post is expected to contain. The
> spike is what proves it. **Expect the schema to change once real data lands**, and change it — a schema that survives
> contact with zero real records has not been validated, only asserted.

---

## Architecture

Three deployables. The two-runtime split [`PRODUCT.md`](PRODUCT.md#agent-surface) requires is real process isolation,
not a module boundary.

| Deployable | Runs                           | Shape                              | Constraint                         |
| ---------- | ------------------------------ | ---------------------------------- | ---------------------------------- |
| `ingest/`  | The workstation, on a schedule | Batch, high volume, nobody waiting | Throughput. Never serves a request |
| `api/`     | Fly.io, Singapore              | Interactive, one user at a time    | Latency. Never scrapes             |
| `web/`     | Cloudflare Pages or Vercel     | Static SPA                         | First paint. Holds no secret       |

```
workstation                          hosted
───────────                          ──────
ingest/  ──scrape──▶ platforms
         ──geocode─▶ Nominatim
         ──extract─▶ ModelScope
         ──write────────────────────▶ Neon
                                       ▲
browser ──▶ web/ (static) ──▶ api/ ────┘
                               └──rerank──▶ Hermes
```

**Every arrow leaving the workstation points away from it.** It accepts no inbound connection, so its address is never
exposed — see [`AUTONOMY.md`](AUTONOMY.md#the-workstation-is-never-publicly-reachable). A change that appears to need
inbound access to it is the wrong change.

### Shared Code, Separate Processes

`ingest/` and `api/` both import a `makanlah/` package holding the corpus schema, the database layer, and the model
clients. **They share libraries and share nothing at runtime** — separate processes, separate hosts, separate failure
domains.

This is why the API is Python rather than a Next.js server. Written in TypeScript, the corpus schema, embedding client
and model clients would each exist twice, and the two copies would drift.

---

## Corpus Schema

**The highest-value contract in the project.** Ingestion writes it, ranking reads it, the UI renders it, and it is the
one thing a worker can be handed a failing test against.

### `source_post` — The Evidence

One row per social post. **This table is the product.** A recommendation that cannot reach a row here is not a
recommendation.

| Column             | Type          | Notes                                                           |
| ------------------ | ------------- | --------------------------------------------------------------- |
| `id`               | `uuid` PK     |                                                                 |
| `platform`         | `text`        | `xhs`, `google_maps`, `instagram`, … Never null                 |
| `platform_post_id` | `text`        | Unique with `platform`. The dedup key across re-ingestion       |
| `url`              | `text`        | Where a human verifies the citation. Never null                 |
| `author_handle`    | `text`        | Attribution                                                     |
| `posted_at`        | `timestamptz` | The post's own date. Nullable — many platforms hide it          |
| `captured_at`      | `timestamptz` | When we fetched it. Never null                                  |
| `langs`            | `text[]`      | Detected, plural. A single-language column would erase the mix  |
| `raw_text`         | `text`        | Verbatim. Never a translation or a summary                      |
| `media_urls`       | `text[]`      | Referenced, never rehosted                                      |
| `raw_payload`      | `jsonb`       | What the scraper saw, so a schema change can re-extract offline |

`unique (platform, platform_post_id)`.

**`raw_payload` is what makes the schema survivable.** Re-extracting from stored payloads costs nothing; re-scraping
costs a rate limit and possibly a session.

### `venue` — The Restaurant

| Column               | Type      | Notes                                                              |
| -------------------- | --------- | ------------------------------------------------------------------ |
| `id`                 | `uuid` PK |                                                                    |
| `name`               | `text`    | As written, in its own script                                      |
| `name_normalized`    | `text`    | Case-folded, punctuation-stripped. The join key for dedup          |
| `aliases`            | `text[]`  | The same place across languages: 亚洲之味 / Asian Flavour          |
| `lat`, `lng`         | `double`  | Null until geocoded. **Nullable is the normal state**              |
| `geohash`            | `text`    | Coarse prefix index for the distance filter                        |
| `address`, `area`    | `text`    | `area` is what a user recognises: Bangsar, SS15                    |
| `city`               | `text`    | `Kuala Lumpur` for the MVP                                         |
| `geocoder`           | `text`    | `nominatim` \| `google_places`. Which one produced the coordinates |
| `geocode_confidence` | `real`    | Below threshold, the venue is unrankable by distance, not deleted  |
| `place_id`           | `text`    | Google Places only. Sharpens the directions deep link              |

**Geocoding runs at ingestion, never on the request path.** Once per venue, nobody waiting — which is why a
one-request-per-second free service is adequate and no key is needed at request time.

### `mention` — The Citation

The many-to-many, and the reason it exists: one post can name five restaurants, and one restaurant accumulates many
posts.

| Column            | Type          | Notes                                                         |
| ----------------- | ------------- | ------------------------------------------------------------- |
| `id`              | `uuid` PK     |                                                               |
| `post_id`         | `uuid` FK     | → `source_post`, `on delete cascade`                          |
| `venue_id`        | `uuid` FK     | → `venue`                                                     |
| `dishes`          | `text[]`      | As named in the post, not translated                          |
| `sentiment`       | `real`        | −1…1                                                          |
| `price_band`      | `smallint`    | 1–4, nullable. Most posts do not say                          |
| `excerpt`         | `text`        | The span the extraction came from. **What the UI shows**      |
| `extractor_model` | `text`        | Which model produced this, so a bad run is revocable by model |
| `extracted_at`    | `timestamptz` |                                                               |
| `confidence`      | `real`        |                                                               |

`unique (post_id, venue_id)`.

**`excerpt` is what makes the evidence visible.** A citation that is only a link asks the user to leave and verify; an
excerpt shows the recommendation in the writer's own words, in the writer's own language.

### `venue_embedding`

| Column       | Type          | Notes                                                                  |
| ------------ | ------------- | ---------------------------------------------------------------------- |
| `venue_id`   | `uuid` FK PK  |                                                                        |
| `embedding`  | `vector(n)`   | pgvector. `n` fixed by the chosen model                                |
| `model`      | `text`        | Part of the key in practice — embeddings from two models never compare |
| `created_at` | `timestamptz` |                                                                        |

Embed a composite of venue name, aliases, dishes and mention excerpts — **not** the raw posts. The retrievable unit is a
venue; posts are evidence attached to it.

### The One Invariant

> **Every ranked result joins to at least one `source_post` through `mention`.**

Checkable in SQL, so it is a test rather than a principle — and therefore a legitimate worker task under
[`SWARM.md`](SWARM.md#4-worker-contract) §4.

---

## Ranking

Four stages. Only the third calls a model, and only the third is expensive.

| Stage        | Does                                                              | Cost                        |
| ------------ | ----------------------------------------------------------------- | --------------------------- |
| **Filter**   | Distance, budget, cuisine → candidate venues                      | SQL. Cheap                  |
| **Retrieve** | pgvector cosine, query embedding vs `venue_embedding` → top ~50   | One index scan              |
| **Re-rank**  | Model sees query + venue summaries + excerpts → top 10 with a why | One call, latency-sensitive |
| **Attach**   | Join citations back onto each result                              | SQL                         |

**Filter before retrieve.** A vector search over every KL venue then filtered by distance wastes the index and returns a
great match forty minutes away.

**Citations are attached in stage 4, from the database — never generated by the model in stage 3.** A model asked to
produce a URL will produce a plausible one. The re-rank returns venue ids and a reason; the link and excerpt come from
`mention`.

**Venues with null coordinates are excluded from distance-filtered queries, not deleted.** They stay rankable by
preference once geocoding catches up.

---

## Model Lanes

Split along the same seam as the runtimes, for the same reason.

| Job         | Where                    | Why                                                                                                                                                  |
| ----------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Extract** | ModelScope (Qwen)        | Batch, high volume, latency-tolerant. Qwen is strong on Chinese, and the corpus is Xiaohongshu. China-hosted latency is irrelevant when nobody waits |
| **Embed**   | **Undecided**            | The one open row. Decide by measurement — see below                                                                                                  |
| **Re-rank** | Hermes, interactive lane | A user is waiting. Never ModelScope: the latency that is free in batch is disqualifying here                                                         |

### The Embedding Decision

`PRODUCT.md` risk #3 is EN/MS/ZH inside one sentence, and this is where a stack fails silently — retrieval biases toward
whichever language the model handles best, and it looks like it is working.

| Candidate                      | Trade                                                                    |
| ------------------------------ | ------------------------------------------------------------------------ |
| Qwen embedding via ModelScope  | Free if the existing quota covers it. **Check this first**               |
| Cohere `embed-multilingual-v3` | Hosted, strong on Malay and Chinese, per-token cost                      |
| BGE-M3, self-hosted            | Free, dense+sparse suits hybrid retrieval, slow on the workstation's CPU |

**Decide by measurement, not argument.** The test: a held-out set of KL venues, queried in each of the three languages,
checking whether the same venue is retrieved regardless of query language. A model that scores well in English and
poorly in Malay has failed, not partly passed. Write the result to `superpowers/research/`.

---

## API Contract

```
POST /recommend
  { query, lat, lng, radius_m, budget?, cuisine?, limit? }
→ { results: [ { venue: {id, name, area, lat, lng, maps_url},
                 score, why,
                 citations: [ {post_url, excerpt, platform, author_handle, posted_at} ] } ],
    degraded: bool, sources_used: [string] }

GET /health → { ok, corpus_size, oldest_capture, newest_capture }
```

`citations` is **never empty**. An entry that cannot be cited is dropped before the response is built, not returned with
a caveat.

`degraded` is true when a source was unreachable at last ingestion. The app keeps working — that is the whole point of
not letting one source be load-bearing — but the UI can say so honestly.

`maps_url` is built server-side as a Google Maps deep link. **No maps SDK, no key, no billing.** With a `place_id`, it
disambiguates a chain with twenty branches.

---

## Ingestion Pipeline

```
discover → fetch → store raw → extract → resolve venue → geocode → embed
```

Each stage is **resumable and idempotent**, keyed on `(platform, platform_post_id)`. A stage that fails records the
failure and continues the batch — never aborts it ([`AUTONOMY.md`](AUTONOMY.md#standing-operational-defaults)).

| Stage             | Notes                                                                                                                 |
| ----------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Fetch**         | Firecrawl for open web; CDP against the signed-in Chrome profile for Xiaohongshu                                      |
| **Store raw**     | Before extraction, always. A schema change must never require re-scraping                                             |
| **Extract**       | One prompt handling all three languages. Never a per-language path                                                    |
| **Resolve venue** | Match on `name_normalized` and proximity. Ambiguity creates a new venue — merging is safe later, a wrong merge is not |
| **Geocode**       | Nominatim, one request per second, contact address in the User-Agent per its usage policy                             |

**Rate limiting and caching are the durable answers, not evasion** ([`AGENTS.md`](../AGENTS.md#critical-do-nots)).
Collect modestly, cache hard, and keep the whole thing easy to turn off.

---

## Testing

The worker contract needs a failing test before a task exists, so these are infrastructure, not hygiene.

| Layer       | Tool       | Covers                                                            |
| ----------- | ---------- | ----------------------------------------------------------------- |
| `makanlah/` | pytest     | Schema validation, venue resolution, the citation invariant       |
| `ingest/`   | pytest     | Each stage against **stored fixtures**, never a live platform     |
| `api/`      | pytest     | Contract shape, and that no result ever ships with zero citations |
| `web/`      | Vitest     | Rendering, including a mixed EN/MS/ZH result                      |
| End-to-end  | Playwright | The core loop against a seeded corpus                             |

**Every test runs against fixtures.** A suite that hits Xiaohongshu is a suite that fails when a session expires, and a
red check that means nothing trains everyone to ignore red checks.

Fixtures are redacted single posts in `docs/source/`, never a corpus dump.

---

## Deferred

Out of MVP scope in [`PRODUCT.md`](PRODUCT.md#scope), and named here so nobody builds toward them: accounts, reviews,
bookings, social features, multi-city, real-time availability.

Two consequences worth stating, because they are what make the MVP cheap:

- **No accounts means no auth, no sessions, no PII.** It is why Neon suffices and a platform like Supabase is not needed
- **No real-time availability means the corpus can be stale.** Freshness is a background concern, so ingestion can fail
  for a day without the app noticing

---

## Open Rows

| Row                    | Resolved By                                                            |
| ---------------------- | ---------------------------------------------------------------------- |
| **Embedding model**    | The three-language retrieval test above                                |
| **Corpus volume**      | The spike. Determines whether the schema needs partitioning at all     |
| **Fallback sources**   | Which platforms carry enough KL signal. Prefer ones needing no session |
| **Ingestion schedule** | After the first full run gives a wall-clock number                     |

Everything else in [`PRODUCT.md`](PRODUCT.md#open-decisions) is closed, with the reasoning in
[`AUTONOMY.md`](AUTONOMY.md#pre-authorized-defaults).
