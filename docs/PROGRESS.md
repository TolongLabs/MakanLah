# Progress — 2026-08-27 · spike passed, app runs end to end

**The spike passed and the app works.** A query in English, Malay or Chinese returns a ranked shortlist from a real
corpus on Neon, every entry citing a real post, answered in the language it was asked in.

**Web client is deployed:** <https://makanlah-b5h.pages.dev> · **API is not** (see Blocked).

---

## The Spike Result

**50 posts from RedNote.** `xiaohongshu.com` is logged out on this machine but **`rednote.com` carries a separate
session and is signed in** — same content, different host, which is why the adapter targets the host rather than the
brand.

| Field         | Coverage | Note                                                        |
| ------------- | -------- | ----------------------------------------------------------- |
| **Name**      | 137/137  | Chinese and Latin scripts both                              |
| **Sentiment** | 150/150  | 100%                                                        |
| **Excerpt**   | 150/150  | 147 verbatim, 3 repaired, 0 dropped                         |
| **Dish**      | 93/150   | 62%. A listicle often gives a verdict without naming a dish |
| **Location**  | 45/137   | 33% via Nominatim. **Now fixed** — see below                |

Extraction: **50/50 posts, 0 failures.** 16 posts named no venue; those are video-first posts whose description carries
no restaurant name, and zero is the right answer for them.

Languages per post: **36 Chinese only · 6 Chinese+Malay · 5 Chinese+English · 3 all three.**

---

## What Is Live

| Thing         | State                                                                                |
| ------------- | ------------------------------------------------------------------------------------ |
| **Corpus**    | Neon `MakanLah` (`ap-southeast-1`). 50 posts, 149 venues, 166+ mentions              |
| **Sources**   | **Two.** RedNote, plus Google Maps reviews. Neither is load-bearing                  |
| **Ingestion** | `ingest/pipeline.py` and `ingest/enrich_gmaps.py`. Both idempotent, both record runs |
| **API**       | `bash scripts/dev-api.sh` → `127.0.0.1:8000`. Local only                             |
| **Web**       | Deployed to Cloudflare Pages. Verified at 390px in light and dark                    |
| **Tests**     | **57 pytest + 16 vitest**, all against fixtures. Never touches a live platform       |

**Google Maps replaced Nominatim as the geocoder.** Nominatim resolved 34%; OpenStreetMap does not carry Chinese-only
restaurant names for KL. Maps needs no API key — its place URL embeds coordinates as `!3d<lat>!4d<lng>` — and resolved
**6/6 on the first batch**, including two Chinese-only names Nominatim missed. It also returns a `place_id`, which
sharpens the directions link for a chain.

---

## Seven Real Defects Found And Fixed

1. **`chrome-session.sh verify` gave a false pass** on a logged-out session. Now asserts note cards rendered
2. **The extractor invented excerpts** — stitched non-contiguous lines into quotes that read correctly and were not in
   the post. Guarded by `repair_excerpt` **and** a Postgres trigger
3. **CJK venue names never deduped.** `\b` never matches inside 适苑酒家, so one restaurant became two venues
4. **An English question was answered in Chinese**, because the model anchored on the excerpt language
5. **`degraded` was hardcoded `false`** — the UI promised honesty it could not deliver. Now backed by `ingest_run`
6. **Placeholder text failed WCAG AA** at 3.39:1. Both themes now clear 4.5:1 on every token pair
7. **The CDP client had no timeouts**, so one crashed tab froze a 50-note batch for 20 minutes with no error

---

## Blocked, Needing A Human

- **Nobody can merge. PRs #3 and #5 are green and waiting.** `scripts/unattended.sh on` reports success but does not
  work: **deny outranks allow** in Claude Code, so the `gh pr merge` deny in `.claude/settings.json` cannot be lifted by
  `settings.local.json`. Filed as **#4**. Not routed around — routing around a deny is the guard failing
- **Fly.io not deployed.** No free allowance and the card is unfunded. `fly.toml` and `Dockerfile` are written, so it is
  `flyctl deploy` once funded. Roughly USD 2-3/month, scale-to-zero when idle
- **The deployed page cannot reach the API** until then. `?api=<url>` repoints it without a rebuild, and the error state
  says so plainly rather than showing an empty list

---

## Next

- Re-run both ingestions so `ingest_run` records a pass and `degraded` clears. Currently true, and honestly so
- More corpus. 50 posts is the spike's number, not a target
- Venue dedup is presentation-level only; the corpus still holds duplicate rows for one restaurant

**Branches:** `feat/xhs-spike` (PR #3) → `feat/app-scaffold` (PR #5, stacked on it). Merge #3 first.
