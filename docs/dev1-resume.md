# Resume Prompt — dev1

**Delete this file when the goal below is met.** It is a handoff for one session and goes stale fast; leaving it in the
repo after launch is worse than not writing it. `git rm docs/dev1-resume.md` in the final PR.

---

## The Goal

**Official launch before 12am tonight.** The app is already live and working — this is not a build, it is closing the
gap between "works" and "worth showing people."

- **Client:** <https://makanlah-b5h.pages.dev>
- **API:** <https://makanlah-api.vercel.app>
- **Video:** `makanlah-video/handoff/makanlah-pitch.mp4` — 2:31, done, Merdeka-themed, for LinkedIn tomorrow

**One real user has tested it and his verdict is the launch bar**, not any internal check: _"the restaurants options are
kinda limited… plus I dunno their price range too, how do I use this app leh?"_ If that is still true at midnight, the
launch is a demo rather than a product.

---

## State At The Pause

|                     |                                                                                              |
| ------------------- | -------------------------------------------------------------------------------------------- |
| `main`              | `e1220aa`                                                                                    |
| API `/health`       | `85b9220` — **behind `main` by docs-only commits. No deploy needed. Verify before assuming** |
| Client `build.json` | `85b9220`                                                                                    |
| Corpus              | 1,507 posts · 247 venues · 2 platforms                                                       |
| Python suite        | 525 passing                                                                                  |

**First action on resume: verify prod rather than trusting this table.** Check the `/health` payload, not the status
code, and confirm the client bundle still references `makanlah-api.vercel.app`.

---

## The Three Peers

Same contract as before, in [#72](https://github.com/TolongLabs/MakanLah/issues/72).

| Session       | Role                                                           | Parked at                            |
| ------------- | -------------------------------------------------------------- | ------------------------------------ |
| `makanlah-13` | **You.** Backend, API, devops, data, ingestion, reconciliation | `main` clean                         |
| `makanlah-8d` | Frontend                                                       | `6525cea`, tree clean                |
| `makanlah-fb` | UAT                                                            | record at `scratchpad/UAT-ROUND2.md` |

**Message them first**, tell them the run is resuming and which sha is live. Both parked cleanly and are waiting.

**Both peers were right and you were wrong on four separate occasions today.** Peer 2 found sentiment reporting praise
as criticism by _reading the cards_ when the numbers agreed. Peer 3 found the walking-distance substitution and the gap
surface applying a weaker evidence standard than the ranked one. Take their findings seriously and verify them anyway —
Peer 3 withdrew two of their own after checking, and that is the behaviour to encourage.

---

## Two Questions Blocking Other People

Ask the owner early; both have someone waiting.

1. **#144 needs three one-word answers** — disclosure one-tap or always-open, whether the model blurb returns, dot
   density for #141. Peer 2's whole batch sits behind it, green and deploy-verified.
2. **#157 or the copilot first?** All three sessions agreed coverage precedes the copilot. The Merdeka video may change
   that. Ask, do not assume.

---

## Remaining Work, In Order

Full queue with worker assignments: [#160](https://github.com/TolongLabs/MakanLah/issues/160).

### Block 1 — Coverage. Nothing Else Matters Until This Moves

**[#157](https://github.com/TolongLabs/MakanLah/issues/157) — Google Maps enriches but never discovers.**
`enrich_gmaps.py:64` iterates `venue where exists (mention)`. Maps supplies **84% of the evidence and cannot introduce a
single restaurant**; every venue enters through RedNote's ~20 keywords. That is the ceiling the tester hit.

- A `discover()` draft exists on branch **`feat/gmaps-discovery-wip` (`250c602`)** and is **UNVERIFIED** — never run
  against a signed-in browser, and `LIST_JS` is a guess at the results-feed DOM. **Do not merge because it compiles.**
- Orchestrator-only: needs the CDP session.

**[#159](https://github.com/TolongLabs/MakanLah/issues/159) — the scraper has no keyword knowledge.** `KEYWORDS` is 20
strings typed once, and nothing records **which keyword discovered which post**, so no run can tell a productive term
from an exhausted one. **549 distinct hashtags sit unused in the 119 posts already captured** — `#吉隆坡探店`,
`#kl探店`, `#pjcafe`. Worker-suitable: harvesting tags from a fixture is a pure function with an easy failing test.

**[#158](https://github.com/TolongLabs/MakanLah/issues/158) — price.** 45 of 256 venues. Maps' price level is on place
records already loaded and thrown away. Fetch is orchestrator; parsing a figure from cached text is worker-suitable.

### Block 2 — Retrieval

- **[#85](https://github.com/TolongLabs/MakanLah/issues/85)** retrieval misses across three languages — now testable,
  since every post has a real language tag
- **[#59](https://github.com/TolongLabs/MakanLah/issues/59)** six venue groups collide under Han folding — pure
  function, six known pairs, worker-suitable
- **[#83](https://github.com/TolongLabs/MakanLah/issues/83)** cards cite a dead post when a live one exists

### Block 3 — Copilot, If The Owner Says So

`POST /ask/stream`: SSE, multi-turn `messages`, visible tool calls, `done` keeping `covered` + `citations` unchanged,
and **`POST /ask` retained as fallback**. Schema agreed with Peer 2, **whose client is already built, tested and
green**. Orchestrator-only — the honesty invariant lives in `makanlah/copilot.py`.

Also here: a static map tile per venue at ingestion, so the All Sources modal needs no third-party request-path fetch.

### Block 4 — Depth

**[#15](https://github.com/TolongLabs/MakanLah/issues/15)** 1,008 truncated Maps posts · **#116** API does not
auto-deploy · **#164** "Undisclosed Location" is a real venue whose name extraction lost, recoverable from its place id.

---

## Workers

**OpenCode: `openrouter/z-ai/glm-4.7-flash`.** **NOT `glm-5.3-flash`** — it returns empty completions or hangs
regardless of prompt, reproduced on a one-line prompt while 4.7-flash ran the same task in 3s. The standing-orders text
still names 5.3; ignore it.

**Devin: blocked.** Refuses with `Refusing to run in an untrusted workspace` despite `trusted_workspaces.json`. It needs
one interactive `devin` in the directory to trust it. This killed the Chatterbox voice spike; the eight Kokoro previews
in `makanlah-video/handoff/` remain the only voice samples.

**Never merge a worker's output on its self-report.** Three workers today produced output that read correct and was not:
one stopped 2 of 6 tests short without saying so, one `break`ed after the first match, one wrote to disk after being
told not to. **Write the failing test first, then run a hidden test the worker never saw.**

---

## Five Things That Will Bite You Again

These are the run's actual output. Each cost a round to learn.

1. **A count that is true by its rule and false as English.** #87, #111, #153 and the sentiment line were **one bug four
   times**, and unit tests passed through all four because each test asked the same question the code did. The invariant
   is in `docs/DESIGN.md` on Peer 2's branch: **any rendered count must equal the items visible on that surface, or name
   the property it counts.**

2. **A check that cannot see its own silence.** Peer 3's count-checker silently never fired twice — a heredoc, then a
   template literal, each eating the regex backslashes — and **its own test reported "3/5 OK" with all three false
   all-clears**. Mutation-test every check: break the subject on purpose and confirm it goes red.

3. **Right measurement, wrong scope.** "163 of 186 venues span more than one bucket" describes a venue's whole record;
   the card describes two or three trimmed posts, where the real figure is **82%, not 12%**. Same shape as reporting
   #143 fixed while production still disagreed on 5 of 25 — the unit tests built their own rows.

4. **Hand-written heuristics over Han text.** Three were written today and all three were wrong: `踩雷` matched inside
   `不踩雷` (inverting the meaning), `length < 3` flagged `鱼你`, `ckt` matched inside `mo(ckt)ail`. The rule that
   worked: **whole-word for Latin, substring for Han**, because 肉骨茶 inside 中药肉骨茶 is genuinely the same dish.

5. **A payload defect is not a defect until you check the client.** A `query_place_id` fix shipped for a bug that did
   not exist — `citationHref()` was already repairing it. The DOM is the only layer with a user in front of it.

---

## Non-Negotiables

From `AGENTS.md`, and they held all day:

- **Every result cites a real post.** A pick without one is dropped before the response is built, never returned with a
  caveat
- **Never fetch from a platform on the request path**
- **No single source may be load-bearing** — which #157 currently violates for _discovery_
- **`main` is PR-gated, merge only on green CI**, and never disable a check to make it pass
- **Rewrite `docs/PROGRESS.md` before the session ends.** It is the only thing that survives
