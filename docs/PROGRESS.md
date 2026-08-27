# Progress — 2026-08-27 · spike in flight

**Terminal condition:** ~50 KL restaurant posts pulled into `source_post` / `venue` / `mention` ([`TRD.md`](TRD.md))
with name, location, dish, sentiment. Report counts, not a verdict.

**Xiaohongshu is logged out — the primary source is unavailable.** Not a CDP fault: the plumbing works. `web_session`
copies and decrypts (len 38, HttpOnly, visible to CDP), but the server rejects it. Search returns `登录后查看搜索结果`
with 0 cards. **A human must re-login in Chrome, then fully quit Chrome** before `chrome-session.sh start`.

**Routed around:** Google Maps reviews via CDP — no key, real user text, mixed EN/MS/ZH, and lat/lng inline in the place
URL (`!3d<lat>!4d<lng>`), which may remove the geocode stage. Reddit serves a bot challenge; logged and skipped, not
evaded.

**Two bugs fixed in `scripts/chrome-session.sh`:**

1. `verify` used `GET /json/new`; Chrome 111+ answers with an error _string_, so the empty-body PUT fallback never
   fired. Now PUT only. **Fixed.**
2. `verify` returns a **false pass** on a logged-out XHS session — it greps the title for "login", and XHS keeps the
   title 小红书 while overlaying a login modal. The one check meant to prevent a silent login wall lets one through.
   **Being rewritten to assert content, not absent keywords.**

**Credentials.** `.env` created (mode 600). `DATABASE_URL` / `DATABASE_URL_UNPOOLED` filled from a new Neon project
`MakanLah` (`hidden-resonance-97962934`, `aws-ap-southeast-1`, free tier). `gh` is ADMIN. **Still empty and
human-gated:** `MODELSCOPE_API_KEY` (+ `MODELSCOPE_MODEL_EXTRACT`), `FIRECRAWL_API_KEY`, `OPENROUTER_API_KEY`,
`HERMES_API_KEY`. `flyctl` and `wrangler` are installed but unauthenticated — deploy-time only. Firecrawl CLI never
installed: only `~/.firecrawl/update-check.json` exists, the signature of an ephemeral `bunx` run.

**If ModelScope stays empty**, extraction for the spike runs on the orchestrator model and the boundary is marked
`TODO(blocked)`. `raw_payload` makes re-extraction free once a key lands.

**Branch:** `feat/xhs-spike`. **Gate:** `docs/PRD.md` still missing — write after the spike.

**Next:** build the Google Maps CDP scraper in `spike/`, pull ~50 KL venue reviews, map to the TRD schema, report
counts, write redacted captures to `docs/source/2026-08-27-*`.
