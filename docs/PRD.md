# PRD — Product Requirements

**What MakanLah must do, and how anyone can tell whether it does it.** Cites [`PRODUCT.md`](PRODUCT.md) for who and why,
and [`TRD.md`](TRD.md) for how. Where this file and `TRD.md` disagree on anything technical, `TRD.md` wins.

> **Status: written during the day-0 spike**, against the first real records rather than ahead of them. Counts quoted
> here come from [`PROGRESS.md`](PROGRESS.md) and the spike capture in [`source/`](source/), not from estimates.

---

## The One Sentence

> A hungry person in Kuala Lumpur states a preference and gets a ranked shortlist in under two minutes, where **every
> entry shows the post it came from**.

Everything below either serves that sentence or is out of scope.

---

## User Stories

Ordered by what breaks the product if missing. **S1 through S4 are the MVP**; S5 and S6 ship only if the MVP lands.

| ID     | As a…                    | I want…                                                      | So that…                                                     |
| ------ | ------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **S1** | hungry person in KL      | to say what I feel like eating in my own words               | I do not have to translate a craving into filter checkboxes  |
| **S2** | person deciding fast     | a ranked shortlist of nearby places                          | I can choose without opening five apps                       |
| **S3** | sceptic                  | to see the actual post behind each pick, in its own language | I can judge the recommendation instead of trusting a blurb   |
| **S4** | person about to leave    | a directions handoff                                         | the decision ends in going somewhere                         |
| **S5** | person on a budget       | to bound the price                                           | the shortlist is affordable                                  |
| **S6** | non-Chinese-reading user | a gloss beside a Chinese excerpt                             | the evidence is legible without replacing the writer's words |

**S3 is the product.** If a shortlist renders without its evidence, the release is not shippable — degraded, empty and
error states included.

---

## Functional Requirements

### FR1 — Preference Input

Free text, plus optional distance, budget and cuisine bounds. Location comes from the browser, or from a typed area name
when permission is refused. **Refusing location must never dead-end the app** — it falls back to a KL-wide search.

### FR2 — Ranked Shortlist

Up to ten venues, ordered by fit against the stated preference. Each entry carries the venue name as written, the area,
a one-line reason, distance when coordinates exist, and **at least one citation**.

### FR3 — Citations Are Load-Bearing

Every entry joins to at least one real `source_post` through `mention` ([`TRD.md`](TRD.md#the-one-invariant)).

- A candidate that cannot be cited is **dropped before the response is built**, never shown with a caveat
- The excerpt shown is **a verbatim span of the post**, in the language the writer used. Never a translation, never a
  paraphrase, never a model-composed summary
- The link resolves to the live post so a user can verify it

> **The spike found this is not free.** Asked for the span an extraction came from, the model returned text that read
> correctly and was **not** in the post — it stitched non-contiguous lines together. A fabricated quote behind a
> citation is worse than no citation, so an excerpt is stored only if it is a substring of `raw_text`; otherwise it is
> repaired from the post or dropped. See [FR7](#fr7--extraction-quality).

### FR4 — Directions Handoff

A Google Maps deep link built server-side, sharpened by `place_id` where one exists. No maps SDK, no key, no billing.

### FR5 — The Corpus Is Read, Never The Platform

The request path touches only the local corpus. **No user request ever triggers a fetch to a social platform.**
Ingestion runs on a schedule, writes the corpus, and is invisible to the request path.

### FR6 — Honest Degradation

When a source was unreachable at last ingestion, the response sets `degraded: true` and the UI says so plainly. The app
keeps working — that is the point of no single source being load-bearing.

### FR7 — Extraction Quality

One extraction path handles English, Malay and Chinese. **A per-language path is a defect**, not an optimisation: it
biases the corpus toward whichever language the pipeline handles best and looks like it is working.

Extraction of a post yields, per venue named: the name as written, aliases across scripts, dishes as named, sentiment,
an optional price band, and a verbatim excerpt. **A post naming nine restaurants yields nine mentions** — the spike's
first real capture was exactly that, and a pipeline that collapses it to one loses most of the corpus.

### FR8 — Venue Resolution

Venues match on a normalized name plus proximity. **Ambiguity creates a new venue.** Merging two rows later is safe; a
wrong merge silently attributes one restaurant's praise to another and is not recoverable from the corpus alone.

---

## Acceptance Criteria

Each is checkable by a test, which is what makes it a worker task under [`SWARM.md`](SWARM.md#4-worker-contract) §4.

| ID     | Criterion                                                                              | How It Is Checked                        |
| ------ | -------------------------------------------------------------------------------------- | ---------------------------------------- |
| **A1** | No response contains a result with zero citations                                      | API contract test over a seeded corpus   |
| **A2** | Every stored `excerpt` is a substring of its post's `raw_text`                         | SQL over the corpus. Zero rows expected  |
| **A3** | Every `mention` joins to a `source_post` and a `venue`                                 | SQL. Zero orphans expected               |
| **A4** | A venue named in Chinese and in Latin script in one post resolves to **one** venue row | Unit test on venue resolution            |
| **A5** | The same venue is retrieved for the equivalent query in each of EN, MS and ZH          | Retrieval test on a held-out set         |
| **A6** | The app returns a shortlist with the primary source unreachable                        | E2E with the scraper stubbed out         |
| **A7** | A result set renders correctly with mixed EN/MS/ZH text at 360 px width                | Vitest render + a phone-width screenshot |
| **A8** | Geocoding runs at ingestion; no request-path call reaches a geocoder                   | Assert no outbound call in the API test  |
| **A9** | Re-running ingestion over the same posts creates no duplicate rows                     | Idempotency test on `(platform, id)`     |

**A5 is the one that fails silently.** A model strong in English and weak in Malay scores well on every other criterion
here. It is a pass/fail on all three languages, not an average.

---

## Non-Functional Requirements

| Area              | Requirement                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------ |
| **Latency**       | Shortlist in under 3 s at p95. The promise is a decision in two minutes, and the app is one step |
| **Availability**  | The app serves from the corpus while every scraper is failing                                    |
| **Collection**    | Modest, cached, attributed, easy to switch off. Rate limits respected; evasion is not a strategy |
| **Privacy**       | No accounts, no PII, no scraped content in the repo. Media referenced, never rehosted            |
| **Cost**          | Free tiers only. No request-path model call beyond the single re-rank                            |
| **Accessibility** | Mixed-script text must remain legible; test with all three languages, never lorem ipsum          |

---

## Out Of Scope

From [`PRODUCT.md`](PRODUCT.md#scope), restated so nobody builds toward them: accounts, user reviews, bookings, social
features, cities other than KL, real-time availability and table stock.

Two consequences that make the MVP cheap and are worth stating: **no accounts means no auth, no sessions and no PII**,
and **no real-time availability means the corpus may be stale**, so ingestion can fail for a day without the app
noticing.

---

## Open Rows

Carried from [`TRD.md`](TRD.md#open-rows) rather than duplicated. The ones that change requirements rather than
implementation:

| Row                 | Blocks                            | Resolved By                                                          |
| ------------------- | --------------------------------- | -------------------------------------------------------------------- |
| **Embedding model** | A5, and therefore FR2             | The three-language retrieval test                                    |
| **Fallback source** | FR6, and the no-load-bearing rule | Which platforms carry KL signal without needing a session            |
| **Gloss for S6**    | S6 only                           | Whether a translation can sit beside an excerpt without replacing it |
