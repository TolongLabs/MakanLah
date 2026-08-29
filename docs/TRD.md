# TRD — Technical Reference

**How MakanLah is built.** Canonical over `AGENTS.md` on anything technical. Cites [`PRODUCT.md`](PRODUCT.md) for what
and why, and never restates [`README.md`](README.md) — that is the outside reader's document, this one is for whoever
implements against it.

> **Status: post-spike, 2026-08-27.** The schema below has met real records and changed where they broke it. What the
> spike altered is listed in [What The Spike Changed](#what-the-spike-changed) at the end, with the reason for each.
> Everything not listed there survived contact unchanged.

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
| `platform`         | `text`        | `rednote`, `google_maps`, `instagram`, … Never null. See below  |
| `platform_post_id` | `text`        | Unique with `platform`. The dedup key across re-ingestion       |
| `url`              | `text`        | Where a human verifies the citation. Never null                 |
| `author_handle`    | `text`        | Attribution                                                     |
| `posted_at`        | `timestamptz` | Parsed date. **Usually null** — see `posted_at_raw`             |
| `posted_at_raw`    | `text`        | Verbatim. RedNote renders `Feb 17` and `3 days ago`, no year    |
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

| Column            | Type          | Notes                                                            |
| ----------------- | ------------- | ---------------------------------------------------------------- |
| `id`              | `uuid` PK     |                                                                  |
| `post_id`         | `uuid` FK     | → `source_post`, `on delete cascade`                             |
| `venue_id`        | `uuid` FK     | → `venue`                                                        |
| `dishes`          | `text[]`      | As named in the post, not translated                             |
| `sentiment`       | `real`        | −1…1                                                             |
| `price_band`      | `smallint`    | 1–4, nullable. Most posts do not say                             |
| `excerpt`         | `text`        | The span the extraction came from. **What the UI shows**         |
| `excerpt_origin`  | `text`        | `model` \| `repaired` \| `dropped`. How the excerpt was obtained |
| `extractor_model` | `text`        | Which model produced this, so a bad run is revocable by model    |
| `extracted_at`    | `timestamptz` |                                                                  |
| `confidence`      | `real`        |                                                                  |

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

> **1. Every ranked result joins to at least one `source_post` through `mention`.**
>
> **2. Every stored `excerpt` is a substring of its post's `raw_text`.**

Both are checkable in SQL, so they are tests rather than principles — and therefore legitimate worker tasks under
[`SWARM.md`](SWARM.md#4-worker-contract) §4.

**The second invariant is enforced by a trigger, not by convention**, because the spike measured the extractor violating
it. Asked for the verbatim span an extraction came from, the model returned text that read correctly and was **not in
the post** — it had stitched non-contiguous lines together, dropping an opening-hours line between them. A fabricated
quote behind a citation is worse than no citation, and the failure is invisible on inspection because the output reads
well. `mention_excerpt_is_verbatim()` raises instead.

The write path repairs before it reaches the trigger: an excerpt that is not a substring is re-anchored on the venue
name to a real contiguous span (`repaired`), and if even that fails it is dropped and the citation falls back to the
post link (`dropped`). **`excerpt_origin` records which happened**, so a bad extractor run is revocable by origin as
well as by model.

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

### Which Excerpt Leads

`db.EXCERPT_ORDER` is the single definition, used by both `venues_with_citations` (stage 4) and `venue_evidence` (the
copilot). It orders on **what the excerpt says**, not on `mention.confidence`.

**Confidence is an anti-signal for readability.** It measures how easy the text was to extract, which is close to the
opposite of whether it is worth reading. Measured on the corpus of 2026-08-28:

| Confidence Band | Mentions | Mean Excerpt | Carries No Opinion |
| --------------- | -------- | ------------ | ------------------ |
| **≥ 0.95**      | 150      | 75.2 chars   | 14.0%              |
| **0.80 – 0.95** | 1553     | 180.0 chars  | 8.2%               |

A postal address is trivially extractable, so it scored highest and led. **82 of 243 venues (33.7%) led with an
address-shaped excerpt**, and 160 of 243 (65.8%) led with under 60 characters. Reordering cut those to **28 (11.5%)**
and **47 (19.3%)**; the remainder are venues where the corpus holds nothing better, which is
[#25](https://github.com/TolongLabs/MakanLah/issues/25), not an ordering problem.

The order is: does it argue anything (non-zero sentiment, ≥60 characters), then how close its sentiment sits to that
venue's own mean, then `mention.id`. **Representative rather than flattering** — the lead is neither the angriest review
nor the most glowing one, which is the only defensible answer to "why this excerpt and not another". The final key makes
it total, so the same query returns the same excerpt twice running; the old ordering left ties to whatever Postgres
returned.

**This cost ranking a little, and the trade is deliberate.** The re-rank prompt embeds excerpts, so changing them
changes what the model sees. Full eval, 3 repeats, against the previous baseline: **p@5 0.984 → 0.982**, **p95 4.66s →
4.36s**, **top1 51/51 → 49/51**. The entire top1 loss is `matcha`. Pin lines name the venue and its dish, so they match
a keyword query well while telling a reader nothing, and ranking was quietly leaning on that. Tracked as
[#26](https://github.com/TolongLabs/MakanLah/issues/26).

---

## Model Lanes

Split along the same seam as the runtimes, for the same reason.

| Job         | Where                                                  | Why                                                                                                                                                                                                                                                 |
| ----------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Extract** | **DashScope `qwen-plus-2025-07-28`**                   | Batch, high volume, latency-tolerant. Qwen is strong on Chinese, and the corpus is RedNote. **ModelScope was the pre-spike assumption and no key for it exists**; the owner holds an International/Singapore DashScope key, which is also nearer KL |
| **Embed**   | **DashScope `text-embedding-v3`**, 1024-dim            | Decided by measurement, not argument. Free under the same key. See below                                                                                                                                                                            |
| **Re-rank** | **DashScope `qwen3.7-flash-2026-07-15`**, thinking off | A user is waiting, and this lane is ~94% of request latency. Dated, and the only flash lane carrying free quota: the rolling `qwen3.8-flash` reads `Not Supported`, so every call was billed (#34)                                                  |

### Every Lane Is Pinned To A Dated Snapshot

**The rolling aliases carry no free quota.** Measured against the ModelStudio console on 2026-08-28: `qwen-plus`,
`qwen-turbo`, `qwen-flash` and `qwen3.7-flash` all read **No Free Quota / Not Supported**, while the dated snapshots
carry **1,000,000 tokens each, expiring 2026-10-13**. An unpinned alias therefore moves onto a paid tier without
anything in the repo changing, which is why each lane names a date.

**`enable_thinking: false` is worth 9x on the interactive lane.** `qwen3.8-flash`, same prompts, same candidates:

| Thinking | Latency, three queries    |
| -------- | ------------------------- |
| On       | 4.06s / 15.48s / 20.75s   |
| **Off**  | **1.04s / 2.02s / 2.26s** |

The qwen3 tier is not slow, it reasons by default. `RERANK_THINKING=1` re-enables it; nothing should, on a lane with a
user waiting. Free-quota alternatives measured the same way: `qwen-plus-2025-07-28` 0.97/1.59/2.39s, `qwen-max`
1.68/7.72/4.83s, `qwen3.5-122b-a10b` 30-38s and unusable.

**Enable Stop-on-Exhaust in the console** so an exhausted lane returns `403 AllocationQuota.FreeTierOnly` rather than
billing silently.

### What A Request Costs, And The Ceiling That Bounds It

Measured 2026-08-29 by recording `usage` from the DashScope response, not estimated:

| Lane                                | Per `/recommend`              |
| ----------------------------------- | ----------------------------- |
| `text-embedding-v3`                 | 2–6 input tokens. Immaterial  |
| `qwen3.7-flash-2026-07-15`, re-rank | **~2,150 input, ~200 output** |

At Singapore list price — **$0.030/M input, $0.130/M output** for `qwen3.7-flash-2026-07-15` in the 0–32K tier, where
every prompt here sits — that is
**$0.00009 per `/recommend`**, about **RM 0.0004**. `qwen-plus` for extraction is
$0.40/M and $1.20/M.

**The previous lane, `qwen3.8-flash`, was $0.15/M and $0.47/M: 4.6× this, and with no free quota behind it.** Re-pinning
was worth more than any optimisation in this document.

| Workload                           | Cost        |
| ---------------------------------- | ----------- |
| A few visitors a day (~30 queries) | ~$0.013/day |
| One full eval run (54 calls)       | **~$0.02**  |
| Re-extracting the whole corpus     | **~$0.39**  |

**The free allowance is worth about $0.15**, so rationing eval runs is a false economy once billing is on. It is a cap
on availability, not a meaningful cost saving.

**The exposure is abuse, not usage.** An unbounded public `/recommend` at 10 req/s costs **~$363/day**. Three controls,
in order of how much they actually bound the bill:

1. **Stop-on-Exhaust in the console.** With billing off, the ceiling is the free quota and the failure mode is downtime,
   never an invoice. Strongest control, and the one outside our code
2. **`DAILY_BUDGET_MYR`**, default **RM 10**, metered in the currency the owner thinks in rather than in calls.
   `MYR_PER_CALL` is measured (RM 0.0019, from the token counts above at 4.4 to the dollar) and **must be re-measured
   whenever a lane is re-pinned**. The API degrades honestly when the day is spent
3. **`IP_DAILY_SHARE`**, default **10%** of the day per visitor. This is the anti-troll control: a loop burns its own
   slice, gets refused for the rest of the day, and every other visitor still gets answers. Without it a daily budget is
   just a bigger bucket for one attacker to drain. Behind Cloudflare the visitor is read from `CF-Connecting-IP`, which
   is trusted **only** when `TRUST_PROXY_HEADER` is set — a direct deployment must not trust it, or a spoofed header
   buys a fresh allowance
4. **Per-IP rate limits**, 20/min on `/recommend` and 10/min on `/ask`. Stops one noisy host, not a distributed one

**`ENABLE_DOCS`** keeps `/docs` and `/openapi.json` off unless asked for; there is no third-party developer audience,
and an endpoint map is free reconnaissance.

**CORS is a cost control here, not a credential one.** Auth is a `Bearer` header rather than a cookie, so
`allow_credentials` is off and no site can ride a signed-in session. Pinning `CORS_ORIGINS` to the Pages domain raises
the bar for a browser-based abuser and does nothing to `curl`, which is why the budget above is the real control.

### The Latency Budget, Now Met

`PRD.md` asks for **p95 < 3s**. The measured p95 is **2.89s**, on `qwen3.7-flash-2026-07-15`. It was missed for the life
of the project and the history below is kept because the reasoning still applies to the next lane change.

**It was not fixed by optimising anything.** Re-pinning the re-rank lane off the rolling `qwen3.8-flash` — which turned
out to carry no free quota at all ([#34](https://github.com/TolongLabs/MakanLah/issues/34)) — took p95 from **4.36s to
2.89s** and mean p@5 from 0.982 to 0.992 at the same time. The lane was the budget.

---

**The history, which is why the target was missed for so long.** The measured p95 was **4.66s**, and that was a stated
trade rather than an oversight.

**Re-rank is 93.9% of p95** — every other stage is rounding error:

| Stage         | Median | p95   | Share Of p95 |
| ------------- | ------ | ----- | ------------ |
| Dish lookup   | 0.05s  | 0.06s | 0.6%         |
| Embedding     | 0.18s  | 0.43s | 4.6%         |
| Vector search | 0.06s  | 0.08s | 0.8%         |
| Citations     | 0.08s  | 0.10s | 1.0%         |
| **Re-rank**   | 2.72s  | 8.87s | **93.9%**    |

**Its tail is upstream variance, not anything in this repo.** Identical prompts against the same lane measured p95
**1.64s** in one window and **8.87s** in another. Two things were tried and rejected on measurement: `max_tokens` made
it **worse** (p95 1.64s unbounded against 3.02s at 700), and a faster model was already chosen.

**So the tail is bounded rather than chased.** `RERANK_TIMEOUT` defaults to 4s, covering the retry rather than each
attempt, and past it the retrieval order ships — worse ranking, still cited, still fast. This is the fallback the
ranking section already described; the timeout now agrees with it instead of being 60s.

Bounding cost nothing measurable: **p@5 0.976 → 0.984, top1 51/51, p95 5.30s → 4.66s, max 7.16s → 4.74s.**

**Closing the last 1.66s meant a ~2.5s budget, which would have dropped re-ranking on a large share of requests.** For a
product whose promise is a trustworthy pick, shipping worse rankings to hit a latency number was the wrong trade — so
the note here said to revisit when a faster lane existed. That is exactly what happened, and the lesson generalises:
**when a stage is 93.9% of p95, the lane is the budget and tuning around it is wasted effort.**

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
  { query, lat, lng, radius_m, prefs?, budget?, cuisine?, limit? }
→ { results: [ { venue: {id, name, area, lat, lng, maps_url, dishes},
                 rank, why, match: {basis, dish, similarity},
                 distance_m,
                 citations: [ {post_url, excerpt, platform, author_handle, posted_at} ] } ],
    degraded: bool, degraded_reasons: [string], sources_used: [string] }

POST /ask
  { venue_id, question }
→ { covered: bool, answer, venue,
    citations: [ {post_url, excerpt, platform, author_handle, posted_at} ] }

GET  /venue/{id}?lat&lng
→ one entry, same shape as a /recommend result. rank/why/match are null: nothing was ranked.
  404 when the venue has no citations -- an entry that cannot be cited is not a result.

GET  /health → { ok, corpus_size, oldest_capture, newest_capture }

POST /auth/signup { email, password }  → { token, user }        409 if taken
POST /auth/login  { email, password }  → { token, user }        401, one message for both failures
POST /auth/guest  {}                   → { token, user }        user.is_guest, user.shared
POST /auth/logout                      → { ok }
GET  /auth/me                          → { user, prefs }        401 without a live token
PUT  /auth/prefs  { prefs }            → { prefs }

POST /companion { step, picked[] }     → { text, source: 'model'|'script', reason? }
GET  /suggestions                      → { chips: [{label, query, posts, venues}], band, source }
```

**Auth never gates `/recommend`.** The product promises a decision in under two minutes, and a login wall in front of
search breaks that. Auth persists preferences; it does not guard the corpus. There is a test asserting search answers
with no `Authorization` header and with a junk one.

| Concern             | How                                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Passwords**       | `hashlib.scrypt`, N=2^15 r=8 p=1, per-row salt. Parameters live **inside** each hash so they can be raised                               |
| **Tokens**          | 32 random bytes, opaque, returned once. Only a SHA-256 fingerprint is stored, so a dump yields no sessions                               |
| **Account probing** | An unknown address and a wrong password return the **same** 401, and the unknown path still runs a hash so timing does not separate them |
| **Rate limits**     | Per IP, in process: login 10/5min, guest 20/5min, signup 5/hour, companion 12/min                                                        |
| **Guest expiry**    | 12 hours, against 30 days for a real account — the guest credential is effectively public                                                |

**`scrypt` rather than argon2id or bcrypt**: both need a C extension in the API image, and the standard library's scrypt
is memory-hard and sufficient. `maxmem` must be passed explicitly — OpenSSL caps it at 32 MB by default, which these
parameters sit exactly on, and every hash raises `memory limit exceeded` without it.

**The rate limiter is in-process and not durable.** It stops credential stuffing from one host, not a distributed
attack. That is a deliberate trade: one API process today, and a limiter that needs Redis to exist is a limiter nobody
turns on.

`prefs` is the `/taste` wizard's output and is **optional on every call** — a bare `query` must keep working, because
auth never gates `/recommend`:

```
prefs: { craving: [string], company: 'solo'|'couple'|'family'|'group',
         range_m: int, mood: 'adventurous'|'comfort', budget: 'cheap'|'mid'|'splurge' }
```

**The `match` block is what a client types against, so it is tested rather than described.** It carried
`dish_hit, lexical, vector` here until 2026-08-29 while the API sent `basis, dish, similarity`; the web client's type
was written faithfully against this block and was wrong for as long as nothing read those fields. `tsc` found it the
moment a real response met the type. `tests/test_api_contract.py` now asserts this line against the response shape.

**`results` may be shorter than `limit`, including empty.** Returning a venue that does not match, with prose conceding
it does not match, is worse than returning nothing — see [`Ranking`](#ranking).

`rank` is the position the re-rank assigned. It replaces the old `score`, which reported retrieval cosine while ordering
came from the re-rank, so a higher number could appear below a lower one. `match.basis` is one of `dish` (an alias hit
on `mention.dishes`), `text` (lexical hit in an excerpt) or `semantic` (vector only), so the UI can say _why_ an entry
is present rather than asserting a number.

### The Copilot Never Introduces A Fact

`/ask` answers one question about one venue **from that venue's stored excerpts, or not at all**. It routes, quotes and
admits gaps.

**`covered: false` is a correct answer, not a failure.** Saying the posts do not cover something is the honesty the
citation trail exists to support, and it is the thing a maps product cannot do because it has no evidence trail to be
honest about.

Three enforcements, none of which trust the model:

| Enforcement                                              | Why                                                                                    |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| A `covered` answer with no excerpt is downgraded         | The model does not get to assert grounding it did not use                              |
| Excerpt indices outside the supplied range are dropped   | An invented index is a hallucinated citation by another name                           |
| Citations are built from database rows                   | A model asked for a URL produces a plausible one. It is never parsed out of the answer |
| `covered: false` **always** carries an empty `citations` | So a client renders the two states from one field, rather than inspecting both         |

Like `/recommend`, `/ask` is **not gated by auth**. Its lane is configured separately from the re-rank
(`COPILOT_MODEL`): re-rank is tuned for "pick 10 and write 12 words", while getting a citation wrong is worse than
getting an ordering wrong.

**The guest account is shared.** `/auth/guest` returns a session on a single row that every caller shares, so `user`
carries `is_guest` and `shared: true`, and the client must surface that. **The disclosure is now in-session rather than
pre-click**: the auth screens carry the button alone, and the nav renders `Guest, Shared` for as long as the session
lasts. That is the owner's call, taken on 2026-08-29, and it is a real narrowing — somebody can now sign in as guest
without having been told the account is shared. It is disclosed continuously afterwards instead, which is where a person
is actually at risk of forgetting. `web/src/__tests__/auth.test.tsx` asserts both halves.

**`/companion` is the one lane deliberately kept away from the citation trail.** It writes a single cheerful sentence
for a wizard step. It is safe to generate precisely because it is useless as evidence: it sees no corpus row, names no
venue, returns no `citations` key and cannot, and `makanlah/companion.py` drops any line that names a place, recommends,
rates, quotes a price or carries a URL. When a line is dropped, or the key is unset, or the free quota is spent, a
scripted line is returned with 200 and `source: 'script'` — a wizard whose companion goes silent reads as broken, a
slightly repetitive one does not. **The scripted lines are duplicated in `web/src/companion/lines.ts`** so the client
speaks before the server answers; `web/src/__tests__/companion.test.ts` reads the Python file and fails if the two
diverge.

Its quota is counted in **requests, not ringgit**, because it runs on a free tier rather than a paid one. Counting it in
MYR would report a bill that does not exist and, worse, would let the paid budget's headroom authorise a call the free
tier has already refused. `COMPANION_DAILY` and `COMPANION_PER_MIN` sit under the tier's 500/day and 15/min: crossing a
free tier starts charging rather than failing.

**`/suggestions` lets a model choose but never write.** It is handed a numbered list of dishes read out of `mention`
(`db.popular_dishes`) and returns **indices**; the label that renders is the database string at that index. A model that
invents a dish produces an out-of-range index, which is dropped — so a chip can never lead to an empty result page,
which is the promise a chip makes. Every chip carries its post count for the same reason the citations exist: the number
is why it is being offered.

It is stricter than `/companion` on purpose. A bad companion line is merely odd; a bad chip is a dead end with the
product's name on it. It shares the companion's **free-tier request counter** rather than the ringgit budget — see the
note above on why metering a free lane in MYR would let paid headroom authorise a call the free tier has refused. Out of
quota returns the corpus order; an unreachable corpus returns `chips: []` rather than six invented ones.

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

| Stage             | Notes                                                                                                                                                         |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fetch**         | CDP against the signed-in Chrome for RedNote and for Google Maps. Firecrawl stays for open-web fallbacks                                                      |
| **Store raw**     | Before extraction, always. A schema change must never require re-scraping                                                                                     |
| **Extract**       | One prompt handling all three languages. Never a per-language path                                                                                            |
| **Resolve venue** | Match on `name_normalized` and proximity. Ambiguity creates a new venue — merging is safe later, a wrong merge is not                                         |
| **Geocode**       | **Google Maps over CDP**, which needs no key. Nominatim is the fallback, one request per second with a contact address in the User-Agent per its usage policy |
| **Merge**         | Venues sharing a Google `place_id` are merged. Nothing else is accepted as evidence                                                                           |

### Two Sources, Neither Load-Bearing

| Source          | Carries                                           | Auth                                 |
| --------------- | ------------------------------------------------- | ------------------------------------ |
| **RedNote**     | Long-form posts, often naming many venues at once | A signed-in Chrome profile, over CDP |
| **Google Maps** | Per-venue reviews, coordinates, `place_id`        | **None.** No API key, no billing     |

This is [`PRODUCT.md`](PRODUCT.md#data-sources)'s design rule made real, and it is about uptime rather than legal cover.
**Prefer a fallback that needs no session**: a second login-walled source doubles the surface that can expire unattended
without doubling the resilience.

**Maps review sentiment comes from the star rating, not from a model.** The rating is the writer's judgement stated
numerically, so inferring it from prose would be less accurate and cost a call per review. A review with no readable
rating stores `null`, never `0` — null means unknown, zero means the writer was ambivalent, and collapsing the two makes
missing data look like a judgement.

### Merging Venues

`venue` deliberately creates a new row on ambiguity, because merging later is safe and a wrong merge is not. **A shared
Google `place_id` is the only accepted evidence** for the merge — it is not a guess, it is Google stating two names
resolve to one establishment.

**Name similarity is explicitly not evidence.** `Village Park` and `Village Park Nasi Lemak` look mergeable and may be
two businesses at one address. Those are collapsed by the ranking layer for a single response, which is reversible,
rather than in the corpus, which is not.

The merge order matters and is pinned by tests: conflicting mentions are deleted before re-pointing, or the
`(post_id, venue_id)` unique key aborts the merge; the venue row is dropped last, or its mentions cascade away before
they can be moved; and embeddings are dropped on both sides, because the survivor's document changed and a stale vector
would rank it on pre-merge text.

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

| Row                    | State                                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Embedding model**    | **Closed.** `text-embedding-v3`, 1024-dim. en 8/8 · ms 7/8 · zh 8/8, with the sample-size caveat recorded    |
| **Corpus volume**      | **Closed for now.** 50 posts → 137 venues, 150 mentions. Far too small to need partitioning                  |
| **Fallback sources**   | **Open.** Google Maps reviews work over CDP with no key and carry coordinates. Reddit serves a bot challenge |
| **Ingestion schedule** | **Open.** 50 posts took ~35 min wall-clock, dominated by page settle time, not by the models                 |

---

## What The Spike Changed

**50 posts, captured 2026-08-27.** A redacted 14-post fixture set is in [`source/`](source/). The full result:

| Field         | Coverage | Note                                                        |
| ------------- | -------- | ----------------------------------------------------------- |
| **Name**      | 137/137  | Every venue row is named. Chinese and Latin scripts both    |
| **Sentiment** | 150/150  | 100%. The extractor always forms a judgement                |
| **Excerpt**   | 150/150  | 147 verbatim, **3 repaired**, 0 dropped                     |
| **Dish**      | 93/150   | 62%. A listicle often gives a verdict without naming a dish |
| **Location**  | 45/137   | **33%. The weak stage** — see Geocoding below               |

Extraction: **50/50 posts, 0 failures.** 16 posts named no venue at all; those are video-first posts whose description
carries no restaurant name, and returning zero is the correct answer for them.

Languages, per post: **36 Chinese only · 6 Chinese+Malay · 5 Chinese+English · 3 all three.** The corpus is
overwhelmingly Chinese, which makes the multilingual embedding decision load-bearing rather than theoretical — a
retrieval stack weak on Chinese would fail on 100% of this corpus, and one weak on Malay fails on 18% of it silently.

### The Six Changes

| Change                                                | Because                                                                                                                                                                                               |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `platform` is **`rednote`**, not `xhs`                | `rednote.com` and `xiaohongshu.com` serve the same content behind **separate sessions**. On the spike machine the first was signed in and the second was not. The host is the identity, not the brand |
| Added **`posted_at_raw`**                             | RedNote renders `Feb 17` and `3 days ago` — no year. Parsing is lossy and re-parsing from a stored string is free                                                                                     |
| Added **`mention.excerpt_origin`**                    | The excerpt may be the model's, repaired, or absent. Without this, a bad extractor run is not revocable by origin                                                                                     |
| Added the **excerpt substring invariant**             | Measured: the extractor returned excerpts that were not in the post                                                                                                                                   |
| **`venue_embedding` is keyed on `(venue_id, model)`** | Embeddings from two models never compare. One column keyed only by venue silently mixes incomparable vectors                                                                                          |
| **DashScope replaces ModelScope**                     | No ModelScope key exists; the owner has an International/Singapore DashScope key. Nearer KL, and OpenAI-compatible so only the base URL changed                                                       |

### Source Health

`ingest_run` records one row per platform per attempt and `source_status` is the last outcome per platform. Without it
`degraded` can only be hardcoded `false`, **which is worse than omitting the field** — the UI then promises an honesty
it cannot deliver.

A run that dies mid-batch leaves `ok` null and reads as "did not finish", never as a pass. This is the same rule
[`AUTONOMY.md`](AUTONOMY.md#verification-replaces-the-human) states about CI: an absent verifier must not look like
success.

`source_health()` never raises. A health check that failed closed would mark every request degraded, which is the same
lie in the other direction.

`media_urls` stays in the schema but is **empty in practice**: RedNote image URLs carry per-request signatures that
expire, so storing them would persist a credential and a dead link. `raw_payload` keeps the image count instead.

### Geocoding Is The Weak Stage

[`CREDENTIALS.md`](CREDENTIALS.md#geocoding-and-what-it-does-not-need) said to move to Google Places only if Nominatim's
match rate on mixed-language Malaysian restaurant names proved poor, and **to measure it rather than assume it**.
Measured: **33%.**

The misses are overwhelmingly Chinese-only venue names, which OpenStreetMap does not carry for KL. A Klang Valley
bounding box rejects out-of-region matches, because Nominatim will otherwise resolve a bare Chinese restaurant name to
somewhere in China — **a wrong coordinate is worse than a null one**, since a null venue is merely unrankable by
distance while a wrong one is confidently misplaced.

Two options, neither taken yet because both cost something:

- **Google Places** — needs a Cloud project with billing enabled even inside the free tier, so it is a hard stop under
  [`AUTONOMY.md`](AUTONOMY.md#what-still-stops-you) #1 until someone funds it
- **Google Maps place search over CDP** — no key at all, and the place URL embeds coordinates as `!3d<lat>!4d<lng>`.
  Proven working during the spike. It is a scrape rather than an API, so it belongs behind the same rate limiting and
  caching as any other source

**Venues with null coordinates are excluded from distance-filtered queries, not deleted.** At a 33% match rate that
exclusion is most of the corpus, so the default search is KL-wide and distance is opt-in.

Everything else in [`PRODUCT.md`](PRODUCT.md#open-decisions) is closed, with the reasoning in
[`AUTONOMY.md`](AUTONOMY.md#pre-authorized-defaults).
