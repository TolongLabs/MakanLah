# Progress — 2026-08-30 · launch-ready, and the halal safeguard that was a coin flip

**`main` is at `d12ac69`. API `/health` reports `5bdd17d`, client `build.json` reports `d12ac69`.** The API is correctly
behind: the only commit between them touches `ingest/` and `docs/`, neither of which is in the API bundle (`vercel.json`
includes `makanlah/**` and `api/**`). **A differing sha is not drift — the question is whether the diff touches a
deployed path**, and #116 exists because answering it by hand has failed twice. **475 Python tests, lint and format
clean, CI green.** Verified on `main` rather than on a branch: `/recommend` with a radius returns cited results,
`/venue/{id}` serves a deep link, `/ask` answers from the corpus and admits a gap, `/auth/guest` reports `shared: true`.

**Agents merge on green CI now.** #23 replaced the blanket `gh pr merge` deny with `.claude/hooks/guard-merge.sh`, which
**fails closed**: it requires an explicit PR number, an OPEN state, every reported check passed, `mergeStateStatus`
CLEAN, and refuses `--admin`. Thirteen cases in `tests/test_merge_guard.sh`. **The first autonomous merge was #27.** The
hook takes effect only after a session restart — the harness caches permissions at start.

**Ranking is measured, not asserted.** `evals/` holds pinned ground truth and a runner. **p@5 0.982, wd@5 0.000, top1
49/51, p95 4.36s** — see the excerpt-ordering trade below, which cost 2 top1 and bought back 0.3s. **p95 is still
measured against a 3s target in [`PRD.md`](PRD.md)** and still not met, deliberately. Tracked as **#16**.

**A full eval run costs ~134k tokens**, 13% of a lane's free allowance, which does not refill before it expires on
**2026-10-13**. The runner prints the bill before spending it; use `--quick` while iterating.

**Every model lane is pinned to a dated free-quota snapshot.** The rolling DashScope aliases carry none. Re-check the
console before repinning.

**Web client is live:** <https://makanlah-b5h.pages.dev> · **API is live:** <https://makanlah-api.vercel.app>

---

## 2026-08-30 (Late) — The Pitch Deck, And A Fix I Reported Before It Was Fixed

**`main` is at `ccdc65f` and `/health` reports `ccdc65f`.** Three PRs landed: **#145** and **#147** (sentiment counts)
and **#146** (the pitch deck).

**The sentiment number took two goes, and the first report was wrong.** #143 was Peer 2's finding: bucket totals
disagreed with `corroboration.posts` on 9 of 10 venues. #145 fixed two causes — one vote per post rather than per
mention row, and dead posts excluded. Its unit tests were mutation-checked and passed, and **I reported it as done**.
Measured against production afterwards, **5 of 25 venues still disagreed**; Village Park read 7 sentiment against 3
posts. `citations` is trimmed to `per_venue` before it ships and `add_corroboration` counts what survives that trim,
while the tally counted every live post in the corpus. Four real Village Park posts were being counted into a breakdown
no reader could open from the card — **#111 in a new place**. #147 restricts the tally to the citations that ship.

**Production now reads 32 of 32 agreeing**, and the agreement is not vacuous: all 32 carry a non-empty breakdown, 15
have more than one post, and the buckets spread 19 positive / 19 mixed / 10 negative.

**The lesson is narrower than "test more".** Every unit test built its own rows, so they could only ever check the tally
against my own idea of the input. The trim happens in another function. Nothing failed — the tests never saw the real
row set. **A pure function's tests cannot verify a contract between two functions**, and the thing that caught it was
comparing two production fields that must agree.

**The pitch deck now looks like the product.** It read the app's tokens for the first time rather than approximating
them, and the chop — the cinnabar seal carrying 食, taken from `Chop.tsx` rather than redrawn — appears in the masthead
and anchors the close. `--enamel` marks where evidence came from and sits only on the source chip; `--seal` marks that a
pick is attested and marks only step 05 and the count of invented picks.

**Rendering the deck found a bug no numeric check saw.** The subtitle is burned in after the slides render, so a slide
cannot see what will cover it. The 208px band put the content floor at 872, **inside** the plate: it clipped the source
chip on slide 02 and `with a caveat.` on slide 01. `render.mjs` now fails the render if content crosses **852**, the
measured top row of a two-line libass plate at `MarginV=28`. Floors are 828 / 838 / 828, confirmed on the burned-in
frames rather than on the slides alone.

**Video: `makanlah-video/handoff/makanlah-pitch.mp4`, 2:31, 1920×1080, 7.9 MB, 0 dub overlaps.**

**Two worker findings worth carrying.** `openrouter/z-ai/glm-5.3-flash` **returns an empty completion or hangs**
regardless of prompt — three probes, one of them trivial; `glm-4.7-flash` ran the same prompt in 3s. Workers should not
use 5.3-flash until it recovers. Separately, the worker **wrote a file to disk after being told not to**, and its output
carried three defects that read as correct: unpacking `dict_row` results as tuples, `Connection.fetchall` (which does
not exist), and `SET langs = langs || %s`, which appends rather than replaces and so never clears the `und` tag it
exists to remove. **Not merged.**

**The Devin Chatterbox spike never ran.** It refused with `Refusing to run in an untrusted workspace` despite the
workspace being added to `trusted_workspaces.json`. No voice clone exists. The eight Kokoro previews in
`makanlah-video/handoff/` are the only voice samples available.

## 2026-08-30 (Owner's /discover Batch) — The Answer Was On The Card, Eighth And Grey

**PR #144 is open and awaiting CI.** Items 1, 2, 3 and part of 5 of the owner's `/discover` batch. He asked to
brainstorm it in this chat directly and chose the card shape and the URL behaviour himself.

**The finding that reframed item 1.** He said nothing on the page told him why any result was there. The answer had been
on the card since the first build — `basisLine`, "Here because a post names this dish" — as the **eighth line, in the
same grey as two neighbouring sentences answering different questions**. The data was never missing. An answer formatted
like a footnote is not an answer, and no data-presence check would ever have caught it.

It is now the subtitle, and it absorbed the metadata row that used to sit there:
`Names bak kut teh · 3 posts, 2 people · 9.4 km · Cheras`. Three lines became one that says more. The rest went behind a
per-card `Why This Showed`, which renders only where there is something the row did not already say.

### Measured Before Designing, Across 35 Live Results

| Signal                                 | Live reality                                   |
| -------------------------------------- | ---------------------------------------------- |
| `basis: 'dish'` with `similarity: 0.0` | **15 of 35** — 63% of all dish matches         |
| `corroboration.authors == 0`           | 12 of 35 — Google Maps reviewers are anonymous |
| `venue.area` absent                    | 19 of 35                                       |
| `sentiment` on the response            | absent, then shipped mid-session as #142       |

`makanlah-13` flagged the zero-similarity case as "one nuance". It is 63% of dish matches, so **never rendering the
number** is now measured rather than stylistic. Recorded in `TRD.md`.

### Sentiment Is Wired But Gated, And That Is #111 Again

`sentiment` counts **mention rows**; `corroboration` counts **live posts**. Across ten live `nasi lemak` results **nine
disagreed**, several by nine to one — Village Park reads 3 posts against 15 sentiment entries. Ungated, a card says "1
post" in its subtitle and "All 9 posts positive" four lines below. `sentimentLine(sentiment, livePosts)` renders only
where the totals agree; it lights up on its own once the API filters. **Filed as #143.**

**I had the silent case backwards and the data corrected me.** I first suppressed unanimity as noise, assuming agreement
was common. 163 of 186 multi-mention venues span more than one bucket — agreement is the 12% case and is the informative
one. Both now print.

### What Was Refused, And Why

- **Images and a menu (item 4).** 0 of 1507 posts carry media, 0 of 247 venues, no menu field. An empty slot on 100% of
  cards is worse than no slot. Needs a re-capture; not this batch
- **A Directions dialog.** Google Maps sets `frame-ancestors` and cannot be embedded, so the dialog could only hold a
  link to Google Maps. `target="_blank"` already meets the stated requirement
- **The model-written `why` on a ranked card.** It answered the same question the fact row now answers and only one of
  the two can be checked against a post. Still renders on `/r/:venueId`

### Above The Fold, Which Item 5 Actually Was

Moving Ask into a dialog removed the reason the companion aside was hoisted above the picks below 64rem. It keeps the
position — its line is a caveat about the list — but lost the card chrome.

| Width      | Aside height  | First pick top | Above the fold |
| ---------- | ------------- | -------------- | -------------- |
| 390 x 844  | 229 → **135** | 799 → **706**  | no → **yes**   |
| 834 x 1112 | 322 → **236** | 750 → **665**  | yes            |

### The New Check, And Why The Obvious One Would Have Passed

`scripts/discover_why_check.mjs`, in CI. It stubs `/recommend` with shapes copied from production, because the cases
that matter are the awkward ones and waiting for them to appear in a live query is how a check ends up asserting only
the happy path. **Its load-bearing assertion is that the answer outweighs the metadata beside it** — every other
assertion passes on the old card too, because the old card carried the same words.

Five mutations, each reddening its own check and nothing else: leaking `similarity`, burying the negative count,
restoring the model prose, flattening `.why-lead` to the metadata colour, removing the sentiment unit gate.

### The Sentiment Line Was Held Twice, For Two Different Reasons

Worth separating, because the second failure is invisible to the check that caught the first.

**First hold: the units disagreed.** `sentiment` counted mention rows, `corroboration` counted live posts; nine of ten
`nasi lemak` results disagreed. Fixed by `#145` then `#147` — the first fix was complete by its own measure and
production still disagreed on 5 of 25. `sentimentLine(sentiment, livePosts)` gates on agreement, and it lit up exactly
as intended once the units matched: 33/33 agreeing on an independent four-query sample.

**Second hold: the units agreed and the buckets were wrong.** Reading what it rendered, **8 of 10 venues carrying a
negative bucket contained no negative language at all**. `王美记` bucketed 0 positive / 2 negative on excerpts saying
"deserves 5 stars" and "definitely worth checking out", and the card said **"2 of 2 posts critical"** about a
Michelin-listed shop. **A unit-agreement gate cannot see this** — both numbers were right and the classification was
not.

**My diagnosis was the shallow half.** I said the `-0.2` threshold was too low. `makanlah-13` found the real cause:
Google Maps has no per-review URL, so ~8 reviews share one, and a "most critical bucket wins" rule turned one 1-star
review into a verdict on all eight. Fixed in `#151` by averaging within an identity and moving the cut points onto the
star scale. **Unflag `CLASSIFICATION_TRUSTED` only after verifying against excerpts** — twice now the first fix has been
incomplete, and twice the second look found the real thing.

**Held in both directions, deliberately.** Rendering only the favourable half biases every card toward good news, which
is worse than showing neither.

### #153 — The Same Root Cause Is Also Silencing Evidence

`post_url` as identity does something larger than the sentiment bug. **14 of 20 venues ship more citations than distinct
URLs.** `Upper House` carries three plainly different reviewers on one URL and renders:

```
Names char siew · 1 post        excerpts shown: 1        corroboration: no stamp
```

Three consequences, all from one key: the card prints "1 post" when three people wrote; `citable()` dedupes on URL so
**two thirds of the writing never renders**; and `independentlyBacked` needs `posts >= 2`, so a venue with three
independent voices is denied the stamp. **That last one is #87 in the mirror** — #87 granted the stamp where it was not
earned and was treated as a launch blocker.

Every error here is conservative, so it is not dangerous and not a launch blocker. The client cannot fix it alone:
`citable()` dedupes on URL because with only a URL it cannot tell a duplicate from three reviewers. It needs
`source_post.id` on each citation.

### The Owner's Second Batch — A Copilot, A Brief, And One Correction Taken

**The copilot is a copilot.** `Ask About This` opens a chat with the character live inside it, multi-turn, tool calls
streaming in expanded and collapsing to `2 steps before answering` once she replies — still openable, because a trail
you cannot reopen is not a trail. **The trace is the evidence claim made watchable**: `copilot.py` has always enforced
that she answers from stored excerpts or declines, and until now the user was only told she looked.

**One stage, moved, never two.** The aside unmounts her while the dialog is open. Two Live2D stages is two WebGL
contexts for one character and on some drivers the second silently kills the first — page renders, aside goes black,
nothing logged. `scripts/copilot_check.mjs` counts canvases across the handoff and was mutation-tested by letting the
aside keep its stage.

**`POST /ask` is the live path today.** `askStream` parses SSE and NDJSON with one reader; `NoStream` falls back. The
transport is agreed with `makanlah-13`, who is sequencing it behind **#157** — every venue enters through RedNote's ~20
keywords, so Google Maps supplies 84% of the evidence and cannot introduce a single restaurant. A copilot over 256
venues still cannot answer "where should my family eat tonight", and that is the right call.

**The map was built wrong and the objection was right.** First version fetched OSM tiles client-side. It worked. OSM's
tile policy is explicit about bulk use by applications and a tile request per viewer is a rate limit on infrastructure
we do not own — I had weighed it against our own corpus rule and missed that the binding constraint was somebody else's
terms. Now renders a stored image, nothing until one exists. `docs/DESIGN.md` gains the map as a documented fourth
exception to the no-images-near-evidence rule.

**#153 closed on both sides.** `post_url` is not an identity: Maps has no per-review URL and ~8 reviews share one. Upper
House shipped three reviewers, rendered **one**, and was denied a stamp it had earned — #87 in the mirror. `citable()`
now keys on `post_id`; the card reads "3 posts" and the dialog renders three testimonies. The shared URL was also
producing three identical React keys, unreachable only because the dedupe was hiding it.

**The stamp still does not fire there, deliberately.** Three anonymous same-platform reviews clear `posts >= 2` but not
`authors >= 2 || platforms >= 2`. They are almost certainly three people; the data does not say so, and inferring it is
how #87 happened.

### Two Instrument Failures Worth Carrying, Both Recorded In AUTONOMY.md

**A guard can be the defect.** Detecting UAT's `Undisclosed Location` took a regex plus `len(name) < 3`. Its only hit
was **`鱼你`** — a real restaurant with a normal two-character Chinese name. That filter would have shipped and deleted
only Chinese venues.

**A sweep that picks its own scope agrees with itself.** "38 venues, zero unusable, cannot reproduce" was true and
worthless: every query ran from one origin and the venue sat in a different walking-distance pool. `makanlah-fb`
reproduced it in one call by varying what the sweep held fixed.

**A conflicted PR gets no CI at all, silently.** `main` moved four times underneath #144; GitHub cannot build a merge
ref for a conflicted PR, so two pushes ran nothing — no red check, no queued run. A watcher reported "success" for a
stale commit because it matched the newest _existing_ run rather than the run for HEAD.

### Where To Pick Up

- **#141** — the visual pass the owner asked for: Apple-leaning surface, dotted sketchboard ground. Deliberately
  deferred so it styles final markup rather than markup about to change
- **#143** — sentiment filtered to live posts; the client needs no change when it lands
- **#140** (`makanlah-13`) — `canonical_for_query` resolves only curated dish names, so all 14 common ingredient words
  route into the semantic lane. A `crab` query returns a chicken rice shop. The subtitle names the weak lane plainly
  rather than papering over it, but the retrieval fix is backend
- The header chrome above the results is the remaining fold cost at phone width. Overlaps #141
- `makanlah-13` was writing a deeper `/discover` UX spec; it had not arrived when this shipped

---

## 2026-08-30 (Post-Launch State) — What Shipped After The Call, And What Is Deliberately Parked

**MakanLah is launch-ready and prod is healthy.** `degraded: false`, every returned result carries citations, corpus
1507 posts across 247 venues. Emilia, Kelvin and Nabilah all yes, verified independently against what prod serves.

### #15 Advanced, Then Was Stopped On Purpose

`pending_venues` orders by mention count, so **every `--limit N` run without an offset re-captured the same top N** —
three batches produced 40 venue-passes and only 27 band repairs. #128 adds `--offset` plus a `venue.id` tie-break,
without which `OFFSET` pagination can silently repeat or skip rows between pages and hide the very problem it fixes.
Verified as a difference rather than a presence: page 0 and page 14 share **0 of 14** venues.

| Google Maps Corpus      | Session Start | Now                                            |
| ----------------------- | ------------- | ---------------------------------------------- |
| Posts over 300 chars    | 52            | **350**                                        |
| 230–250 truncation band | 488           | **362**                                        |
| Average length          | 197           | **316**                                        |
| Longest post            | 340           | **3229**                                       |
| Total posts             | 1388          | **1388** — repaired in place, never duplicated |

**Then stopped deliberately.** Each `enrich_gmaps` run opens an `ingest_run` row, and the API honestly reports an
unfinished one as degraded — so while a batch is in flight, prod tells visitors _"the last Google Maps refresh did not
finish."_ It clears itself on completion, but **running ingestion against a product whose link may be shared at any
moment is the wrong trade.** Resume at a quiet hour.

**Repairing `raw_text` changes nothing a reader sees.** Excerpts were derived at extraction time, so they stay truncated
until `ingest/pipeline.py` replays. That replay spends DashScope credit and is therefore **the owner's call, not an
agent's** — parked, not forgotten.

### #129 — The Free Quota Lapsed Under Two Request-Path Lanes

The owner reported on 2026-08-30 that Alibaba Cloud emailed to say the `qwen3.7-flash` free quota is exhausted.
**Re-rank (every `/recommend`) and copilot (every `/ask`)** both default to `qwen3.7-flash-2026-07-15` when
`DASHSCOPE_API_KEY` is set. Nothing broke — the lane moved from free to paid, and a `spicy noodles` query still returned
3 ranked results in 3.6s. **Spend that day: RM 0.0716 against a RM 10 ceiling.** The exposure scales with traffic, and a
launch post is exactly the traffic shape that makes today's number a poor predictor of tomorrow's.

### A Health Field Should Report The Capability, Not Its Configuration

Peer 3's generalisation, recorded because two of the three each cost a cycle:

| Field                | Reported                   | The Question Actually Being Asked                |
| -------------------- | -------------------------- | ------------------------------------------------ |
| `database: true`     | credentials are configured | are they the ones we think, from where we think? |
| _(no version field)_ | —                          | **is what I am looking at deployed?**            |
| `rerank: true`       | a **key** is configured    | does the lane still have **quota**?              |

Each is true, and each answers something narrower than the reader intends. They cannot be caught by disbelieving the
value — only by noticing the question has drifted. `rerank: "ok" | "no_quota" | "unconfigured"` distinguishes what a
boolean cannot. **Recorded on #129, not proposed as work.**

---

## 2026-08-30 (Launch Ready) — Three Personas Yes, And A Safeguard That Was A Coin Flip

**MakanLah is launch-ready.** All three UAT personas returned YES, verified independently against prod at `5bdd17d`:
**Kelvin** (`肉骨茶`, `蛋挞` clean, every citation opens), **Emilia** (empty state names the distance rather than
blaming the corpus), **Nabilah** (told plainly what the app does not know, shown one real `清真友好` testimony, asked to
judge it herself). **The citation trail holds for all three, which is what sank two of them in round one** — 6 of 8
cards linking dead posts and an audit page broken on 5 of 8, both closed and independently re-measured.

**Nabilah is a yes as a discovery tool, not a decision tool.** She still cannot filter by halal, and the notice she
reads is English while the evidence it points her to is Chinese. Recorded on #115, not hidden.

### The Halal Safeguard Was Probabilistic, And One Sample Could Not See It

`why` is **regenerated per request by a model**. #122 and #124 filtered the text it produced, so both were only as good
as the phrasing they anticipated. Peer 3 measured **12 identical calls** where this session had measured one:

|                                | Before #126 | After #126 |
| ------------------------------ | ----------- | ---------- |
| Non-empty `why` on a gap query | **5**       | 0          |
| Of those, asserting halal      | **4**       | 0          |

`Nasional halal, dekat Masjid Jamek` reached a **rendered card, in Malay**. The same query returned `why=''` on other
calls, which is exactly why the single-sample check passed. **A safeguard that is probabilistic on halal is not a
safeguard.**

#126 made it structural: a query raising a coverage gap drops **every** `why` in the response. No model output to match,
nothing to phrase around. It cost one defensible line — `清真友好，国民老店` quotes the poster and infers nothing — and
bought a guarantee independent of what a model said this time. **The evidence is untouched**: `gap_mentions` still marks
the venue and the citation stays on the card.

**The new lesson, and it is a different one:** every other catch this run was an instrument problem. This was the first
where the **subject** is stochastic and the instrument was fine. **A check that samples a non-deterministic generator
once measures that sample, not the system** — verifying it needs a rate over N, not a pass over one.

### Also This Session

**Ten instrument-versus-subject catches**, now split between false all-clears and false alarms: a cancelled CI deploy
leaving a merged green fix undeployed (#116), a probe run against a stale local `main` reporting a pass for a check that
never executed, an `expect(phase, …)` assertion that could not fail (#118), and a coverage notice that was **correct
end-to-end on the server, present in every response, and rendered by nobody** — with no test failing on either side.

**The video is recorded, verified and handed over.** `HANDOVER.md` records its validity as **conditional** —
frame-by-frame against one query's ranking, margin of one venue and ~200 px of scroll — and states the audio as
**unjudged rather than unverified**: silence, clipping, dead air, channel and dynamics all checked mechanically, nobody
has heard it.

---

## 2026-08-29 (Launch Call) — The Product Is Launch-Ready, And The Recorder Was Telling The Truth

**MakanLah is declared launch-ready and the launch video is recorded.** `makanlah-demo.mp4`, 1920x1080, 56.7s, 5.1 MB,
English subtitles bottom-centred, narrated by Kokoro `jf_nezumi`. It lives in the scratch run directory and is
deliberately **not** committed. Peer 3 closed the last blocking condition (#106) before filming.

**The recording was blocked by memory, and the fix was not to kill anything.** Two runs died on
`page.goto: Page crashed` with `ERR_INSUFFICIENT_RESOURCES`. `/dev/shm` was clear at 10%, so it was real RAM: 564 MB
free against a swap partition of 1024 MB that was **1023.8 MB used, 172 kB free**. Both long-lived Chrome profiles were
accounted for — `makanlah/chrome-session` is the 23-hour signed-in RedNote CDP credential, and `ms-playwright-mcp`
belongs to another session — so there were no orphans to reclaim. A **6 GB swapfile on `/home`** (103 GB idle) cleared
it on the next attempt. It is deliberately **not** in `/etc/fstab`: it evaporates on reboot, so nothing permanent
changed.

### The Corroboration Frame Read Zero, And Zero Was Correct

The first successful capture reported `corroboration pairs on screen: 0`, which `scripts/demo/README.md` says is a
recorded bug. It was not. Three checks, each against something the previous one did not own:

| Check                                                                     | Result                                                                        |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Deployed bundle still contains `evidence-pair`, `testimony`, `corroborat` | Yes — the selector survived the redesign                                      |
| API returns corroborated venues                                           | Yes — `nasi lemak` returns 5 two-platform venues                              |
| The filmed dish's second platform is alive                                | **No** — every bak kut teh venue with 2 platforms has its RedNote post `dead` |

`cravingOptions` is deterministic from the clock; at 19:00 it leads with `肉骨茶 bak kut teh`, and `leadPair` correctly
refuses to pair a dead post with a live one. **The recorder was honest and the data was the constraint.** Renderable
pairs for that hour's three cravings, measured by mirroring `leadPair`'s own rule rather than the API's looser
`platforms >= 2`: bak kut teh **0 of 4**, ayam goreng **1 of 2**, `海鲜 seafood 大排档` **3 of 4**. Re-recorded with
`DEMO_CRAVING=2` (PR **#112**): 3 pairs, a `corroboration` beat at 37.6s, matching the independently predicted three
(肥肥蟹, Talkcrab Subang, 海脚人). Frames were checked **by eye**, not by pixel arithmetic — the mistake that passed a
subtitle check on type twice the correct size.

### Prod Was Drifting And A 200 Would Not Have Shown It

The client reported `0d9a933` while `/health` reported `665cbaf` — **the API was two commits behind a client already
shipping the UI for #110**, so `evidence_gap` was inert on prod. Deployed and verified: `/health` now reports `0d9a933`.
**#110 then verified against its own test matrix on prod**: `roti canai` returns `results=0` with `evidence_gap` naming
**Devi's Corner** and **Kapitan**, Potato Corner correctly excluded, neither pickable.

### #111 — `evidenceOf` Counts A Dead Post Toward "Two Sources"

`citable()` dedupes by `post_url` and does **not** filter `dead`, so `evidenceOf` reads `corroborated` where `leadPair`
renders one testimony. **7 of 48 results across 15 dish queries.** Latent rather than live: `Discover.tsx:320` passes
`evidenceOf(results[0])`, and no top pick overclaimed in that sample. Left with peer 2 rather than opening a second PR
into `web/src` mid-redesign. Fix is one line; the test must assert `evidenceOf` and `leadPair` **agree**, because a
check consulting only the changed function agrees with itself.

---

## 2026-08-29 (Late) — A Stamp That Produced The Failure It Exists To Prevent

**Merged and deployed: #110, #114, #117.** Client `ecbd030`.

**The corroboration stamp counted posts nobody can open.** `add_corroboration` counted every citation,
so 兴记肉骨茶 rendered "Corroborated by two independent sources" over **four posts of which three are unopenable** — a
reader clicking through to check would have found one testimony behind a claim of two. **The stamp was producing the
exact failure it exists to prevent.** Measured across 8 queries and 59 results, **11 overclaimed**; 32 of 55 still carry
it afterwards.

The client half was the same defect, filed separately as #111: `leadPair` refuses a dead citation and `evidenceOf`
counted it, so the companion could claim two sources beside a card rendering one. **7 of 48 results across 15 queries.**
Latent only because Discover reads `results[0]`, and a peer noted correctly that the shield is _ranking order_, not
structure — 兴记 has been rank 1 on `肉骨茶` in earlier builds.

**Verified by two independent recounts, neither of which re-ran the function under test.** A peer recomputed
posts/authors/platforms from the raw `citations` arrays with their own liveness set and matched `add_corroboration` on
**61 of 61 venues**, reduced **if and only if** the row carries a dead citation — 11 of 11 with, 50 of 50 without. The
web test asserts `evidenceOf` and `leadPair(...).length > 1` **agree** across the committed prod fixture, plus a second
test that the fixture still contains a row where they used to disagree.

**#98's decidable half shipped as `evidence_gap` (#110).** `roti canai` returned Potato Corner: the lane resolved the
dish, found exactly Devi's Corner and Kapitan, and both were dropped because their only citations are dead. Now
`results: []` plus a block naming both venues with `place_id` links. **Names rather than counts**, because the two
claims are not equally checkable — that a post said something is unverifiable once the post is gone, while the
restaurant is checkable in ten seconds.

**The companion contradicted the page.** On that gap screen she read _"Answer the four questions and this fills in"_
directly beneath _"Filtered by your answers: nasi lemak 椰浆饭, On my own, All of KL, Something familiar"_. The
`curious` mood collapsed "nothing searched yet" into "searched and found nothing". `CompanionPhase` separates them.

### The Sixth Instrument, And It Was Mine

The other five checks owned their definition of success. **This one never consulted its subject at all**:
`expect(phase, ...)` instead of `expect(phase(), ...)` — a function reference is never equal to `'idle'`, so the
assertion could not fail against _any_ implementation, and the line reads exactly like an assertion. Found by pinning
the component to always pass `'idle'` and watching the test stay green. Now in [`AUTONOMY.md`](AUTONOMY.md) via #118.

**Six across three sessions in one day is not carelessness. It is the default failure mode of verification written by
whoever wrote the fix.** A check is trusted the moment it is green, and nothing except breaking the subject on purpose
distinguishes green-because-correct from green-because-blind.

**One deployment fact that cost two false readings tonight:** the client auto-deploys on merge, the API does not. A PR
touching `makanlah/` or `api/` ships **half-live** until `scripts/deploy-api.sh` runs, and both times the symptom was a
feature that looked broken while every test stayed green. Tracked as #116.

---

## 2026-08-29 (UAT Rounds Two And Three) — Six Merges, And Five Instruments Caught Measuring Themselves

**Merged and on prod: #94, #95, #97, #99, #101, #103, #104, #106.** Peers shipped #92, #96, #100, #102, #105 alongside.
Client `dc68121`, API commit now reported by `/health` (#102) — the two deploy independently and **were observed one
commit apart**, which is why that endpoint exists.

**The largest thing fixed: the lexical lane could see 12% of the corpus.** `dishes.py` hand-listed **15** dishes against
**838 distinct dish strings across 1033 dish-mentions** — 12.3% of strings, 18.1% of mentions, **0 of 10 mixed-script
strings**. The vocabulary is now the corpus (810 keys), with the alias table kept for the one job folding cannot do.
Measured on prod, before and after:

| Query        | Before                                       | After                                    |
| ------------ | -------------------------------------------- | ---------------------------------------- |
| `蛋挞`       | Gu On Korean BBQ, ALVA, The Tokyo Restaurant | **华阳 Oriental Kopi**, `basis=dish`     |
| `char siew`  | 1 result, `basis=semantic`                   | **5 results, all `basis=dish`**          |
| `叉烧`       | `basis=semantic`, `dish=None`                | `basis=dish`, incl. 碧華樓 tagged `叉燒` |
| mood queries | —                                            | byte-identical, deliberately untouched   |

**A negative result worth more than the fix, recorded on #85 so nobody re-derives it: a similarity floor cannot separate
answerable from unanswerable queries.** `蛋挞` scores **0.5651** while `ayam goreng berempah` scores 0.5877 and
`kimchi jjigae` 0.6088 — the answerable query scores _below_ two that are not in the corpus at all. Any threshold
rejecting the misses rejects the hits.

**#98 is the half that was split out, and it is the launch-relevant one.** The app answers confidently where the honest
answer is that nobody wrote about it. The sharpest case is `roti canai`: the corpus **does** carry the dish, both venues
carrying it have only dead citations, `with_live_citations` correctly drops them, and the user gets Potato Corner. **The
app is most misleading exactly where it knows most**, and every citation that dies converts a good answer into this
silently.

**Three citation-trail fixes, three different surfaces, three different right answers.** The card is a pointer, the
audit page is a record, and the payload is a contract:

| Surface      | Defect                                                                  | Fix                                            |
| ------------ | ----------------------------------------------------------------------- | ---------------------------------------------- |
| Result card  | 3 of 5 cards rendered a dead RedNote chip                               | Drop the chip; a dead pointer is worth nothing |
| `/r/:id`     | 5 of 8 visible RedNote links dead, unlabelled                           | Keep the row, lose the link, say so            |
| `match.dish` | Per-query while `basis` was per-row, so 5 rows named a dish they missed | Per-row                                        |

Hiding rows on the audit page was rejected: a stamp reading `posts: 4` over a page showing one row invites the doubt the
stamp exists to answer.

**The corroboration stamp was inverted and punished its own best evidence.** `independentlyBacked()` required
`c.authors >= 2`, and Maps citations carry `author_handle: null`. Four RedNote posts by two handles were stamped; two
RedNote posts plus a Maps review were not. Now `posts >= 2 && (authors >= 2 || platforms >= 2)`. **Verified 17 of 17
rows across three queries on prod, moving in both directions.** One caveat travels with it: no `posts=1, platforms=2`
venue exists, so **the floor clause is not exercisable through the UI** and is covered by mutation tests only.

**An unhandled 500 lost its CORS header** (#81). Starlette's `ServerErrorMiddleware` sits outside `CORSMiddleware`, so a
server fault read in the browser as a CORS misconfiguration. Caught one layer inside instead — **the registration order
is the fix**, and there is a comment at the call saying so.

**The companion had two gates on two screens and only one was ever measured.** `/discover` mounted her from 48rem;
`/taste` held out until 56rem. Measured at 834:

|                     | Before            | After                                         |
| ------------------- | ----------------- | --------------------------------------------- |
| `/taste` canvas     | NONE              | **288×220**, CI ink **56.9%**, head at row 14 |
| `/taste` dead space | 549px             | 321px                                         |
| `/discover` stage   | 720×180 letterbox | 288×200                                       |
| `/discover` aside   | 770×419           | 770×322                                       |

`Live2DStage.frame()` scales purely by height and centres on `w / 2`, so an uncapped stage does not enlarge her — it
parks her in a 4:1 letterbox with the bubble's tail pointing at 41px of nothing.

### Five Instruments Caught Measuring Themselves, In One Afternoon

The rate says this is the default failure of this work, not carelessness. **Every one was caught by a control, except
the one caught by a peer.**

1. `taste_tablet_check.mjs` printed **four green ticks at four widths while measuring nothing** — `.option` matched
   hidden step panels, so the clearance assertion read `0 <= 1031`
2. A peer's 834 mascot run blocked the `image` resource type; Live2D textures are `texture_00.png`, so the probe
   measured its own blocking
3. A peer's S1 "crash" was DOM text slicing in the reader, not the app
4. A peer computed dead chips from the **API payload** rather than the rendered DOM — the payload carries dead citations
   by design, and the question that matters is what the reader saw
5. A peer reported the tablet mascot broken from `/taste` alone. **No control caught this one**; bundle evidence from a
   second session did

**And one of my own reports deserved the distrust it got.** I wrote "measured against prod" for #99 when what I ran was
`rank.recommend()` in-process against the prod _database_. That verifies the code and does **not** verify that
production serves it — which is precisely where a green check hides a broken deploy.

**Neither machine can verify that the mascot paints.** Headless Chromium here reports `coverage=0.0%` at every width
**including 1440** — its WebGL will not run Cubism. Geometry is verified locally, ink by CI, and `mascot_check.mjs` now
carries the 834 case so the pixel count happens where the instrument works.

**Closed:** #81, #84, #93. **Filed:** #93, #98. **Still open and not mine:** #86 (no halal corpus signal — the tablet
persona's blocker is data, not frontend), #78 (Cubism shader warning), #83's remaining API-side work.

---

## 2026-08-29 (UAT Round Two) — A Stamp That Punished Its Own Best Evidence

**Merged: #94 (corroboration), #95 (CORS on a fault), #97 (tablet companion, in CI now).** Prod served `7bfbdca` at
21:22:15Z and the stamp fix was verified there across three queries by a second session: **17 of 17 rows correct, moving
in both directions.** Closed **#84** with live evidence, and **#81**.

**The corroboration stamp was inverted, and it withheld itself from exactly the strongest evidence the corpus has.**
`independentlyBacked()` required `c.authors >= 2`. Google Maps citations carry `author_handle: null`, so a Maps review
counts zero authors — which meant four RedNote posts by two handles were stamped and two RedNote posts plus a Maps
review were not. Cross-platform agreement is the one thing the companion's own copy calls strongest, and it was the case
being penalised. Now `posts >= 2 && (authors >= 2 || platforms >= 2)`. **Two posts stays as the floor**: one post is one
voice however many platforms syndicate it.

**A caveat that travels with that verification.** No `posts=1, platforms=2` venue exists in the corpus, so the floor
clause **cannot be exercised through the UI at all**. It is covered by mutation tests in `evidence.test.ts` and by
nothing else. Reported as "not exercisable", never as a pass.

**An unhandled 500 used to arrive with no `Access-Control-Allow-Origin`** (#81), so a server fault read in the browser
as a CORS misconfiguration and sent whoever debugged it to audit a config that was already correct. Starlette's
`ServerErrorMiddleware` sits **outside** `CORSMiddleware`. Fixed by catching one layer inside it — `add_middleware`
inserts at the front, so the handler is registered **before** the CORS call in order to end up within it. **The ordering
is the fix**, which is why there is a comment saying so at the call. Still a 500, still logs the traceback, body names
the exception class and never its message, `degraded` absent because our bug is not an outage.

**Two screens hosted the companion and they had two different gates.** `/discover` mounted her from 48rem; `/taste` held
out until 56rem because its comment said the gate mirrored the rail's second column — answering "is there room for a
character" with the answer to "is there room for a column". Measured at 834, before and after:

| Surface         | Before                 | After                  |
| --------------- | ---------------------- | ---------------------- |
| `/taste` 834    | canvas NONE, gap 549px | **288×220**, gap 321px |
| `/taste` 768    | canvas NONE, gap 549px | **288×220**, gap 321px |
| `/discover` 834 | 720×180                | **288×200**            |
| 390 (phone)     | NONE                   | unchanged, deliberate  |

**The width cap is not cosmetic.** `Live2DStage.frame()` scales purely by height and centres on `w / 2`, so an uncapped
stage does not enlarge her — it parks her small in a 4:1 letterbox while the bubble's tail stays at `left: var(--s6)`
pointing at 41px of nothing.

**Three checks that agreed with themselves, caught this session.** The pattern is not slowing down.

1. `taste_tablet_check.mjs` printed **four green ticks at four widths while measuring nothing** — `.option` matched
   hidden step panels, so the clearance assertion read `0 <= 1031`. The `optionCount` guard is the assertion, not
   tidiness
2. A peer reported the mascot absent at 834 on a route they had not meant to test, then corrected it themselves
3. A peer's first 834 run blocked the `image` resource type; Live2D textures are `texture_00.png`, so the probe measured
   its own blocking and read as a regression

**Neither this machine nor the peer's can verify that she is painted.** Headless Chromium here reports `coverage=0.0%`
at every width **including 1440** — its WebGL will not run Cubism at all. Geometry is verified locally, ink is verified
by CI, and `mascot_check.mjs` now carries the 834 case so the pixel count happens where the instrument works.

**#83's consequence, written down before somebody files it as a bug.** `with_live_citations()` drops any entry whose
every citation is known dead, so `宝香绑线肉骨茶` — one citation, confirmed dead — is now absent from **every** result
set including a search for its own exact name. Measured across five queries. Correct behaviour, and it was nearly
escalated as an indexing fault. Noted on the issue.

**#85 is next and is the largest open product defect.** `蛋挞`, `ayam goreng berempah` and `char kuey teow` all miss,
and `something not too heavy` still returns FamilyMart SS2 in the top four. First reading: the lexical lane fires only
for the **fifteen hand-listed dishes** in `makanlah/dishes.py`, so every query outside that table falls to the vector
lane alone — which is why the Malay side is weakest. Not yet measured, and the measurement comes before the fix.

---

## 2026-08-29 — The Citation Trail Now Survives Being Checked

**#83 is closed on production, measured rather than inferred.** Same `肉骨茶` query, before and after loading liveness:
**6 of 8 cards led with a dead citation; now 0 of 6.** The set shrank because `宝香绑线肉骨茶` dropped out — its only
citation was dead, so it was a ranked entry nobody could check.

### The Prober That Did Not Work, And Why That Was Worth Finding

A plain-HTTP prober was written, tested, and **measured against five independently classified posts: 0 of 5 agreement,
everything `unknown`.** RedNote renders notes client-side; the served HTML is 460KB with no note content and no
missing-post text, and the first 4KB of `__INITIAL_STATE__` is **byte-identical** between a dead post and a live one.

It failed to `unknown`, never to `dead`, which is the only reason this was cheap. The measurement now comes from the UAT
session's Playwright harness, which already resolves every `post_url` as a byproduct — a better answer than a second
browser stack, and it came from the frontend session rather than from me.

**`ingest/load_liveness.py` writes only `live` and `dead`.** 39 rows in: 20 dead, 17 live, **2 `unknown` skipped**. That
rule earned itself immediately: `69904021` is 兴记肉骨茶's only surviving citation, was `unknown` because a security
challenge blocked confirmation, and loading it as dead would have stripped a real venue of its last evidence.

### Two Numbers That Should Frame Any Launch Decision

**54% of probed posts are dead** (20 of 37 classified), far worse than the 21% a smaller round-1 sample suggested. But
across 57 cards, **zero leave a user with nothing to check** — the dead posts cluster on a few venues and almost every
affected venue carries an unaffected Google Maps citation. The failure mode was "the link I clicked was dead", not "this
recommendation is unfalsifiable". The second number is the one that matters; the first says re-capture is more urgent
than it looked.

### The Session's One Recurring Failure, Now Five Instances

**A check that ran, reported success, and was measuring nothing.** Mascot asserted a live WebGL context — a blank canvas
has one. Theme asserted tokens exist — they existed, resolving to the wrong values. The ledger asserted a counter
increments — it did, in a container nobody would see again. `add_corroboration` passed ten unit tests and raised
`KeyError` on the first real response, because the fixtures agreed with the function rather than with the data. And a
numeric subtitle check for "dark pixels, near the bottom, centred" passed happily on type twice the size it should be.

**In every case the fix to the check was to assert a difference rather than a presence** — pixels against zero, light
against dark, before against after a cold start, live corpus against fixture, rendered frame against measurement.

### Two Findings That Were Wrong, Corrected By The People Who Made Them

The UAT session reported "Ask About This returns nothing". **I attributed it to a crashed renderer under memory pressure
and told the owner so. That was wrong.** They ruled it out with a crash listener that never fired and twelve polls
returning fresh DOM, and found their own bug: reading the panel by slicing _forward_ from `"Asking about"` when the
answer renders _above_ the form. I reached for the environmental explanation because one was available.

They also corrected "the corpus usually has live evidence, the card picks the dead one" — they had not probed the
alternatives, only read them off the payload. 阿喜 has **no** live RedNote citation at all, only Maps. That is a
materially different product from one where selection can always find something.

### Also Landed

**#87** — `corroboration: {posts, authors, platforms}` and `shared_with`. On live data it cuts both ways: `兴记肉骨茶`
has four authors on one platform and was being **refused**; `中南肉骨茶` has two posts by **one** author across two
platforms and was being **stamped**. **#59** — three of six Han-folded groups collapse, three are genuinely different
(`华阳` two `place_id`s **11,970m** apart; Oriental Kopi is a chain, so the comment in `text.py` calling them one
kopitiam was wrong and is corrected). **The video pipeline** — Kokoro `jf_nezumi`, chosen by measuring pitch **and**
intelligibility, where the highest-pitched voice was the least intelligible at 50% WER.

### Open

**#15** (1,008 truncated Google Maps posts) needs the signed-in browser. **#81** (a 500 loses its CORS headers, so the
browser reports a fault that does not exist). **#86** (no halal signal — a coverage decision, not a defect). A recurring
browser-driven probe over the ~1,468 unprobed posts. And the launch video, deliberately unrecorded: the UI is settled
but the recording waits on the UAT re-probe clearing its cooldown.

---

## 2026-08-29 (UAT Round One) — The Same Failure, Now Four Times

**Prod is at `4d1ef4f`.** PRs #74, #77, #89 merged. Peer 3 ran UAT as three personas; eight frontend findings fixed, one
rejected with evidence.

### The Pattern, Fourth Sighting

Every one of these was **a check that ran, reported success, and was measuring nothing** — and in every case the fix to
the check was to assert a **difference** rather than a **presence**.

| Bug                          | The check asserted     | Why it passed anyway                           | What the check asserts now       |
| ---------------------------- | ---------------------- | ---------------------------------------------- | -------------------------------- |
| **Mascot rendered nothing**  | A live WebGL context   | A blank canvas has one                         | Painted pixels against a floor   |
| **Dark theme entirely dead** | The tokens exist       | They did, resolving to the light values        | The colours move between schemes |
| **Spend ledger** (Peer 1)    | The counter increments | It did, in a container nobody would see again  | It survives a cold start         |
| **Drop The Craving**         | The label updates      | It did — the request still carried the craving | The claim and the request AGREE  |

A presence assertion agrees with itself. A difference assertion has to be shown two states and cannot.

### The Blocker That Was Not One

Peer 3 reported "Ask About This never renders an answer" as the launch blocker. **It renders.** Reproduced twice against
prod — logged out and as a guest signed in through the UI — answer and citations both painted; Peer 1 confirmed `/ask`
independently.

The symptom matched **a tab crash under memory pressure**, which the same report separately excluded as the reporter's
own machine. This box was at 631 MB free with swap 100% full and crashed three times. **A dead renderer emits no console
errors, and a completed POST that never paints is indistinguishable from being ignored.** Two findings, one cause, and
the cause was the environment.

The lesson survived the rejection: the Ask panel showed in-flight state only in a button label, so waiting and
finished-with-nothing looked identical. They are different claims and now look different. Measured on prod:
`.ask-waiting` at 0 ms, answer at ~900 ms.

### Two Bugs My Own Fixes Introduced

Both caught before shipping, both worth keeping:

**The new empty state claimed "within 3 km of you" from the radius control** — but `run()` drops the radius when
geolocation never resolved. That is #82 inverted: a false blame replaced by a false precision. Gated on the radius
actually sent.

**Drop The Craving cleared the label while still sending the craving.** `run()` reads its ref synchronously and React
had not re-rendered. This is the fourth row in the table above.

### Worktree Collisions: Three, Now Ended

The main checkout was shared with Peer 1 and moved under me twice. The third time was the worst — my files sat
uncommitted on their branch and **their in-progress code reported as 17 failures in my test run**, which costs judgement
rather than minutes. Peer 1 has relocated to `MakanLah-p1` with its own copy of the gitignored dotenv, which was the
whole reason they kept being pulled back. **Commit early when sharing a checkout, and check `git branch --show-current`
before trusting a test run.**

### Still Open

**#83 is half-done.** `prefer_live` selection is merged, but `dead_at` is filled by a prober that does not exist yet, so
every dead link Peer 3 measured is still dead on prod. **#87** needs `corroboration` and `shared_with` from the API; the
client renders them the moment they arrive and claims nothing without them. **#86** halal has no corpus signal. **#78**
the Cubism shader warning, non-fatal.

## 2026-08-29 (Round Three) — One Failure Pattern, Found Three Times In One Afternoon

**PR #71 merged** (mascot framing). **PR for the six-item batch open on `feat/round-three`.** Three peers now: Peer 1
backend/devops, this session frontend, Peer 3 UAT. Contract in issue #72. **Unattended mode is ON** — self-merge on
green CI is armed.

### The Pattern, Written Once Instead Of Three Times

Three separate bugs this session, all the same shape: **the check ran, reported success, and was measuring nothing.**

| Bug                            | What the check asserted        | Why it passed anyway                                |
| ------------------------------ | ------------------------------ | --------------------------------------------------- |
| **Mascot rendered nothing**    | A live WebGL context, not lost | A blank canvas has one                              |
| **Entire dark theme was dead** | The tokens exist               | They existed, resolving to the light values         |
| **Spend ledger** (Peer 1's)    | The counter increments         | It did — in a container nobody would ever see again |

**In all three the fix to the CHECK was to assert a DIFFERENCE rather than a PRESENCE.** Pixels against zero. Light
against dark. Before against after a cold start. A presence assertion agrees with itself; a difference assertion has to
be shown two states and cannot.

The mascot one is worth the detail: the model canvas is **4648×8000 units and the character's ink starts 34.3% down
it**. `scale: 0.3, anchorY: 0.08` framed units 536–2536, which is empty air above her head. Every asset returned 200,
`onReady` fired, the context was live, and **0% of the canvas had ink in it**. Measured by fitting the whole model into
a probe canvas and reading back alpha. Now 56.5%, asserted as a floor in CI.

The dark theme one shipped in this session and was caught within the hour: my own edit nested `:root` inside `:root`,
which is a descendant selector that never matches.

### Two More Found By Looking, Not By Testing

**Every landing section below the hero shipped blank.** The reveal CSS carried a comment reading "visible by default,
and that is the whole rule" directly above `opacity: 0.001` on the un-revealed state. The comment was right and the code
did the opposite. There is no hidden resting state now — the animation plays from an offset and stops mattering if the
observer never fires.

**Two horizontal overflows on a phone**, both from layout defaults rather than from anything written: the closed nav
drawer extended the document 74px past a 390px viewport (a `position: fixed` ancestor does not clip its children), and
the discover grid sized to `max-content` so a four-option distance control widened the whole page.

### What Shipped

Landing rewritten as marketing with a new Codex hero and live counters; `/discover` rebuilt around an empty full-width
search with corpus-derived chips; LiveroiD given a real job on both screens; auth stripped of chrome; footer
right-aligned; browser chrome replaced and theme-aware; a three-state theme switch.

**`GET /suggestions` lets a model choose but never write** — it returns indices into a corpus list, so it cannot name a
dish nobody wrote about. It shares the companion's free-tier request counter rather than the ringgit budget, because MYR
headroom would authorise a call the free tier has already refused.

**Verified against the live corpus**, not asserted: asked 阿喜 "is there usually a queue?" and got _"One reviewer noted
a 'big line' at 11:30am, while another reported no queue at 10am"_ with both Google Maps citations attached.

### State

99 web tests, 358 Python tests, four browser guards green (mascot pixels, chrome in both themes, motion in both engines,
layout 5/5). Overflow 0 at 360/390/834 on every route.

**A worktree collision nearly cost this batch.** The main checkout was on Peer 1's branch with all 29 of my files
uncommitted on it. Backed up, verified byte-for-byte, moved to `feat/round-three`, re-verified. **Commit early when
sharing a checkout.**

## 2026-08-29 (Later) — The Companion Speaks, And The Guard Nearly Stopped Guarding

**PR #70, four commits, on `feat/landing-solarsim`.** The five refinements from the owner's local-dev eyeball.

### The Landing Rebuild Took The Layout Guard's Only Host With It

`scripts/layout_check.py` measures `.evidence-pair` against a 34rem container query. The specimen plate on the landing
was **the only surface in the app that renders one with no API behind it**, which is why CI could run it at all.
Rebuilding the page around post cards removed the plate, and the guard reported **five `nothing was measured` failures**
rather than passing quietly — the precondition assertion added in #53 doing exactly the job it was added for.

The plate is back, beside the remaining cards under one heading, and the guard's cases are re-derived for the new
geometry. **The 1024px hole is gone**: it used to stack there "by design" because the hero split before the page reached
its cap, and the section is now full width until 76rem. Margins measured at all five widths: −236, +145, +335, +62, +62.

**42rem, not 40rem, is the floor on the plate's column.** A container query counts the content box, so 32px of padding
and a 1px border come off before the bar is measured: 38rem of column is 542px of content and fails silently, 40rem
clears by 30px which is one padding change from failing again.

### Four Things The Companion Taught, All Measured

| Found                                                                       | Fix                                                    |
| --------------------------------------------------------------------------- | ------------------------------------------------------ |
| At a 400ms beat the Gemini line lost the race **every time** in the browser | She speaks when the line lands; 1200ms is the ceiling  |
| `display: none` still pulled 500 KB of pixi and a WebGL context on a phone  | The stage is not mounted below 56rem. Her bubble stays |
| The Web Speech API exposes word boundaries, not amplitude or visemes        | The mouth is an oscillation, and the code says so      |
| Her tier is free, so MYR budget headroom could authorise a refused call     | Counted in requests: 400/day, 12/min, under 500 and 15 |

The first is the one worth carrying: **the lane was wired up, called, billed against quota and never heard.** Nothing
failed. The scripted fallback rendered, every test passed, and the only way to see it was to read the bubble text in a
real browser and notice it was never the model's.

**`POST /companion` is the one lane deliberately kept away from the citation trail**, and that is what makes it safe to
let a model write. No corpus row, no venue name, no `citations` key. `_safe()` drops any line that names a place,
recommends, rates, quotes a price or carries a URL, and falls back to the script.

### The Guest Disclosure Is Narrower Now, On Purpose

The heading and three paragraphs of consent copy are gone at the owner's instruction. **Somebody can now sign in as
guest without having been told the account is shared.** `docs/TRD.md` says so rather than still claiming the old
contract; the disclosure moved to in-session, where the nav reads `Guest, Shared` for the whole session.

### LiveroiD Is Committed

Gitignored as a BOOTH download under Live2D's licence, so **CI never had it and production shipped the text fallback
every time**. The owner took the call explicitly: personal project, their risk. Biome excludes it as a received source.

### State

**Not verified: audible sound.** Headless Chromium ships no TTS voices. The call path runs without error and picks a
voice correctly; nobody has heard her. That needs a real browser.

Green at the point of pushing: `bun run lint`, `tsc --noEmit`, **336 Python tests, 98 web tests**, `motion_check.mjs`
4/4 across Chromium and Firefox in both preference states, `layout_check.py` 5/5. 48 screenshots regenerated in
`docs/screenshots/`. Every new assertion was mutation-tested — the first version of "stays quiet until the voice is
switched on" passed against a companion that did speak, because advancing fake timers left the promise chain unflushed.

**Worktrees:** `wt-landing` holds this work. `wt-footer` and `wt-authguest` are spent and should be removed.
**Unattended mode is off.**

## 2026-08-29 — The API Is Live, And #6 Is Closed

**`https://makanlah-api.vercel.app`**, Vercel Hobby, region `sin1`. The client on Pages calls it: a real browser at
`makanlah-b5h.pages.dev` completes guest auth and `/recommend` and gets **3 results, the first with 3 citations across
both `google_maps` and `rednote`** — a corroboration pair in production. `/recommend` for `肉骨茶` returns 7 cited
results in **2.51s**. Before today the shipped bundle called `http://127.0.0.1:8000`, so the public site worked for
nobody.

### Render Was Not The Answer, And The Reason Matters

Its 750 free instance-hours are **per workspace per calendar month**, not per service. `kawan-backend`,
`cukaipandai-api` and `layak-backend` had already consumed them, so Render had suspended all three; `catatmd-api`
survived only because it is on paid Starter. Adding MakanLah as a fourth free service means any one of them can suspend
the other three, which is the wrong property for a launch week.

**The keep-warm ping this file previously floated would have made it worse, not better.** One always-on free service is
744 hours — the entire pool. Do not add one.

### Two Options In The Research Doc Are Now Dead

`docs/superpowers/research/2026-08-28-free-public-deployment.md` was built on secondary sources and two of its six
options no longer exist as described. **Cloudflare Python Workers ships no PostgreSQL driver at all** — not `psycopg`,
not `psycopg2`, not `asyncpg` — so option 1 was a rewrite of `db.py`, not a deploy. **Hugging Face Docker Spaces are no
longer free** and block every outbound port except 80, 443 and 8080, which excludes Postgres on 5432 regardless.
**Koyeb's free compute tier no longer exists.** Check the vendor page, not a listicle.

Vercel Hobby is **single-region but you choose the region**, which is the property that made it work: `sin1` sits beside
Neon in `ap-southeast-1` and the model API in Singapore. The `iad1` default would have added a transpacific round trip
to every query and nothing would have looked broken. The owner read the Hobby terms — _"non-commercial, personal use
only"_ — and accepted them for this project.

### The Deploy Looked Correct For The Wrong Reason

The first deploy uploaded **25.4MB**, the whole repo, **including `.env`**. `config.py` calls `load_dotenv()` against
the repo root, so the bundled file silently satisfied every credential: `/health` reported `database: true` while
nothing was configured in Vercel at all.

It was never reachable — the catch-all route hands every path to FastAPI, and four probes returned 404 — and that
deployment has been deleted, with the five values moved into Vercel's encrypted store. **`/health` could not have caught
this, because it passes either way.** What caught it was listing the bundle's files: 125 files, no `.env`, and `/health`
still answering 200 with 1,507 posts.

**This is the recurring shape again, in a new place**: an absent configuration and a correct one were indistinguishable
from outside until something asserted which one was there.

### Open

**#59** — six venue groups the Han fold collides that `normalize()` cannot see. **#15** — 1,008 truncated Google Maps
posts, which needs the signed-in browser and stays orchestrator-only.

---

## 2026-08-29 — The Frontend Session: A Mark, And Motion That Survives Reduced Motion

Contributed by the frontend session; wording is theirs, merged here because `docs/PROGRESS.md` is one file and two
sessions must not both hold it open. Prod is at `94e9f02`, matching `main`; #56, #62 and #64 merged.

Reduced motion no longer means no motion. Windows "Animation effects" off and macOS Reduce motion both land on
`prefers-reduced-motion`, and the old rules set `animation: none` with 1ms transitions, which removed every cue rather
than the harmful ones. Movement goes, fading stays: entrances swap to the fade keyframes and control feedback keeps its
full 120ms. Guarded in CI by `motion_check.mjs` across Chromium and Gecko, both preference states, mutation-tested.

MakanLah has a mark. A hanko chop reading "lah" in seal script, 300 bytes of SVG, used as both the logo and an
attestation stamp on results carrying two independent platforms. The ground is shippou, a motif shared by Japanese komon
and Peranakan tile. Cinnabar joins enamel green as a second accent with a separate meaning: green marks where evidence
came from, cinnabar marks that it is attested. Live on prod at `94e9f02`; `docs/screenshots/` refreshed from the live
site across all three devices.

**The seal is driven by `evidenceOf()`, the same function behind the pair layout and the mascot**, so the three cannot
disagree about what counts as corroborated. That is the citation trail expressed as a visual rule rather than restated
as one.

### Two Notes From That Session Worth Carrying

**The layout guard caught a real regression on its first change.** The redesign touched hero, specimen and results, and
`layout_check.py` confirmed the corroboration pair still splits at 1280+ with the margin unchanged at **+3.34px**.

**Three bugs, all found by measuring rather than looking.** Two logo drafts spelled `Ldh` and `loh` — a full-height stem
is what makes a `d`, and a squared ring is indistinguishable from an `o`. Then a rotated stamp pushed the document 10px
past the viewport. The plausible cause was the stamp; its right edge measured **345 against a 375 viewport**, so it
could not have been. Querying every element for `right > clientWidth` named the real offender. **Reason from the
measurement, not from the plausible cause** — the same lesson the wrong-worktree runs taught on this side.

---

## 2026-08-29 — Two Workers, Three Merges, And The Real Launch Blocker Named

**Prod serves `main`** (`/build.json` = `420e893`), and **#46 is closed**. Four PRs merged today: #57, #58, #61, plus
the peer's #56 and #62. Suite is **300 passing** on `main`.

### The Launch Blocker Is Not What The Backlog Said

The deployed client calls `http://127.0.0.1:8000` — its build-time default — so **the public site works for nobody but
the machine that built it**. The bundle also still carries a literal `https://your-api` placeholder. Deploying the API
(#6) is therefore not a nice-to-have before the launch post; it is the post's precondition.

**Cloudflare Python Workers is dead as an option, and this is now verified rather than assumed.** The Workers Python
runtime ships **no PostgreSQL driver at all** — not `psycopg`, not `psycopg2`, not `asyncpg` — and documents only
`aiohttp`, `httpx` and the JS `fetch()` FFI. `db.py` is `psycopg` throughout, so that path is a rewrite of the data
layer onto Neon's HTTP SQL endpoint, across every query on the citation path.
`docs/superpowers/research/2026-08-28-free-public-deployment.md` is corrected in place rather than left recommending
something that cannot work.

**Render Singapore is blueprinted and its build path is verified**, not sketched: a clean 3.11 venv installs
`requirements.txt`, imports every runtime dependency, loads `api.main:app` with `/health` `/recommend` `/ask`, and folds
a real venue name. That check caught `pip install .` failing — `pyproject.toml` declares no build backend — which would
have broken Render's first build.

**What is left on #6 is not mine to do:** a Render account and three pasted secrets (`DATABASE_URL`,
`DASHSCOPE_API_KEY`, `CF_PAGES_PROJECT`). Creating accounts and typing credentials are outside the authorization.

### Workers Are Working, With Caveats Worth Carrying

Both lanes the owner asked for exist and both produced merged code:

| Lane     | Model                                   | Outcome                                |
| -------- | --------------------------------------- | -------------------------------------- |
| Devin    | `swe-1-7` (SWE-1.7 Max, 262K, **Free**) | #31 — fold + disambiguation, 290 green |
| OpenCode | `openrouter/z-ai/glm-5.3-flash`         | #41 — shared embed deadline, 270 green |

**Three things cost time and will again.** Devin's `--permission-mode` rejects tool calls in `accept-edits` and `smart`
is not on this account, so the only working non-interactive mode is `dangerous`; it is run in a **clone with no git
remote** so it physically cannot push. Workspace trust is a separate gate —
`/home/user/.local/share/devin/cli/trusted_workspaces.json` needs the path added. And a worker told to lint `makanlah/`
will not lint the test file, which is how #57 went red on two ruff errors **in the spec I wrote**, not in the worker's
code.

**Neither worker was merged on its self-report.** Both spec files came back byte-identical, and each got a hidden check
it never saw. #41's proved the deadline is genuinely shared in wall-clock — four batches against a 2.0s budget gave
timeouts of 2.0 → 1.1 → 0.2 and gave up at 2.00s — where the committed test only proved the numbers decrease. #31's ran
the fold across the live corpus to catch over-merging.

### #41 Was A One-Line Omission, Not A Mystery

`embed()` passed no timeout and inherited `_post`'s **120s default**, while `rerank()` beside it has always bounded
itself with `RERANK_TIMEOUT`. That matches the observed maxima — **131.88s and 122.14s** against a p95 of 2.7–3.1s —
almost exactly. Both production callers pass a single batch, so the shared budget never spans batches and ingestion is
untouched.

### What The Hidden Check Found: #59

The fold made a data problem visible that `normalize()` cannot see: **`normalize()` finds 0 colliding venue groups
across 256 venues; `fold_variants()` finds 6, covering 13.** Several are not branches — `八大八小 The Eight` and
`八大八小` are **both in Bukit Jalil**, and `华阳冰室` / `华阳 Oriental Kopi` is the exact pair `text.py` already
carries a comment about. The `兴记肉骨茶` group has **three** rows, not the two #31 documented. Filed as #59; each group
needs checking against `place_id` before anything merges, and the evidence-based merge rule must not be loosened.

### The Drift Guard Paid For Itself Within The Hour

`tests/test_deploy_manifest.py` asserts `requirements.txt` and `pyproject.toml` agree. It fired for real on the rebase:
#31 landed `opencc` as a **request-path** dependency and `requirements.txt` did not have it. Render would have built
green and raised `ModuleNotFoundError` on every `/recommend` — a failure visible only in production, under traffic.
`pyyaml` is a dev dependency so the blueprint checks cannot silently skip; a skipped check and a passing one are
identical in a CI log.

### Open

**#6** needs the owner: a Render account, then `DATABASE_URL`, `DASHSCOPE_API_KEY` and `CF_PAGES_PROJECT` pasted into
its dashboard, then `VITE_API_BASE_URL` set on Pages and a rebuild. **#15** (1,008 truncated Google Maps posts) needs
the signed-in browser and is orchestrator-only. **#59** needs a review pass over six venue groups.

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

**Open issues: #46** deployed site behind main · **#41** latency tail under burst · **#31** two branches read as a
duplicate · **#15** 1,008 posts missing text · **#6** deploy. #16, #20, #22, #25, #26, #34 and #36 all closed.

**#6 is not a technical blocker.** `wrangler` is installed and already authenticated to the account hosting the Pages
site. It stops on a **platform-terms question**, which `AUTONOMY.md` names as one of the four things that end a run:
deploying means serving cached third-party excerpts publicly, and putting a live Neon credential into Cloudflare. Both
are the owner's call. **This also blocks the LinkedIn post** — the demo points at `127.0.0.1:8000`, so a reader who
clicks through today reaches a client with no backend.

## The Deploy Gap, And The Exhibit That Went Stale

_Written by the frontend session, kept verbatim._

> The staleness probe closes the gap that a skipped deploy left open. `guard-merge.sh` counts SKIPPED alongside SUCCESS,
> so an unset or rotated Cloudflare token made "did not deploy" indistinguishable from a green review. The build now
> stamps `dist/build.json` with its commit and a daily scheduled job reads it back, files one issue edited in place, and
> closes it when the live site catches up. It never runs on `pull_request` and so cannot reach the merge gate. First run
> red and correct: issue #46. It stays red until `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` exist.
>
> The landing exhibit was re-frozen against the corpus after #40, #42 and #27. Both cited posts survived the repair —
> the response went stale because chrome-stripping changed an excerpt and #27 changed which citation leads. A live URL
> is not a live exhibit, and the check for one would have passed.

## A Documented Contract Nothing Compared To The Code

`TRD.md` described `match: {basis, dish_hit, lexical, vector}` while `/recommend` sent `{basis, dish, similarity}`. The
web client's type was written **faithfully against the doc**, so the client was wrong about the response for as long as
nothing read those fields — invisibly, until a real response met the type and `tsc` rejected it.

**The drift was in the documentation, not the client.** `tests/test_api_contract.py` now parses that block and compares
it against the response shape, with a second test pinning the parsed key set — because a comparison against an empty
parse succeeds, which is the same hole as an absent check reading as a pass.

## Three Findings Worth Carrying Forward

**The re-rank lane had no free quota and nobody could see it.** `qwen3.8-flash` reads `Not Supported` in the ModelStudio
console: every `/recommend` and every `/ask` was billed from token one. Free-quota state is not readable from the API
key, so nothing in the repo could say so — which is why `scripts/quota.py` now exists. Re-pinning to
`qwen3.7-flash-2026-07-15` (dated, 1M free, expires 2026-10-22) took **p95 4.36s → 2.89s, meeting the 3s target in
[`PRD.md`](PRD.md) for the first time**, raised p@5 0.982 → 0.992, and costs 4.6× less. **The lane was the budget**; the
`max_tokens` tuning tried earlier was always going to be wasted effort.

**The invariant asked the wrong question.** Every excerpt check asked _was this written?_ and never _does this say
anything?_, so a postal address passed as testimony 82 times in 243 venues. The sharpest case: `repair_excerpt`, the
guard against fabricated quotes, anchored its repair on the venue name — and on a RedNote listicle that line **is** the
pin line, so the fabrication guard was reinserting addresses precisely where the model had done best.

**Spend is bounded in ringgit, with a share per visitor.** A global budget alone is a bigger bucket for one attacker to
drain: they take the day and every real visitor sees a degraded app. `IP_DAILY_SHARE` means a troll burns a tenth and
everyone else is unaffected.

## The Citation Quality Pass, 2026-08-28 Evening

Found by re-recording the demo. The corroboration pair #24 had just fixed put its first frame on camera, and the frame
cited **a postal address against that venue's single most negative review**. Three PRs, each measured:

| PR      | What                                                | Effect                                                  |
| ------- | --------------------------------------------------- | ------------------------------------------------------- |
| **#27** | Citations no longer ordered by `mention.confidence` | venues leading with an address **82 → 28** of 243       |
| **#29** | Pin line stripped where testimony sits under it     | RedNote address-shaped **103 → 73**, leads **28 → 18**  |
| **#30** | Extractor asks for the opinion, not the location    | new captures only, **6 better / 0 worse** on 15 sampled |

**Confidence was an anti-signal.** It measures how easy the text was to extract, which is close to the opposite of
whether it is worth reading: the ≥0.95 band averages **75 characters against 180**, and is nearly twice as likely to
carry no opinion at all. An address is trivially extractable, so it won every time.

**The problem was one platform.** RedNote excerpts average **55.9 characters against Google Maps' 196.8**, and **103 of
317 are address-shaped against 5 of 1388**. That is the differentiating source — Google Maps reviews are a commodity —
so the weak column was the one carrying the product's actual claim.

**It cost ranking a little, deliberately.** Full eval: **p@5 0.984 → 0.982, p95 4.66s → 4.36s, top1 51/51 → 49/51**. The
entire top1 loss is `matcha`. Pin lines name the venue and its dish, so ranking had been leaning on text the reader
should never have seen (**#26**).

**A language bias caught by its own test.** The "is there testimony left" threshold was a plain `len()`, and 30 CJK
characters is a paragraph where 30 Latin characters is half a sentence. Weighting CJK double raised the repair count
**22 → 30**, all eight recovered being Chinese testimony a character count was discarding.

### #25 Is Closed

The replay ran on 38 posts from the raw cache — no platform touched, 2% of the extraction lane's free quota.

|                                  | before      | after        |
| -------------------------------- | ----------- | ------------ |
| RedNote address-shaped excerpts  | 103 (32.5%) | **2 (0.8%)** |
| Google Maps address-shaped       | 5 (0.4%)    | 5 (0.4%)     |
| Venues leading with an address   | 82 (33.7%)  | **3 (1.2%)** |
| Two-source pairs with an address | 48/175      | **4/134**    |

**52 mentions and 9 venues were dropped for having nothing to say**, which is the policy rather than a fault: they land
in the `uncited_venue` view, unrankable rather than deleted. Ranking held at **p@5 0.976, top1 50/51**.

**`truth.json` is one step behind the corpus on purpose.** Two venues it labels correct are now unrankable because their
only excerpts were pin lines. Regenerating it with `build_truth.py` needs its own baseline run — the obvious next
housekeeping task.

### The Old Next Step, Kept For Its Reasoning

A replay over `ingest/pipeline.py` would fix most of the remaining 71. It reads the raw cache and touches no platform.
**It is gated on two things, both measured rather than guessed:**

1. **4 of 15 re-extract to an empty excerpt.** Honest — those posts give a name and a location and no verdict — but an
   uncitable mention is dropped by the one invariant, so a replay would _shrink_ the corpus. Whether a venue with no
   testimony should be recommendable is a product call
2. **`repair_excerpt` puts the address back.** Its fallback windows on the **venue name**, which is what a pin line is
   made of, so it undoes #30 exactly where the model did best. **Do this one first** or the replay's ceiling is lower
   than it looks

## The Demo Video

`scripts/demo/` records, narrates and muxes it — Playwright, Piper, ffmpeg, all local and free.
**`makanlah-demo-v2.mp4`, 55.4s, 1920×1080, 2.4 MB**, sitting beside the repo rather than in it (`.mp4` is gitignored).

Narration keys to beats `record.mjs` **measures** and writes to `beats.json`, not to hand-tuned offsets that drift the
moment a page gets slower. `record.mjs` also **asserts the corroboration pair is on screen** and prints the count, so a
run that re-records the #20 bug says so instead of looking fine.

**What it still cannot show:** `/ask` is API-only, so the strongest moment in the product — the copilot answering
`covered: false` — is unfilmable. And the RedNote column of the corroboration pair is still a pin line (**#25**), which
ordering cannot fix because the corpus holds nothing better for that venue.
