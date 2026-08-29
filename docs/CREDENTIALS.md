# Credentials And Logins

**Every human-gated login, done once, before an unattended run starts.** A missing credential is the fifth thing
[`SWARM.md`](SWARM.md#6-unattended-long-runs) lists as stopping a long run, and it is the only one a human must resolve
in person. Front-load all of it.

An agent never types a password, accepts terms, or submits a form on someone's behalf —
[`../AGENTS.md`](../AGENTS.md#cli-first-always). So each row below is either **yours to do once**, or **the agent's
forever after**.

---

> **Read this first: the host is the identity, not the brand.** `xiaohongshu.com` and `rednote.com` serve the same
> content behind **separate sessions**. On the build machine the first was logged out and the second was signed in, and
> the scraper works against `rednote.com` for exactly that reason. Signing in to one does not sign you in to the other.
> If a capture returns nothing, check which host you are actually signed in to before assuming the session expired.

## The Xiaohongshu Catch

> **Being signed in to Chrome is necessary but not sufficient, and the obvious workaround is blocked.** Headless
> Chromium launches an empty profile and hits the login wall as if you had never signed in. Pointing `--user-data-dir`
> at the real profile does not fix it, because **Chrome 136+ refuses remote debugging against the default profile
> directory**:
>
> ```
> DevTools remote debugging requires a non-default data directory.
> Specify this using --user-data-dir.
> ```
>
> Verified on dev1, Chrome 151. It is a deliberate anti-cookie-theft measure with no flag to disable it. The failure is
> quiet: Chrome starts, serves no debugging port, and every fetch returns a login wall — which reads exactly like an
> expired session.

**Use `scripts/chrome-session.sh`.** It copies only the session-bearing files to a non-default directory, launches
Chrome there with CDP, and — importantly — **verifies the session actually carried** rather than assuming it did.

```bash
scripts/chrome-session.sh start     # copy, launch, wait for CDP
scripts/chrome-session.sh verify    # open xiaohongshu, fail loudly on a login wall
scripts/chrome-session.sh stop      # kill Chrome and delete the copy
```

Three things it handles that are easy to get wrong:

| Trap                                       | What happens without it                                                                                                                                   |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`Local State` must be copied too**       | On Linux it holds the key the cookie store is encrypted with. Cookies copied alone decrypt to nothing                                                     |
| **The source profile must not be running** | Chrome holds a lock; copying underneath it yields a torn cookie store that fails like an expired session                                                  |
| **No display over SSH**                    | `DISPLAY` is unset and `XDG_SESSION_TYPE=tty`, so the script falls back to `xvfb-run`. Headless mode is a different code path that some sites fingerprint |

**The copy is a duplicated live credential.** It lives at mode 700 under `~/.cache/`, never inside the repo, and `stop`
deletes it. Re-run `start` when the session expires — that is a normal outcome, not a failure, and ingestion falls
through to the next source meanwhile.

**For interactive exploration, the `claude-in-chrome` extension is the better tool** — it drives the browser you are
actually signed into, with no copy at all. It is wrong for scheduled ingestion because it needs a human in the loop,
which is the whole reason the CDP path exists.

## Do These Once, In A Browser

Ordered by what blocks the most if skipped.

| What                   | Why It Is Needed                                                      | After That                                                                                                                                 |
| ---------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Claude Code**        | The orchestrator. **Nothing runs without it**                         | `claude` — OAuth in a browser, once per machine                                                                                            |
| **RedNote**            | The primary source. **Sign in at `rednote.com`, not xiaohongshu.com** | Keep the profile signed in, and **quit Chrome** before `chrome-session.sh start`; see the catch above                                      |
| **Neon**               | The corpus. Nothing reads or writes without it                        | Create a project in a region near KL; copy the pooled and direct strings to `DATABASE_URL` / `DATABASE_URL_UNPOOLED`                       |
| **DashScope**          | **Extraction, embeddings and re-rank — all three lanes**              | Use the **International/Singapore** console. Copy the key to `DASHSCOPE_API_KEY`. Nearer KL than ModelScope, and one key covers everything |
| **Google Maps**        | The second source, and the geocoder                                   | **Nothing to do.** No API key, no billing. It runs over the same signed-in Chrome                                                          |
| **OpenRouter**         | The GLM-5.3-Flash worker lane, and the primary one after 2026-09-23   | Copy the key to `OPENROUTER_API_KEY`. No further browser                                                                                   |
| **Firecrawl**          | Open-web fallback sources. ~20k credits already available             | Copy the key to `FIRECRAWL_API_KEY`. No further browser                                                                                    |
| **Hermes Agent**       | Both runtimes — the copilot and ingestion                             | Copy the key to `HERMES_API_KEY`. Confirm the var names against its docs; `.env.example` marks them unconfirmed                            |
| **Devin** _(optional)_ | The free SWE-1.7 worker lane, until 2026-09-23                        | `devin` login. Skip it and OpenRouter covers the lane                                                                                      |
| **Codex** _(optional)_ | Second-opinion reviews, and image generation Claude Code cannot do    | `codex` login with a ChatGPT account                                                                                                       |

**GitHub needs nothing.** `gh` on dev1 is already authenticated with `ADMIN` on `TolongLabs/MakanLah`, so branches, PRs,
issues and merges all work headlessly.

---

## Fallback Sources

The design rule is that no single source is load-bearing, so fallbacks are not optional — and each carries its own auth
question. **Resolve this when choosing them, not when one goes dark.**

| Source Type                                     | Auth                                                                            |
| ----------------------------------------------- | ------------------------------------------------------------------------------- |
| Open web — blogs, listicles, review aggregators | None. Firecrawl handles these, and they need no session                         |
| Google Maps reviews                             | **In use, and needs nothing.** Read over CDP; the place URL carries coordinates |
| Instagram, Facebook, TikTok                     | A logged-in session, with the same catch and the same fragility as Xiaohongshu  |

**Prefer a fallback that needs no session.** A second login-walled source doubles the surface that can expire unattended
without doubling the resilience — two sessions that both go stale on the same trip is not a fallback, it is the same
failure twice.

---

## Geocoding, And What It Does Not Need

**Directions need nothing prepared.** The MVP deep-links to Google Maps rather than rendering one, and the URL scheme
takes no key, no SDK and no billing account. On a phone it opens the native app.

What does need a decision is **geocoding** — Xiaohongshu posts carry a restaurant name and a vague area, not
coordinates, and the core loop lets a user filter by distance. Start with **Nominatim**: free, no key, no billing, and
its one-request-per-second limit is irrelevant because geocoding runs at ingestion time, once per restaurant, with
nobody waiting.

**Measured, and Nominatim lost: 34%.** OpenStreetMap does not carry Chinese-only restaurant names for KL, and those were
most of the misses. Geocoding now runs over **Google Maps via CDP**, which needs no key and no billing because it reads
the place page rather than the Places API: the URL embeds coordinates as `!3d<lat>!4d<lng>`, and the `place_id` it
returns both sharpens the directions link and is the only evidence accepted for merging two venue rows.

Nominatim stays as the fallback. **Google Places, the paid API, was never needed** — which is why nothing here requires
a card.

---

## The ModelStudio Console Session

Free-quota state is not readable from the DashScope API key. It lives in the Alibaba Cloud console behind an account
login, so `scripts/quota.py` reads it through the same CDP Chrome the scraper uses:

```bash
scripts/chrome-session.sh start   # sign in to Alibaba Cloud once, in that window
scripts/quota.py                  # prints free quota for every lane config.py can resolve
```

**The login persists in `~/.cache/makanlah/chrome-session`, outside the repo, at mode 700.** `chrome-session.sh stop`
deletes it, so do not run `stop` if the point is to keep checking quota. It is a duplicated live credential either way:
treat that directory the way you would treat the browser profile it came from.

**Why a dashboard scrape rather than an API.** The console's own endpoints need a session token that is not the
DashScope key. The script therefore breaks when the console is redesigned, which is an accepted cost — the alternative
is a number nobody checks until a card is charged.

**It reads the model tabs separately on purpose.** The console splits LLM / Vision / Multimodal / Audio / Embedding and
a search only matches inside the active tab, so an embedding model looked up under LLM reports "not listed" — which
reads exactly like "no quota" and is not the same thing.

**Measured 2026-08-29, and the reason this exists:** `qwen3.8-flash`, the lane behind every `/recommend`, reads
**`Not Supported`** — no free quota at all, every call billed. `qwen-plus-2025-07-28` had 954,215 tokens left and
`text-embedding-v3` 956,723. Nothing in the repo said so ([#34](https://github.com/TolongLabs/MakanLah/issues/34)).

---

## What Never Lands In The Repo

- **No `.env`.** `.env.example` carries key names, never values. The git guard blocks `git add .env`
- **No cookie jars, session files or auth tokens**, including inside a captured payload in `docs/source/`. Strip them
  before the file is written
- **No scraped corpus.** `data/raw/` and `data/corpus/` are gitignored and a force-add is blocked
- **No absolute path that only exists on one machine.** `XHS_SESSION_PATH` lives in `.env` for exactly this reason

`scripts/preflight.sh` reports which keys are present without ever reading a value, and the `env-drift` hook reports a
local `.env` that disagrees with the repository by naming keys, never values.
