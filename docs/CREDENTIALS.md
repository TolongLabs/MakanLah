# Credentials And Logins

**Every human-gated login, done once, before an unattended run starts.** A missing credential is the fifth thing
[`SWARM.md`](SWARM.md#6-unattended-long-runs) lists as stopping a long run, and it is the only one a human must resolve
in person. Front-load all of it.

An agent never types a password, accepts terms, or submits a form on someone's behalf —
[`../AGENTS.md`](../AGENTS.md#cli-first-always). So each row below is either **yours to do once**, or **the agent's
forever after**.

---

## The Xiaohongshu Catch

> **Being signed in to Chrome on the workstation is necessary but not sufficient.** Headless Chromium launches a fresh,
> empty profile. It cannot see the desktop browser's cookies, and it will hit the login wall as if you had never signed
> in.

The session only reaches automation through one of three routes:

| Route                     | How                                                                                                  | Cost                                                                                           |
| ------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Attach to the profile** | Launch Chrome with `--user-data-dir=$HOME/.config/google-chrome --profile-directory=Default`         | Chrome must not already be running — the profile is locked to a live instance. Needs a display |
| **CDP attach**            | Start Chrome once with `--remote-debugging-port=9222` on the real profile; automation connects to it | Most robust for long runs. The port is the session — never expose it beyond localhost          |
| **`claude-in-chrome`**    | Drives the actual browser you are signed into                                                        | Interactive. Right for exploration, wrong for a scheduled ingestion run                        |

**A display is required for the first two.** On dev1 an SSH session has `DISPLAY` unset and `XDG_SESSION_TYPE=tty`, so
headful Chrome will not start from a terminal. Either run from the Qube's own GUI session, or wrap it:

```bash
sudo apt-get install -y xvfb
xvfb-run -a google-chrome --user-data-dir="$HOME/.config/google-chrome" --profile-directory=Default ...
```

**Treat the cookie jar as a live credential.** `~/.config/google-chrome/Default/Cookies` is not in the repo and must
never enter it — `.gitignore` covers `*.session` and the git guard blocks force-adding a corpus, but neither knows about
a path outside the tree. Point `XHS_SESSION_PATH` at it in `.env`; do not copy it in.

**Sessions expire, and that is a normal outcome, not a failure.** When one does, ingestion falls through to the next
source and the run continues ([`AUTONOMY.md`](AUTONOMY.md#standing-operational-defaults)). Re-authenticating is a human
task, queued as an issue, not a reason to stop.

---

## Do These Once, In A Browser

Ordered by what blocks the most if skipped.

| What                   | Why It Is Needed                                                    | After That                                                                                                      |
| ---------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Claude Code**        | The orchestrator. **Nothing runs without it**                       | `claude` — OAuth in a browser, once per machine                                                                 |
| **Xiaohongshu**        | The primary source. Already done on dev1                            | Keep the profile signed in; see the catch above                                                                 |
| **OpenRouter**         | The GLM-5.3-Flash worker lane, and the primary one after 2026-09-23 | Copy the key to `OPENROUTER_API_KEY`. No further browser                                                        |
| **Firecrawl**          | Open-web fallback sources. ~20k credits already available           | Copy the key to `FIRECRAWL_API_KEY`. No further browser                                                         |
| **Hermes Agent**       | Both runtimes — the copilot and ingestion                           | Copy the key to `HERMES_API_KEY`. Confirm the var names against its docs; `.env.example` marks them unconfirmed |
| **Devin** _(optional)_ | The free SWE-1.7 worker lane, until 2026-09-23                      | `devin` login. Skip it and OpenRouter covers the lane                                                           |
| **Codex** _(optional)_ | Second-opinion reviews, and image generation Claude Code cannot do  | `codex` login with a ChatGPT account                                                                            |

**GitHub needs nothing.** `gh` on dev1 is already authenticated with `ADMIN` on `TolongLabs/MakanLah`, so branches, PRs,
issues and merges all work headlessly.

---

## Fallback Sources

The design rule is that no single source is load-bearing, so fallbacks are not optional — and each carries its own auth
question. **Resolve this when choosing them, not when one goes dark.**

| Source Type                                     | Auth                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| Open web — blogs, listicles, review aggregators | None. Firecrawl handles these, and they need no session                        |
| Google Maps / Places reviews                    | An API key, not a browser login. Prefer it for exactly that reason             |
| Instagram, Facebook, TikTok                     | A logged-in session, with the same catch and the same fragility as Xiaohongshu |

**Prefer a fallback that needs no session.** A second login-walled source doubles the surface that can expire unattended
without doubling the resilience — two sessions that both go stale on the same trip is not a fallback, it is the same
failure twice.

---

## What Never Lands In The Repo

- **No `.env`.** `.env.example` carries key names, never values. The git guard blocks `git add .env`
- **No cookie jars, session files or auth tokens**, including inside a captured payload in `docs/source/`. Strip them
  before the file is written
- **No scraped corpus.** `data/raw/` and `data/corpus/` are gitignored and a force-add is blocked
- **No absolute path that only exists on one machine.** `XHS_SESSION_PATH` lives in `.env` for exactly this reason

`scripts/preflight.sh` reports which keys are present without ever reading a value, and the `env-drift` hook reports a
local `.env` that disagrees with the repository by naming keys, never values.
