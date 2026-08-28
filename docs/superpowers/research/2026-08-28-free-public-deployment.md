# Deploying MakanLah Publicly, For Free

**Date:** 2026-08-28 · **Decides:** [#6](https://github.com/TolongLabs/MakanLah/issues/6), the unfunded Fly card ·
**Status:** recommendation, not yet executed

**Recommendation: put the API on Cloudflare Workers (Python) with Hyperdrive in front of Neon, and keep the client on
Cloudflare Pages where it already is.** Fall back to Render's Singapore free tier if Python Workers cannot reach Neon.

---

## What Actually Has To Be Hosted

| Piece      | Now                                      | Constraint                                                                   |
| ---------- | ---------------------------------------- | ---------------------------------------------------------------------------- |
| **Client** | Cloudflare Pages, free, live             | Static Vite build. Already solved, nothing to change                         |
| **API**    | **Local only** — this is the whole issue | FastAPI. Outbound to Neon (`ap-southeast-1`) and DashScope (Singapore)       |
| **Corpus** | Neon free tier                           | Stays. Not part of this decision                                             |
| **Ingest** | The workstation, and it must stay there  | It needs the signed-in browser. `AUTONOMY.md` forbids inbound to it entirely |

**Only the API needs a home.** Ingestion deliberately does not move: it needs the authenticated Chrome session, and the
workstation must never accept an inbound connection.

### The Requirements That Eliminate Most Options

1. **No card.** The Fly attempt died here ([#6](https://github.com/TolongLabs/MakanLah/issues/6))
2. **Singapore or edge.** KL users, a Singapore Neon and a Singapore DashScope. A US-only free tier adds ~200ms each way
   to a p95 that already misses its target ([#16](https://github.com/TolongLabs/MakanLah/issues/16))
3. **Tolerates a slow request.** A `/recommend` is one embedding call, one vector query and one re-rank — **p95 4.66s**,
   nearly all of it waiting on a model. Any platform with a short hard request timeout is out
4. **Outbound TCP to Postgres**, or a documented substitute

---

## The Options, Ranked

### 1. Cloudflare Workers, Python — Recommended

Cloudflare shipped a real Python runtime with **first-class FastAPI support**: the Workers runtime hands an ASGI server
to the Worker, and FastAPI runs unpatched.

|                |                                                                         |
| -------------- | ----------------------------------------------------------------------- |
| **Free tier**  | 100,000 requests/day, **10ms CPU per invocation**                       |
| **Region**     | 330 locations, 125 countries — KL is one, so there is no region to pick |
| **Cold start** | ~1s with snapshots, ~10s without                                        |
| **Card**       | None                                                                    |

**The 10ms CPU limit is not the blocker it looks like.** Workers bills **CPU** time, not wall-clock, and a `/recommend`
is almost entirely I/O wait on DashScope. The Python in `rank.py` — a haversine, a dedupe, some dict shuffling over ≤50
candidates — is well inside 10ms.

**The real question is Postgres.** Workers cannot open arbitrary TCP the way a normal process does, and the documented
answer is **Hyperdrive**, a pooler that keeps warm connections near the origin database. Hyperdrive itself is built on
Workers' TCP socket support and allows ~20 connections per config on the free plan, which is ample for one API.

**Verify before committing**, because the searchable documentation covers the JavaScript drivers well and Python less
so: does `psycopg` work over Hyperdrive from a **Python** Worker? If it does, this is the answer — same vendor as the
client, no cold-start penalty on a warmed edge, no card, and the lowest latency of anything here. If it does not,
option 2.

**Also check:** a 6-simultaneous-outbound-connection cap per invocation. We need two — Neon and DashScope — so this is
comfortable, but it constrains any future fan-out.

### 2. Render, Singapore — The Safe Fallback

|               |                                                         |
| ------------- | ------------------------------------------------------- |
| **Free tier** | Web service + Postgres, **no card**                     |
| **Region**    | **Singapore available** — the right one                 |
| **The catch** | **Spins down after 15 minutes idle; cold start 30-60s** |

**The cold start is the whole problem, and it is worse for this product than for most.** MakanLah's promise is a
decision in under two minutes. A first visitor after a quiet hour waits **30-60 seconds before the 4.66s query even
starts**. For a LinkedIn post — bursty traffic, mostly first-time visitors, many arriving after an idle gap — that is
close to the worst possible traffic shape.

**Mitigation, and be honest that it is a workaround:** an external cron pinging `/health` every 10 minutes keeps it
warm. This is widely done and widely tolerated. It is also, strictly, using the free tier against its intent — decide
that deliberately rather than drifting into it.

Spin-down was **30 minutes until recently and is now 15**, so the margin is narrowing.

### 3. Hugging Face Spaces, Docker — Viable, Odd Fit

Docker Spaces host FastAPI free; the container must listen on **port 7860**, and **only `/tmp` is writable**. Our API
writes nothing to disk, so the sandbox is not a constraint.

**The mismatch is presentational.** A Space is an ML demo surface. Sending LinkedIn traffic to a `huggingface.co/spaces`
URL reads as a research demo rather than a product. Fine as a backup, wrong as the front door.

### 4. Koyeb — Thin

One service, **512 MB RAM, 0.1 vCPU**. Explicitly "not for production" by the vendor's own description, and it **may
demand a card** if it cannot verify you are human. 0.1 vCPU against a FastAPI process that loads `psycopg` is tight.

### 5. Railway — Will Stop

**$5 the first month, then $1/month of credit**, and services **pause when it runs out**. A product on LinkedIn that
goes dark mid-month is worse than one that was never posted. Excellent DX, wrong billing shape for this.

### 6. Oracle Cloud Always Free — Most Resources, Most Friction

A real always-free ARM VM in Singapore, and **it was halved on 2026-06-15**: 4 OCPU/24 GB is now **2 OCPU/12 GB**.

Still by far the most compute here, and the only option that could host ingestion too. But: **a card is required at
signup**, Ampere capacity in a given home region is frequently unavailable, and idle instances can be reclaimed. It is a
VM, so it is also the only option that makes us responsible for TLS, a reverse proxy, and patching.

**Worth it only if the project later needs a machine.** For one FastAPI process it is a large amount of undifferentiated
work.

---

## Recommended Sequence

1. **Spike Cloudflare Python Workers + Hyperdrive → Neon.** Timebox it. The single question is whether `psycopg` works
   from a Python Worker over Hyperdrive
2. **If yes, ship it there.** Client and API on one vendor, no cold start, no card, lowest latency
3. **If no, Render Singapore** with a 10-minute keep-warm ping, and say plainly in `TRD.md` that the ping exists and why
4. **Do not move ingestion.** It stays on the workstation with no inbound. `AUTONOMY.md` is unambiguous

**Whichever wins, set `CORS_ORIGINS` to the Pages domain rather than `*`** — it currently defaults to `*`, which was
right for a local API and is not right for a public one.

---

## What This Does Not Solve

**Cold start and p95 are different problems and both are real.** Even with zero cold start, `/recommend` is 4.66s at p95
([#16](https://github.com/TolongLabs/MakanLah/issues/16)). Deploying does not improve that, and a first-time visitor
from LinkedIn experiences the sum of both.

**The free Neon tier also sleeps.** Not researched here; check before launch, because a sleeping database in front of a
warm API produces exactly the same first-visit stall.

---

## Sources

- [Platforms with a real free tier for developers in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [The 2026 Developer's Guide to Zero-Cost Full-Stack Hosting](https://dev.to/sreeraj-sreenivasan/the-2026-developers-guide-to-zero-cost-full-stack-hosting-fastapi-react-and-postgresql-dgh)
- [Render Free Tier 2026: Limits, Pricing & What Changed](https://agentdeals.dev/vendor/render)
- [Koyeb Free Tier 2026: Pricing, Limits & Credit Card](https://www.srvrlss.io/provider/koyeb/)
- [Railway vs Render — Free Tier Comparison (2026)](https://agentdeals.dev/railway-vs-render)
- [Write Cloudflare Workers in Python](https://developers.cloudflare.com/workers/languages/python/)
- [Python Workers redux: fast cold starts, packages, and a uv-first workflow](https://blog.cloudflare.com/python-workers-advancements/)
- [Cloudflare Workers Python FastAPI package docs](https://developers.cloudflare.com/workers/languages/python/packages/fastapi)
- [Connect to PostgreSQL — Cloudflare Hyperdrive](https://developers.cloudflare.com/hyperdrive/examples/connect-to-postgres/)
- [Hyperdrive connection pooling](https://developers.cloudflare.com/hyperdrive/concepts/connection-pooling/)
- [TCP sockets — Cloudflare Workers](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/)
- [Docker Spaces — Hugging Face](https://huggingface.co/docs/hub/en/spaces-sdks-docker)
- [Deploying a FastAPI App on Hugging Face Spaces](https://medium.com/@na.mazaheri/deploying-a-fastapi-app-on-hugging-face-spaces-and-handling-all-its-restrictions-d494d97a78fa)
- [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle Cloud free tier 2026: 4 OCPU/24GB cut to 2 OCPU/12GB](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/)
