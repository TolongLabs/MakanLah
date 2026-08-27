# Progress — 2026-08-27 · the app works end to end

**A query in English, Malay or Chinese returns a ranked shortlist from a real corpus on Neon, every entry citing a real
post, answered in the language it was asked in.** Median response **2.51s**, inside the 3s target in [`PRD.md`](PRD.md).

**Web client is live:** <https://makanlah-b5h.pages.dev> · **API is local only** — see Blocked.

**Start the API:** `scripts/dev-api.sh`. **Point the live page at it:** append `?api=<url>`.

---

## The Corpus

|                 |                                                                    |
| --------------- | ------------------------------------------------------------------ |
| **Posts**       | **607** — 488 Google Maps, 119 RedNote                             |
| **Venues**      | **281**, 139 geocoded, 89 with a Google `place_id`                 |
| **Mentions**    | **822** — 822 with sentiment, 822 with an excerpt, 183 with a dish |
| **Excerpts**    | 812 verbatim from the model, 10 repaired, **0 fabricated**         |
| **Two sources** | 61 venues cited by both. Neither is load-bearing                   |
| **Invariants**  | 0 uncited venues · 0 non-verbatim excerpts · 281 embeddings        |

RedNote languages per post: **84 Chinese only · 14 Chinese+Malay · 13 Chinese+English · 8 all three.**

**Geocoding moved from Nominatim to Google Maps over CDP.** Nominatim managed 34%; OpenStreetMap does not carry
Chinese-only restaurant names for KL. Maps needs no API key — the place URL embeds coordinates as `!3d<lat>!4d<lng>` —
and also returns the `place_id` that makes venue merging evidence-based rather than a guess.

---

## Blocked, Needing A Human

- **Nobody can merge. PRs #3 and #5 are green and waiting.** `scripts/unattended.sh on` reports success but does not
  work: **deny outranks allow** in Claude Code, so the `gh pr merge` deny in `.claude/settings.json` cannot be lifted
  from `settings.local.json`. Filed as **#4**. Not routed around — routing around a deny is the guard failing
- **API not deployed.** Fly has no free allowance and the card is unfunded. `fly.toml` and `Dockerfile` are written; it
  is one `flyctl deploy` at roughly USD 2-3/month. Filed as **#6**

---

## Twelve Defects Found And Fixed

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

---

## Next

- Google Maps enrichment is running over the 116 venues that have only one source. Incremental, so partial results stick
- The corpus still holds duplicate venue rows where no shared `place_id` proves they are one place
- `degraded` reads `true` until a pipeline run records a pass for both platforms

**Branches:** `feat/xhs-spike` (PR #3) → `feat/app-scaffold` (PR #5, stacked). **Merge #3 first.**
