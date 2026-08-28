# Progress — 2026-08-28 · agents can merge; citations now lead with testimony

**`main` is at `5e48e98`.** Eight PRs merged today — #3, #5, #14, #17, #18, #23, #24, #27 — and no feature branches
remain. **228 Python tests, 74 web tests, lint and format clean, CI green.** Verified on `main` rather than on a branch:
`/recommend` with a radius returns cited results, `/venue/{id}` serves a deep link, `/ask` answers from the corpus and
admits a gap, `/auth/guest` reports `shared: true`.

**Agents merge on green CI now.** #23 replaced the blanket `gh pr merge` deny with `.claude/hooks/guard-merge.sh`, which
**fails closed**: it requires an explicit PR number, an OPEN state, every reported check passed, `mergeStateStatus`
CLEAN, and refuses `--admin`. Nine cases in `tests/test_merge_guard.sh`. **The first autonomous merge was #27.** The
hook takes effect only after a session restart — the harness caches permissions at start.

**Ranking is measured, not asserted.** `evals/` holds pinned ground truth and a runner. **p@5 0.982, wd@5 0.000, top1
49/51, p95 4.36s** — see the excerpt-ordering trade below, which cost 2 top1 and bought back 0.3s. **p95 is still
measured against a 3s target in [`PRD.md`](PRD.md)** and still not met, deliberately. Tracked as **#16**.

**A full eval run costs ~134k tokens**, 13% of a lane's free allowance, which does not refill before it expires on
**2026-10-13**. The runner prints the bill before spending it; use `--quick` while iterating.

**Every model lane is pinned to a dated free-quota snapshot.** The rolling DashScope aliases carry none. Re-check the
console before repinning.

**Web client is live:** <https://makanlah-b5h.pages.dev> · **API is local only** — see Blocked.

---

## Read This Before Merging Anything

**A merge silently reverted a commit today and CI stayed green**, because the commit's tests went out with its code. It
was caught only because the test count dropped 220 → 216. `git merge-base --is-ancestor` returned **true** for the
reverted commit, which is why it was durable — git considered it merged and would never re-apply it.

The checks that would have caught it, and the four instances of the same shape from one day, are rule 4 in
[`AUTONOMY.md`](AUTONOMY.md#a-check-that-owns-its-own-definition-of-success). **It is the most reusable thing this
session produced.**

---

## Six Things Found By Measuring, 2026-08-28

1. **The reported ranking bug was the model, not the architecture.** `bak kut teh` returning 首都茶室 and 何九茶室 was
   blamed on venue-level embeddings. Measured A/B: `qwen-turbo` scores **p@5 0.20 / wd@5 0.40** and reproduces the
   complaint exactly; `qwen3.8-flash` scores **1.00 / 0.00** and returns the one real bak kut teh shop. The swap made to
   escape a paid tier fixed relevance as a side effect. **Hybrid retrieval is no longer justified by this failure**
2. **Distance filtering had never worked.** Six parameters into a five-placeholder query, so every request carrying
   `radius_m` raised `ProgrammingError` — which `api/main.py` returned as `200 degraded: true`. The client blamed the
   corpus for a bug in the query builder for the life of the project. Fixed, and `degraded` now means only that the
   corpus is unreachable
3. **The first quality metric flattered the system.** Counting a venue wrong only when its dishes were the opposite
   cuisine scores the actual complaint **0.000**, because a kopitiam and a bak kut teh shop are both Malaysian
4. **A median was hiding the tail.** [`PRD.md`](PRD.md) sets a **p95** target and every report until now quoted a
   median. The baseline's median was a healthy 2.61s while its p95 was **11.19s**. The number that mattered was never
   being read
5. **Nothing asserted the response shape.** `score` reported retrieval cosine while the ORDER came from the re-rank, so
   a higher number could sit below a lower one — in every response, caught by no test. Now `rank` + `match.basis`
6. **Citations led with a postal address, 82 times out of 243.** Both citation queries ordered by `mention.confidence`,
   which measures how easy the text was to extract — close to the opposite of whether it is worth reading. The ≥0.95
   band averages **75 characters against 180** for the band below, and is nearly twice as likely to carry no opinion.
   Found by re-recording the demo: the hero frame cited an address against that venue's single most negative review.
   Fixed in #27; address-shaped leads **82 → 28**. It cost **top1 51/51 → 49/51**, all of it `matcha` — pin lines name
   the venue and its dish, so ranking had been leaning on text the reader should never have seen (**#26**)

**Start the API:** `scripts/dev-api.sh`. **Point the live page at it:** append `?api=<url>`.

---

## The Corpus

|                 |                                                                  |
| --------------- | ---------------------------------------------------------------- |
| **Posts**       | **1,507** — 1,388 Google Maps, 119 RedNote                       |
| **Venues**      | **243**, **241 geocoded (99%)**, 240 with a Google `place_id`    |
| **Mentions**    | **1,705** — all with sentiment and an excerpt, 486 with a dish   |
| **Excerpts**    | 1,695 verbatim from the model, 10 repaired, **0 fabricated**     |
| **Two sources** | **175 venues (72%) cited by both.** Neither is load-bearing      |
| **Invariants**  | 0 uncited venues · 0 non-verbatim excerpts · 0 dangling mentions |
| **Health**      | `degraded: false` — both sources recorded a passing run          |

**Geocoding went 34% → 99%** once Google Maps replaced Nominatim. Latency holds at **median 2.73s** against the 3s
target in [`PRD.md`](PRD.md).

## The Spike's Terminal Condition

The question the spike existed to answer, re-measured against the live corpus rather than quoted from memory:

> Can ~50 KL restaurant posts be pulled with **name, location, dish and sentiment** into records matching the
> `source_post` / `venue` / `mention` schema in [`TRD.md`](TRD.md)?

**119 RedNote posts captured. 87 of them yielded at least one mention, producing 317 mentions:**

| Field                       | Of 317 Mentions |
| --------------------------- | --------------- |
| **Venue name**              | **317 (100%)**  |
| **Location** (lat/lng)      | **315 (99%)**   |
| **Sentiment**               | **317 (100%)**  |
| **Dish**                    | **172 (54%)**   |
| **All four on one mention** | **171 (54%)**   |

**The schema held.** No TRD change was needed for RedNote: every captured post fit `source_post`, and every extracted
claim fit `venue` + `mention` as written. **Dish is the one weak field** — 46% of RedNote mentions give a verdict on a
restaurant without naming a dish, which is a property of how people write, not a extraction defect.

---

RedNote languages per post: **84 Chinese only · 14 Chinese+Malay · 13 Chinese+English · 8 all three.**

**Geocoding moved from Nominatim to Google Maps over CDP.** Nominatim managed 34%; OpenStreetMap does not carry
Chinese-only restaurant names for KL. Maps needs no API key — the place URL embeds coordinates as `!3d<lat>!4d<lng>` —
and also returns the `place_id` that makes venue merging evidence-based rather than a guess.

---

## Blocked, Needing A Human

- **API not deployed.** Fly has no free allowance and the card is unfunded. `fly.toml` and `Dockerfile` are written; it
  is one `flyctl deploy` at roughly USD 2-3/month. **#6**
- **1008 Google Maps posts are missing their text.** The scrape read reviews collapsed behind Google's own control. The
  marker is stripped from all 1331 affected excerpts and the scraper now expands before reading, but the lost text needs
  a re-capture over CDP. **#15**
- **p95 is 4.66s against a 3s target.** Bounded, not met, and the trade is deliberate. **#16**

---

## Eighteen Defects Found And Fixed

Each was found by running something, not by reading code.

1. `chrome-session.sh verify` **passed on a logged-out session** — it grepped the title for "login"
2. The extractor **invented excerpts**, stitching non-contiguous lines. Now a Postgres trigger, not a convention
3. **CJK venue names never deduped** — `\b` never matches inside 适苑酒家, so one restaurant became two venues
4. **An English question was answered in Chinese** — the model anchored on the excerpt language
5. **`degraded` was hardcoded `false`** — the UI promised an honesty it could not deliver
6. **Placeholder text at 3.39:1**, below WCAG AA
7. **The CDP client had no timeouts** — one crashed tab froze a 50-note batch for 20 minutes, silently
8. **Google Maps citations linked nowhere** — built from the venue's internal UUID
9. **The hosted page hung forever** on an unreachable API, with no request deadline
10. **Maps enrichment wrote only at the end** — a crash at venue 90 of 93 discarded the whole run
11. **A 3-way venue merge aborted** on the unique key: two dropped rows can hold a mention of the same post
12. **Latency was 12.5s against a 3s target.** The re-rank prompt was missing the literal word `json`, so DashScope
    returned 400 and re-ranking **silently never happened**; the lane was also a 235B model reading 48 candidates
13. **`他们家` was stored as a venue** — a pronoun meaning "their place", taken as a name by the extractor
14. **`华阳` / `华阳茶室` / `华阳冰室` were three rows for one kopitiam** — `茶餐室` and `冰室` were missing from the
    CJK generics
15. **A dry run reported 0 merges, then the real run merged 7** — it previewed against the stored key rather than the
    recomputed one, which is the shape of a dry run nobody should trust
16. **A run killed by `timeout` left its record open forever.** SIGTERM becomes `SystemExit`, which is not an
    `Exception`, so the handler never fired: the source read as permanently broken and `degraded` could never clear
17. **`chrome-session.sh verify` probed the wrong host.** It opened `xiaohongshu.com` while `ingest/rednote.py` reads
    `rednote.com` — separate sessions for the same content ([`CREDENTIALS.md`](CREDENTIALS.md)). The gate reported a
    login wall for a session that was live, which is exactly the false signal it was written to prevent
18. **`verify` could not assert anything and still exited.** Ambient `python3` has no `websockets`, so it printed a
    warning and skipped the content check. It now runs under `uv run --with websockets`; asserted **46 note cards, no
    login wall**

---

## Next

- **The pipeline is caught up.** Every venue that could be enriched has been; 2 of 243 remain ungeocoded
- Dish coverage is the weakest field at 486 of 1,705 mentions. Reviews name dishes; listicles often give a verdict
  without naming one
- Growing the corpus is now one command: `ingest/capture_rednote.py --target N`, then `ingest/pipeline.py`

**No open PRs, no feature branches.** Open issues: **#25** RedNote excerpts are pin lines · **#26** ranking leans on
address text · **#16** p95 · **#15** 1,008 posts missing text · **#6** deploy.

## The Demo Video

`scripts/demo/` records, narrates and muxes it — Playwright, Piper, ffmpeg, all local and free.
**`makanlah-demo-v2.mp4`, 55.4s, 1920×1080, 2.4 MB**, sitting beside the repo rather than in it (`.mp4` is gitignored).

Narration keys to beats `record.mjs` **measures** and writes to `beats.json`, not to hand-tuned offsets that drift the
moment a page gets slower. `record.mjs` also **asserts the corroboration pair is on screen** and prints the count, so a
run that re-records the #20 bug says so instead of looking fine.

**What it still cannot show:** `/ask` is API-only, so the strongest moment in the product — the copilot answering
`covered: false` — is unfilmable. And the RedNote column of the corroboration pair is still a pin line (**#25**), which
ordering cannot fix because the corpus holds nothing better for that venue.
