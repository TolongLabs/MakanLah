# Progress — 2026-08-27 · spike passed, app running locally

**The spike passed. The premise holds.** `xiaohongshu.com` is logged out on this machine but **`rednote.com` carries a
separate session and is signed in** — same content, different host. Search returns ~46 real KL restaurant posts per
query.

**Numbers from the first full ingestion (21 posts):** 21/21 extracted, 0 failed · **103 mentions across 94 venues** ·
**103/103 excerpts verbatim** (0 repaired, 0 dropped) · geocoded **32/94 (34%)**. A second batch of 50 captured notes is
extracting now.

**The core loop works end to end** against Neon, in all three languages, every result citing a real post.

---

## What Is Live

| Thing         | State                                                                              |
| ------------- | ---------------------------------------------------------------------------------- |
| **Corpus**    | Neon `MakanLah` (`hidden-resonance-97962934`, `ap-southeast-1`), migration applied |
| **Ingestion** | `ingest/pipeline.py` — raw → extract → venue → geocode → embed. Idempotent         |
| **API**       | `api/main.py` on `127.0.0.1:8000`. `/health` and `/recommend` both verified        |
| **Web**       | `web/` Vite + React. `tsc` clean, builds to 62 kB gzipped. **Not yet deployed**    |
| **Tests**     | 43 passing, all against fixtures. Never touches a live platform                    |

**Restart the API:** `bash scripts/dev-api.sh` (or the uvicorn line in `docs/README.md`).

---

## Four Real Defects Found And Fixed

1. **`chrome-session.sh verify` gave a false pass** on a logged-out session — it grepped the title for "login" and XHS
   keeps the title 小红书 behind a login modal. Now asserts note cards rendered. Exits 1 correctly
2. **The extractor returned excerpts that were not in the post**, stitching non-contiguous lines into quotes that read
   correctly. Guarded by `repair_excerpt` **and** a Postgres trigger — a fabricated quote now raises
3. **CJK venue names never deduped.** `\b` sits between a word and a non-word character and every CJK glyph is a word
   character, so `\b(酒家)\b` never matched inside 适苑酒家 — one restaurant became two venues
4. **An English question was answered in Chinese**, because the model anchored on the excerpt language. The answer
   language is now detected in code and pinned in the prompt

---

## Blocked, Needing A Human

- **Nobody can merge.** `scripts/unattended.sh on` reports success but does not work: **deny outranks allow** in Claude
  Code, so `.claude/settings.json`'s `gh pr merge` deny cannot be lifted by `settings.local.json`. Filed as **#4**.
  **PRs #3 and #5 are green and waiting.** Not routed around — routing around a deny is the guard failing
- **Fly.io is off.** No free allowance and the owner's card is unfunded, so the API stays local. `fly.toml` will be
  ready for a one-command deploy
- **Cloudflare Pages is authenticated** and the web client deploys there — free, no card

---

## Open, Worth Deciding Later

- **Geocoding is the weak stage: 34%.** `TRD.md` said to measure Nominatim before reaching for Google Places. Measured.
  Chinese-only venue names are the bulk of the misses
- **8 of 21 posts yielded 0 venues** — likely video-first posts whose description carries no venue name
- Embedding row **closed by measurement**: `text-embedding-v3`, en 8/8 · ms 7/8 · zh 8/8, sample-size caveat recorded in
  `docs/superpowers/research/`

**Branches:** `feat/xhs-spike` (PR #3) → `feat/app-scaffold` (PR #5, stacked). Both green.
