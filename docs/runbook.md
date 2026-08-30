# MakanLah Runbook — Run It Yourself

Everything needed to take this repository from a clone to a working app with a real corpus behind it. Written for
somebody who has never seen it before.

**The app runs without a corpus.** It will return nothing and say so, which is the honest failure and a useful thing to
see before you spend anything on ingestion.

## Contents

1. [What You Are Running](#1-what-you-are-running)
2. [Prerequisites](#2-prerequisites)
3. [Clone And Install](#3-clone-and-install)
4. [The Database](#4-the-database)
5. [Keys And Environment](#5-keys-and-environment)
6. [Running It Locally](#6-running-it-locally)
7. [Filling The Corpus](#7-filling-the-corpus)
8. [Checks](#8-checks)
9. [Deploying](#9-deploying)
10. [Operating It](#10-operating-it)
11. [Troubleshooting](#11-troubleshooting)
12. [What Is Confirmed, And What Is Not](#12-what-is-confirmed-and-what-is-not)

---

## 1. What You Are Running

Three processes that share a library and nothing else.

|           | Where                | Needs                                          |
| --------- | -------------------- | ---------------------------------------------- |
| `api/`    | Anywhere Python runs | The database, an embedding key, a re-rank key  |
| `web/`    | Any static host      | Only the API's URL                             |
| `ingest/` | Your own machine     | The database, a signed-in Chrome, a Places key |

**Ingestion never serves a request and the API never scrapes.** If you only want to see the app work, you need the first
two and a corpus somebody else filled.

---

## 2. Prerequisites

| Tool       | Why                             | Check                     |
| ---------- | ------------------------------- | ------------------------- |
| **Bun**    | JS packages, scripts, git hooks | `bun --version`           |
| **uv**     | Python dependencies and running | `uv --version`            |
| **Python** | 3.11 or newer                   | `python3 --version`       |
| **Chrome** | Only for RedNote capture        | `google-chrome --version` |

A Neon account (free tier is enough) and, for ingestion, a Google Cloud project with billing enabled — the Places free
tier still requires one.

---

## 3. Clone And Install

```bash
git clone https://github.com/TolongLabs/MakanLah.git
cd MakanLah

bun install     # dev tooling, and wires the husky hooks
uv sync         # Python dependencies from pyproject.toml
```

`bun install` installs commit hooks that lint staged files and enforce Conventional Commits. If you are only reading,
that is harmless.

---

## 4. The Database

Neon, Postgres with pgvector. Pick a region near your users; every request path crosses it.

You need **two** connection strings from the Neon console and they are not interchangeable:

- `DATABASE_URL` — the **pooled** one, for the API
- `DATABASE_URL_UNPOOLED` — the **direct** one, for migrations and long ingestion batches

pgbouncer in transaction mode does not support the session-level statements migrations issue, so a migration against the
pooled URL fails in a way that reads like a permissions problem.

```bash
uv run python -m makanlah.migrate
```

This is idempotent. It creates the extensions (`uuid-ossp`, `vector`, `pg_trgm`), the corpus tables and the indexes.

---

## 5. Keys And Environment

```bash
cp .env.example .env
```

`.env.example` documents every name with the reason it exists. Nothing in it is a secret and nothing ever should be.

**The minimum to serve an existing corpus:**

| Variable            | For                                     |
| ------------------- | --------------------------------------- |
| `DATABASE_URL`      | Reading the corpus                      |
| `DASHSCOPE_API_KEY` | Embedding a query, and the re-rank pass |
| `VITE_API_BASE_URL` | The client, pointing at your API        |

**Additionally, to ingest:**

| Variable                | For                                                  |
| ----------------------- | ---------------------------------------------------- |
| `DATABASE_URL_UNPOOLED` | Writing in long batches                              |
| `GOOGLE_PLACES_API_KEY` | Venue discovery, reviews and price. Server-side only |
| `XHS_CHROME_PROFILE`    | The signed-in Chrome profile for RedNote             |
| `NOMINATIM_USER_AGENT`  | Their usage policy requires a real contact address   |

**Two Google keys, never one.** The Places key is unrestricted by referrer and must stay server-side. The Static Maps
key (`VITE_STATIC_MAPS_KEY`) is restricted by HTTP referrer and ships in the browser bundle on purpose. Reusing the
first for the second publishes an unrestricted key.

With no model key the app still starts. The copilot reports itself unavailable and ranking falls back to the filtered
set — worse ordering, still cited.

---

## 6. Running It Locally

Two terminals.

```bash
scripts/dev-api.sh              # uvicorn on 127.0.0.1:8000
cd web && bun run dev           # Vite on 127.0.0.1:5173
```

Confirm the API is actually talking to your database rather than guessing:

```bash
curl -s localhost:8000/health | python3 -m json.tool
```

`corpus_size` and `venues` come from the database. If they are zero, the app is healthy and the corpus is empty, which
is section 7.

---

## 7. Filling The Corpus

Four stages. Each is separately runnable and each is safe to re-run — capture writes to a raw cache, and everything
downstream reads that cache rather than the network.

### 7.1 Discover Venues From Google Maps

```bash
uv run python ingest/discover_gmaps.py --limit 40
```

Searches an area × dish grid and creates venues from the results. **A discovered venue carries coordinates and no
evidence, and cannot be recommended** — both retrieval paths inner-join `mention`. It becomes recommendable in 7.3.

Idempotent: re-running the same query finds the same places and creates none of them twice.

### 7.2 Capture RedNote Posts

Needs a Chrome signed in to RedNote. The host is the identity, not the brand — `rednote.com` and `xiaohongshu.com` serve
the same content and sign in separately.

```bash
scripts/chrome-session.sh start       # CDP-controllable Chrome carrying your session
uv run python ingest/capture_rednote.py --limit 50
scripts/chrome-session.sh stop        # removes the copied session, which is a live credential
```

### 7.3 Extract, Enrich, Embed

```bash
uv run python ingest/pipeline.py                    # raw -> extract -> venue -> geocode -> embed
uv run python ingest/enrich_places.py               # Maps reviews and price, ~1s a venue
uv run python ingest/backfill_review_dishes.py      # tag reviews with the dishes they name
uv run python ingest/backfill_prices.py             # read a price from post text where one is stated
```

`enrich_places.py` is the one that makes discovered venues recommendable. It costs one Place Details call each
(Enterprise SKU, 1,000 free a month), and `--dry-run` reports the call count before spending it.

### 7.4 Embed Anything New

```bash
uv run python -c "from ingest.pipeline import embed_pending; print(embed_pending())"
```

**Do not skip this.** A venue with no embedding is invisible to retrieval even though it has evidence, and the symptom
is a dish query returning one result while the database holds hundreds.

---

## 8. Checks

All three run in CI and all three should pass before a push.

```bash
bun run lint        # biome + prettier + ruff, check and format
bun run typecheck   # tsc --noEmit, from web/
uv run pytest -q    # the Python suite, entirely against fixtures
```

Ranking quality is measured rather than asserted:

```bash
uv run python -m evals.run --quick
```

`evals/` holds pinned ground truth. The full run costs real tokens and prints the bill before spending it.

---

## 9. Deploying

**The API is deliberately not git-connected.** Merging updates the client and leaves the function alone, so a deploy is
an explicit act:

```bash
scripts/deploy-api.sh
```

It refuses a dirty tree, passes the commit sha in as `GIT_COMMIT_SHA`, and then **asserts `/health` reports that sha**
rather than trusting the deploy to have said READY. A deploy that succeeds and serves the previous build is the failure
that endpoint exists to make visible.

The client builds on push and writes its own commit into `build.json`, so both halves can be checked from outside.

**A differing sha between them is not drift.** The question is whether the diff touches a deployed path — `api/**` and
`makanlah/**` for the function, `web/**` for the client.

---

## 10. Operating It

**Freshness is a background concern.** Re-run section 7 on whatever cadence suits you. Nothing refreshes on a user
request, by design: a platform going dark should make the corpus stale, never make the app fail.

**Let an ingest run finish.** `start_run` inserts a row with `ok = null` and `finish_run` sets it, so a killed run
leaves an open row forever and every response then reports `degraded: true` with "the last refresh did not finish". It
clears itself the next time a run completes cleanly.

**Watch the spend.** `makanlah/ledger.py` records model spend and refuses calls past a daily ceiling. `/health` reports
which capabilities are configured, by name and never by value.

---

## 11. Troubleshooting

| Symptom                                                     | Cause                                                                                                                                         |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Migration hangs or errors oddly                             | Using the pooled URL. Migrations need `DATABASE_URL_UNPOOLED`                                                                                 |
| A dish query returns 1 result, database has many            | Venues without embeddings. Run 7.4                                                                                                            |
| Every response says "the last refresh did not finish"       | A killed ingest run left `ok = null`. Let one finish                                                                                          |
| `/health` reports `commit: null`                            | Deployed without `GIT_COMMIT_SHA`. Use `scripts/deploy-api.sh`                                                                                |
| Places calls return 400 INVALID_ARGUMENT                    | A legacy `0x…:0x…` CID being sent as a place ID                                                                                               |
| Maps enrichment returns 0 reviews for everything            | CDP path only. An ambiguous name lands on the results feed                                                                                    |
| Static map tile 403s                                        | Referrer restriction. The key only works from its allowed origins                                                                             |
| `bun run lint` differs from CI                              | Ruff first-party inference. `known-first-party` in pyproject pins it                                                                          |
| API dies at import: `could not convert string to float: ''` | An empty `EMBED_TIMEOUT=` in `.env`. `_load` uses `setdefault`, so an empty value SETS it and the code default never applies. Delete the line |
| `/recommend` returns a bare `{"error": ...}`                | No database. `/health` degrades honestly; that route is thinner                                                                               |

---

## 12. What Is Confirmed, And What Is Not

**Confirmed, by running it:**

- The documented path from a clean clone to a serving app, followed literally by someone who had not written it. That
  check found the runbook broken at section 6 and this list overstated, which is why it now says who confirmed what
- Places enrichment at roughly one second a venue, review text untruncated
- Idempotent discovery — a repeated query creates nothing twice
- `scripts/deploy-api.sh` catching a deploy that serves the previous build

**Not confirmed:**

- Any region other than the Klang Valley. Areas, dish vocabulary and the coordinate bounds all assume it
- Ingestion on macOS or Windows. The Chrome session script is written for Linux
- Behaviour past the Places free tier, which nothing here has crossed
- Concurrent ingestion. Three parallel CDP shards killed Chrome; the Places path has not been pushed the same way
- The full ingestion pipeline end to end from empty. Each stage is confirmed; the whole sequence in one sitting on a
  fresh database is not
