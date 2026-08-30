# Progress — 2026-08-30 · the repo was made publishable, and a merged fix turned out never to have shipped

**`main` is at `cff13c2`. API `/health` reports `cff13c2b`.** They agree for the first time today, and getting them to
agree is the whole story of this session's second half.

**The repository is ready to be read by strangers, except for one licence question.** #192 landed the public
`docs/README.md`, `docs/runbook.md`, a corrected `docs/TRD.md`, an MIT `LICENSE` and an archived history. Description,
15 topics and homepage are set on the repo. **[#195](https://github.com/TolongLabs/MakanLah/issues/195) is the only
thing between here and public**, and it is an owner decision, not a technical one.

## The Fix That Was Merged And Not Live

@makanlah-9e found `pork` still in the production chip rail hours after #190 merged, and was right to stop before
putting it in a public README rather than after.

|                              |                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------- |
| **What #190 did**            | Removed `pork` from the unprompted default chip pool                            |
| **Merged as**                | `7c5e892`                                                                       |
| **What the API was serving** | `08b5aeb` — the commit immediately before it                                    |
| **Why nobody noticed**       | The merge was green, the PR closed, and nothing reports the gap between the two |

This is **[#116](https://github.com/TolongLabs/MakanLah/issues/116) for the second time today**, and this time the diff
genuinely did touch a deployed path. The header block above exists because of the first time.

**Now: `/suggestions` returns `['soup','rice','chicken','curry','BKT','fish']` on three consecutive calls.**

### The Half That Would Have Looked Like Success

"No pork chip" is satisfied just as well by having broken pork retrieval entirely, so that is the half worth testing.
`POST /recommend` with `bak kut teh` returns 5 results, `degraded:false`, every one cited — Kepong Ba Kut Teh
(3), 興记肉骨茶 (5), 旧巷子肉骨茶Authentic Klang Bak Kut Teh (3). **Unoffered, not unreachable**, which is what #190 was
for.

@makanlah-a6 then confirmed the retrieval battery carries over unchanged, by diff before probe: between `08b5aeb` and
`cff13c2b` the only request-path Python change is `makanlah/suggest.py`, and `suggest` is referenced exactly once in the
API, at `api/main.py:563`, inside the `/suggestions` handler. Nothing on the `/recommend` path imports it. **Reachable
~250, slots ~325, rate 30% stand.**

## Two Traps Found In The Deploy Path

**`vercel deploy` failed with `Not authorized` while `vercel whoami` succeeded.** The link in `.vercel/project.json` was
stale. Relinking fixed it, and `projectId` was unchanged before and after — `prj_0PQ1bU2Vz1h4shbF0aHID8FwiMBt` — which
is how the relink is known to have hit the same project rather than a lookalike.

**`vercel link` appends `.env*` to the tracked `.gitignore`.** Line 25 already carries `.env.*`, so the addition is
redundant, and it leaves the tree dirty — which `scripts/deploy-api.sh` then correctly refuses to deploy from. Revert it
after any relink.

## makanlah.pages.dev Is Not Ours

It returns 200 and serves a third-party APK page in Malay, titled _"777RT APK Versi Terbaru…"_. **Ours is
`makanlah-b5h.pages.dev` and only that.** Never write the short form in a README, a deck, or the launch post — a reader
who guesses it lands on someone else's site.

## Branches: 10 → 4

Six deleted. Four had merged PRs; the other two were checked against **main's own content** rather than their PR state,
because a squash merge leaves a branch reading `unmerged` when its work has fully landed:

| Branch                         | Why It Was Safe                                                                           |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| `docs/correct-huayang-comment` | The ledger isolation is in main as `_never_touch_the_real_ledger`, `tests/conftest.py:21` |
| `feat/gmaps-discovery-wip`     | Main's `ingest/gmaps.py` is a strict superset — it adds only `discover`, main has seven   |

**`feat/render-blueprint` was kept deliberately.** Its content is genuinely not in main, and given how often #116
resurfaces, an already-written Render blueprint is worth more than a tidy branch list. Remaining alongside it:
`docs/checkpoint-2` (#165) and `docs/readme-screenshots` (#194).

## Open, And Who Owns It

| Item                        | Owner        | Note                                                                                        |
| --------------------------- | ------------ | ------------------------------------------------------------------------------------------- |
| **#195 Live2D licence**     | Owner        | Blocks going public. Four options costed in the issue; option 4 first, it may moot the rest |
| **#194 README screenshots** | @makanlah-9e | Needs a rebase onto `cff13c2` — the branch predates the README rewrite — and a re-shoot     |
| Demo video, pitch deck      | @makanlah-9e | #187 narration drift still open                                                             |
| #179, #177, #189, #193      | —            | Deferred, not blocking launch                                                               |

**The chip row is time-banded.** @makanlah-a6 caught this: a frame shot in one MYT window will not match one shot in
another, so `/suggestions` has to be checked in the same minute as the screenshot rather than assumed from an earlier
call. My own call came back `band: "late night supper"`.

**Web client is live:** <https://makanlah-b5h.pages.dev> · **API is live:** <https://makanlah-api.vercel.app>

---

## 2026-08-30 (Earlier) — The coverage ceiling came off, and the browser stopped being the way in

**`main` is at `977caf6`. API `/health` reports `977caf6`, client `build.json` reports `3c99b62`.** The client is
correctly behind by one commit: `3c99b62` is the copilot voice change, which touches `makanlah/` only and is not in the
client bundle. **A differing sha is not drift — the question is whether the diff touches a deployed path** (#116). **644
Python tests, lint and format clean.**

**The corpus tripled, and then had to be made reachable.** Those are two different jobs and only the first is scraping.

|                         | Start of day | Now       |
| ----------------------- | ------------ | --------- |
| Venues                  | 256          | **823**   |
| With evidence (citable) | 247          | **814**   |
| Carrying a price        | 45           | **627**   |
| Posts                   | 1,507        | **4,523** |
| Mentions                | 1,653        | **4,764** |
| Distinct authors        | 118          | **2,190** |

**Reachable through real queries is the number that matters, and it is not that one.** @makanlah-92's 46-query battery
read **114 → 142** before the candidate ceiling was raised, while citable grew 229%. Reachable-as-a-share-of-citable
_fell_ from 46% to 17%. That gap was the whole evening's second act: coverage was solved and retrieval was not.

**Price went 0% user-visible to 78%**, measured on the client by the session that filed it, not by the one that fixed
it. 75 of 95 results and 56 of 72 distinct venues carry a band, rendered as words rather than `$` symbols.

**Web client is live:** <https://makanlah-b5h.pages.dev> · **API is live:** <https://makanlah-api.vercel.app>

---

## 2026-08-30 — Owner's Frontend Batch: Glass, One Row, And Two Checks That Agreed With Themselves

**Eleven owner requests, all shipped on `feat/discover-glass-cards` (PR #185).** Glass result cards on `/discover`, a
chip rail that holds one row, the sidebar's duplicate CTA and theme switcher removed with Sign Out moved under the
email, a glass footer sitewide, an opacity sweep, the filter caption folded into a hover tooltip, Codex-generated motifs
on the three `/dashboard` cards, a scrim that dims and blurs the page behind the open sidebar, and a social embed
poster.

### Glassmorphism Is An Owner Override, Recorded As One

`docs/DESIGN.md` lists glassmorphism-with-no-reason-for-depth as a tell. The owner was told and answered **"Override for
my request."** It ships, and `DESIGN.md` now carries the override with its qualifiers rather than quietly contradicting
itself. **A standing design rule that gets silently broken is worse than one that records its exceptions.**

### The Three Checks That Passed By Agreeing With Themselves

All three are the failure this repo keeps meeting, and none was caught by reading code.

| Check                 | Reported               | Actually                                                       |
| --------------------- | ---------------------- | -------------------------------------------------------------- |
| One-row chip rail     | Fixed                  | Never hid a chip at any width                                  |
| `narrate.sh` tail pad | `tail-pad 2.9s`        | Computed the pad, then discarded it on the next line           |
| `bun run typecheck`   | `nothing to typecheck` | Tested `[ -d src ]` from a root where the source is `web/src/` |

**The chip rail hid nothing.** `el.hidden = true` was the entire mechanism and `.chip-button { display: inline-flex }`
beats the UA sheet's `[hidden]`, so the attribute was set on every overflowing chip and every one kept rendering. It
wrapped to two rows at 320–540px and read as correct only at ≥1024px, **where all six chips fit unaided and nothing
needed hiding**. The verification had been run at the one width where the mechanism was never exercised. Measured after
`.chip-button[hidden] { display: none }`: **3 chips at 320px, 4 at 430, 5 at 540, 6 at 1024 and up, one row at all nine
widths tested.**

**`bun run typecheck` could not fail.** It tested `[ -d src ]` from the repo root, where `src/` does not exist — the
source is `web/src/`. So it printed "nothing to typecheck" and exited 0 on every run since the client was created,
including the run immediately before CI rejected this branch on `error TS2532`. **The command AGENTS.md documents as the
typecheck was a no-op the whole time.** It now runs `tsc --noEmit` from `web/`, where the `vite/client` and
`vitest/globals` type packages actually live — pointing it at `web/tsconfig.json` from the root was not enough and
failed on CI's clean install with TS2688 while passing here. Exit codes checked both ways: **0 clean, 2 with the
narrowing guard removed.**

**`narrate.sh` promised in a comment what an unconditional `tpad=""` threw away**, so the closing line played 2.5s over
no picture. **ffprobe reports the two stream durations separately and never calls a mismatch an error**, so every mux
"worked". Video was 163.08s against 165.62s of audio; it is now 166.04s, and the frame at 165.4s renders the close slide
with the whole final subtitle.

### The Walkthrough Video Is Sound, And Its Narration Drifts — #187

166.04s video against 165.62s audio, mean volume −20.9 dB, no silence gap over 6s, real content in every sampled frame.
**But 2 of 19 narration lines are spoken while a different beat is on screen**, and 15 of 19 are pushed later than
intended, drift peaking at **10.7s**.

`schedule.py` pushes any line that would still be speaking when the next starts, and the pushes cascade. It begins at
line 0: `record.mjs` marks `landing`, waits 1400ms, marks `compare` — and the landing line takes **6549ms** to read,
injecting 5.2s before anything else happens. **The total is not the problem, the distribution is:** `taste` has 9.4s of
slack and `market` 9.6s.

Filed rather than fixed here. It needs a fresh capture against prod and a re-verification of all 19 lines, not a text
edit, and **no narration text needs to change** so no measured figure is at risk.

### The Link Preview Was Broken And Looked Fine

`og:image` was the relative `/og.png`. **Facebook, LinkedIn, X and Slack fetch it from their own servers with no page
context**, so it resolved against their host and 404'd — the link rendered as bare text with nothing reporting a
failure. The file itself served 200 the whole time; the tag pointing at it was the defect. Now absolute, plus `og:url`,
`og:site_name`, `og:image:alt` and three `twitter:*` tags.

The poster is Codex Images 2.0 art composited under real type at exactly 1200×630. **The art was generated textless on
purpose**: generated lettering is subtly wrong and a wordmark is the one thing on a link preview that cannot be.

### Workers: One Lane Silently Did Nothing

OpenCode (GLM-5.3-Flash) and Devin (SWE-1.7 Max, Free tier — no money spent) were fanned out, split by file to avoid
collisions. **GLM-5.3-Flash works**, contradicting an earlier peer finding that it returns empty completions.

**Devin exited 0 having done nothing**, because `--mode` is not a valid flag —
`error: unexpected argument '--mode' found`. Correct invocation is `--permission-mode accept-edits`. This is exactly the
self-report failure `SWARM.md` warns about: **the exit code was clean and the work was absent.** Neither worker was
merged on its self-report; each diff was read and the hidden `opaque-check.mjs` run against it.

### `scripts/opaque-check.mjs` Is New, And Mutation-Tested

Reads **computed** styles from a real browser across 3 routes × 2 themes rather than grepping CSS, because a rule can be
overridden, inherited or beaten on specificity and none of that shows in source. Fails any element with `0 < alpha < 1`
and no `backdrop-filter` or `background-image`. **110 controls and surfaces, all solid or glass.**

### Gate State, And What Is Left On #141

Measured at 320–1600px: **no horizontal document scroll on any of the four routes** (`scrollWidth == clientWidth`), and
**53 rendered labels all TitleCase** — the only flags were corpus venue names, which are data rather than chrome.

**`impeccable critique` was not run: there is no `impeccable` binary on this machine.** The skill is vendored, the CLI
is not installed. Recorded rather than claimed.

**Left open on #141 deliberately:** the distance segment wraps to two rows inside one pill below ~560px, leaving a large
asymmetric grey void. Pre-existing, unrelated to what PR #185 was asked to change, and commented on the issue with the
measurement rather than folded into an already-large green PR.

**Also gitignored `scratchpad/`.** Untracked but unignored, it turned `bun run lint` red through the `**/*.md` glob
while CI stayed green on its clean checkout — **a gate that failed only on the machine doing the work.**

## 2026-08-30 (Evening) — Google Maps Became A Source, And Four Ceilings Came Off

### The Browser Is No Longer The Ingestion Path

Owner directed the switch after CDP enrichment spent an afternoon on 52 venues. `ingest/places_api.py` and
`ingest/enrich_places.py` replace it. Measured on the same venues:

|              | CDP over Chrome                             | Places API          |
| ------------ | ------------------------------------------- | ------------------- |
| Per venue    | ~25s                                        | **~1s**             |
| Review text  | 1,008 of 1,388 cut off at Google's "… More" | **whole**           |
| Price        | parsed from prose, 3% of mentions           | `priceRange` in MYR |
| Failure mode | Chrome died and the loop kept going         | an HTTP status      |

**500 venues in 9 minutes. Cost MYR 0.00** — 998 calls against free monthly allowances of 1,000 Place Details Enterprise
and 5,000 Text Search Pro. Google replaced the $200 monthly credit with per-SKU free calls on 2025-03-01. Field masks
are narrow on purpose: `reviews`, `priceLevel`, `priceRange` and `rating` are Enterprise, and adding one unneeded field
to a search mask would cut the discovery allowance fivefold.

**`place_id` in this corpus is not a Places API place ID.** It is the `!1s0x...:0x...` pair lifted from a Maps URL — a
CID. 809 of 821 stored ids are that shape, and trusting the column sent one 400 per venue, **505 in a single run**
before it was stopped. `is_api_place_id` refuses anything `0x`-prefixed. Sharper than it sounds: the 5-venue test passed
_before_ this bug existed, because `pending_venues` did not return `place_id` at all. **Adding it as an optimisation is
what broke the run.**

### Four Ceilings, Each Invisible Until The Corpus Outgrew It

Every one of these was correct for a 250-venue corpus and wrong for an 823-venue one. None was caught by a unit test,
because each test builds its own inputs and never meets the real distribution.

1. **Embeddings.** 571 of 814 citable venues had none, so retrieval could not see them. `nasi lemak` went from 8 results
   to **1**. Fixed by running `embed_pending()`; 571 embedded in under a minute.
2. **The re-rank input.** `models.rerank` reads only the first 16 candidates, and the lexical lane was built by
   iterating a dict. `nasi lemak` matched 192 venues and an arbitrary 16 reached the model. Ordering by candidate order
   alone made it _worse_ — 3 results, all vegetarian caterers whose reviews merely said the words. Now ordered by how
   often a venue's own posts name the dish, with distance as the tie-break.
3. **The candidate ceiling.** `filter_candidates` returned the 400 nearest. At 400 the vocabulary is 624 terms and
   `steamboat` does not match; at the full 740 in range it is 806 and it does. `steamboat` returned 2 in the afternoon
   and **0** in the evening because 400 newer venues sat between the user and it. Now 2000. **This is the answer to
   citable +229% against reachable +25%.**
4. **The copilot's inputs.** It refused every price question while 627 venues carried a band, because `_shape` fed it
   only excerpt prose.

### Decisions Recorded

**Price has two provenances and they are not interchangeable.** A band parsed from a post's own words is evidence and
cites that post; a band from Google's `priceRange` is a third party's figure carried without a citation (#179). The
copilot may state the second and may not cite it. Conflating them would have it say "a reviewer said RM20" about a
figure no reviewer wrote.

**Only 257 of 315 parsed price figures were written.** 240 state an explicit RM range and 17 carry a per-person marker;
the other 58 are a bare figure in prose and stay null. One reads _"on the pricey side (a mangorange drink costs around
RM12)"_ and parsed to band 1, the cheapest, on a venue the writer had just called expensive. Found by eyeballing twelve
real rows, not by re-reading the parser.

**Pork leaves the default suggestion chips and stays fully searchable.** This is a **neutral-defaults** decision, not a
halal safeguard — @makanlah-92 measured that the `soup` chip still returns three bak kut teh houses one tap in, so
calling it a safeguard would overclaim exactly where `rank.py` says overclaiming is unforgivable. **No hand-written
non-halal dish list**: a list that catches `pork` but misses `siu yuk`, `char siew`, `babi` or `肉骨茶` looks like a
safeguard and is not. The version that satisfies the principle is a wizard question, filed rather than built.

**The copilot is LiveroiD**, the character `companion.py` already voiced. The persona sits UNDER the honesty rules and
the prompt says so explicitly, because a model reads a personality as permission unless told otherwise. Six tests pin
that the rules, the 40-word cap and the refusal wording survive any later tone edit. Description did not land the voice
and temperature did nothing at 0.1 vs 0.45; **three worked examples did**.

### What A Killed Run Leaves Behind

`source_status` is `distinct on (platform) order by started_at desc`, and `start_run` inserts with `ok = null`. So a
`kill -9` leaves an open row forever and every request reads "the last Google Maps refresh did not finish" — two apology
panels above the first result. It does **not** latch on failure; it reflects the latest run. **The rule: the last ingest
run of a session must be allowed to finish.** Confirmed false on prod after the final run completed.

### Instrument Failures, Fourth And Fifth Of The Day

**A check that did not vary what it claimed to vary.** The first candidate-ceiling comparison mutated
`db.CANDIDATE_CEILING` after import and reported 52 results against 71. Python binds default arguments at definition
time, so **both runs used 2000** and the entire difference was re-rank nondeterminism. Caught only because the gap was
too large for a ceiling change and too consistent with the ±3 noise floor @makanlah-92 had warned about.

**A run that looked like work and was not.** Three concurrent CDP shards killed Chrome 18 venues into a 183-venue shard;
the loop then walked 28 more batches against a dead socket, printing `Connection refused` each time, and reported a
completed stats dict at the end. A failed batch is a normal outcome; a dead browser is the end of the run, and the two
shared a handler.

### Open, Deliberately

- **#179** — a cited `RM 20` is evidence in a way a Google band structurally is not. Bands are the stopgap
- **#177** — the dish vocabulary carries non-dishes (`Spicy` 38 rows, `Classic`, `Breakfast` 45). Review tagging
  amplifies a pre-existing problem. Option 3 in the issue (require N distinct venues) is probably right
- **`/ask/stream`** — SSE with visible tool calls, owner-requested. Unbuilt, not merely undeployed. The one-shot `/ask`
  fallback is verified end to end on prod
- **Restaurant photos** — the Places API returns 10 per venue with attribution, verified at 800px. Blocked on a
  platform-terms question: `photoUri` is signed and expires, and re-hosting runs into Maps Platform caching terms
- **The 61 venues that stopped being reachable** in @makanlah-92's battery. Expected to return now the ceiling is
  raised, since they were crowded out by distance rather than out-ranked. **Unverified**

---

---

## 2026-08-30 — Resumed. #144 Unblocked, #141 Built, The Gap Surface Reads Its Flag

**Three peers came back from the restart with no role between them.** The handoff table in `docs/dev1-resume.md` names
`makanlah-13` / `makanlah-8d` / `makanlah-fb`; the live sessions are `makanlah-f3`, `makanlah-92` and `makanlah-73`.
**Session names do not survive a restart, so a handoff must not use one as an address.** `scratchpad/UAT-ROUND2.md` did
not survive either: scratchpads are session-scoped and all three were empty. Roles were re-taken by agreement, not
recovered. Peer 2 is frontend and holds the tree.

### #144's Three Answers: Two Of Them Changed Nothing

Answered by Peer 1 under [`AUTONOMY.md`](AUTONOMY.md), the owner having delegated. **One-tap disclosure and no model
blurb on the card were already the built state**, verified in the rendered DOM at 390px rather than from source: the
disclosure is a `<details>` with no `open`, and the blurb renders only on `/r/:venueId`. **A question can be answered by
looking at what shipped**, and two of the three were.

**The third was not a yes/no at all.** #141 is unimplemented work, deferred until this branch's structural rework
landed. Built at the answered density.

| Setting | Value                               | Checked Against                |
| ------- | ----------------------------------- | ------------------------------ |
| Lattice | 24px pitch, ~1px dot                | Composited pixels, not the CSS |
| Light   | `#dcddd2` on `#f7f7f4`, **1.28:1**  | Gutter sample, 84 dots         |
| Dark    | `#262820` on `#12130f`, **1.25:1**  | Same lattice, same count       |
| Script  | 兴记肉骨茶 + a full Chinese excerpt | Not Latin placeholder          |

**The two themes land within 0.03 of each other**, which is what "survives both themes" had to mean to be checkable.
Drawn as a gradient rather than the mask `.ground` uses, because a gradient reads `var(--dot)` and a data URI cannot.

### The Gap Surface Now Names Each Entry's Evidence Class

The park note's first item. `85b9220` shipped `verifiable` and `live_citations` per entry and the client never read
them. Each entry now says **"9 posts still open"** or **"No post still opens"** instead of all of them reading alike.

**Both fields are optional and the note disappears when they are absent.** An older API sends neither, and a missing
flag read as `false` turns "we cannot tell" into "nobody wrote about this" — inventing the exact claim the flag was
added to prevent. **Silence is the honest fallback; `false` is a claim.**

### #170: Three Of Five Advertised Filters Reach Nothing

Found by Peer 3, confirmed here by controls rather than by reading source.

| Body                                                    | HTTP |
| ------------------------------------------------------- | ---- |
| `prefs` as a bare string, a bare integer, or `null`     | 200  |
| `radius_m: 999999` and `radius_m: 50`, a declared field | 422  |

**A declared field rejects a bad value; `prefs` accepts every shape**, which is what an undeclared field looks like. Two
additions to the issue: **`budget` and `cuisine` are dead request fields** — declared at `api/main.py:93-94` and read
nowhere, since `:159` passes only `query, lat, lng, radius_m, limit` — and **Drop The Craving cannot change the
results**, because it re-runs the same term at the same radius with the only differing input inside the discarded
object. The false comment that hid this is corrected; the product half is untaken.

**A same-query A/B does not measure this and nearly said the opposite.** Two sequential calls differing only in the
craving returned different result counts, which reads as evidence `prefs` works. An identical payload sent twice also
varies across time and matches within a burst, so `/recommend` is time-sensitive and the A/B was measuring the clock.
**The 200-vs-422 table is the decisive test.** Same shape as a check agreeing with itself: the control is what turned a
plausible finding into a real one.

### Notes For The Next Session

- **`gh` cannot read check-runs with this token** (`gh pr checks`, `gh api .../check-runs` both 403). `guard-merge.sh`
  falls back to `gh run list`, so merging still works. Use `gh run list --branch <ref>` to read CI
- **`distance_gap` fires on 54% of dense-anchor requests, and its `verifiable: true` class is the majority.** Peer 3
  measured 14 of 26 requests firing across 3 anchors x 10 dishes, **36 entries, 25 true against 11 false**, with live
  counts up to 13. **Do not sample this surface from a far-flung anchor.** Peer 2 scanned 16 dishes from Penang, JB and
  Kuantan, found one trigger, and concluded the true class was unobserved. It was the sample: where nothing in range
  serves the dish AND the wide lane knows nothing either, nothing can fire. The product scenario is the dense anchor,
  someone standing in KL on a tight radius, and there it fires constantly
- **A narrower case is still real:** `bak kut teh` at `radius_m=300` from KL centre returns `results: []` with no gap of
  either kind, where radius 0 returns 5 picks. It degrades honestly to "Nothing for X within 0.3 km of you", so it is a
  quality gap rather than a lie. Peer 1 has it, behind #170
- **`readingFor()`'s five labels stay sentence case.** `One source`, `Two sources`, `Thin evidence`, `Nothing to read`,
  `Listening`. TitleCase arguably applies; five labels that read as a deliberate set are a set, and converting them one
  at a time is how a consistent thing becomes inconsistent

---

## 2026-08-30 — PAUSED For A Workstation Restart

**`main` is deployable. Deploy it on resume and tell both peers the sha** — Peer 3 asked to be pinged with whichever
build is live.

### What Happened Right Before The Pause

PR #166 changed `tally_sentiment` to count dead posts, built on Peer 2's diagnosis that `1919餐馆` was misscored. **Peer
2 retracted that diagnosis and it was right to.** The mention scores **−1.0 correctly**; the post is `dead: true` and is
excluded because nobody can open it.

**Both peers then independently argued for reverting, and the deciding reason is the same one:** if sentiment counts
dead posts while `add_corroboration` does not, the two numbers on one card describe different populations — **which is
#143 arriving from the other direction.** Reverted. The `distance_gap` half of #166 is kept: it is unaffected, Peer 3
wanted it, and Peer 2's client for it is built and green.

### The Copy Bug: Fixed On Peer 2's Branch, NOT On `main`

Peer 3's point was that the line read **"Of the N posts here"**, and _here_ means on this card — so if the card renders
a dead excerpt the number excludes, **the sentence is false as English however correct the arithmetic is**.

**Peer 2 fixed it on `ffc909e`**, now reading `3 posts still open: 1 critical, 2 positive.` — naming the property rather
than gesturing at the page, and reusing vocabulary already on screen, since a dead row reads _"This post no longer
opens."_

**That fix is on their branch behind #144, and it is NOT deployed.** Verified rather than assumed:
`git merge-base --is-ancestor 6525cea 85b9220` fails, and `why-more-body` is absent from `main` entirely. So the live
client still carries the old wording.

**This also closes Peer 3's open question.** They measured `.why-more-body = []` on prod and could not tell "#144 not
deployed" from "#144 deployed and failing to render" without repo access. It is the former. **Nothing to file.**

**Fixing it found a second direction nobody had seen.** `leadPair` caps excerpts at **two** however many the line
counts, so "of the 3 posts here" was wrong beside two quotes **on a healthy venue with no dead post involved**.

**Peer 2 declined the alternative of never rendering a dead excerpt, rightly**: a stamp reading four posts over a page
showing one invites exactly the doubt the stamp exists to answer.

### The Invariant That Came Out Of It

Peer 3 generalised **#87, #111, #153 and this line into one bug occurring four times** — each true by its own rule and
false as English, which is why unit tests passed through all four. In `docs/DESIGN.md` on Peer 2's branch, **not yet on
`main`**:

> **Any rendered count must equal the items visible on that surface, or name the property it counts.**

`scratchpad/countcheck.mjs` enforces it, ran clean on `85b9220`, and correctly did not fire on "Corroborated by two
independent sources" because that names its property. **Trust its zero only because it is mutation-tested 5/5** — Peer
3's first two versions silently never fired, a heredoc then a template literal each eating the regex backslashes, and
v1's own test reported "3/5 OK" with all three false all-clears.

**That is the day's lesson arriving on the instrument built to catch the day's lesson**: the failure was never the
language, it was that neither check could see its own silence. Belongs with the Han-text caution in #159.

### Three Chinese-Text Heuristics Were Written Today And All Three Were Wrong

Carry this into #159, which touches Han text throughout:

- Peer 2's `length < 3` name guard flagged **鱼你**, a real two-character venue
- Peer 3's negative-excerpt sweep matched **踩雷 inside 不踩雷** and **雷 inside 無雷**, inverting all three hits
- My gap matcher matched **`ckt` inside `elder garden mo(ckt)ail`** and **`sate` inside `ro(sate)d chicken`**

None were visible to an English-language test pass. The rule that worked: **whole-word for Latin, substring for Han**,
because 肉骨茶 inside 中药肉骨茶 is genuinely the same dish and there is no word boundary to lean on.

### A Scope Error All Three Sessions Made

Peer 2 justified printing unanimity on **163 of 186 multi-mention venues span more than one bucket** — my figure,
describing a venue's **whole record**. The line describes the **cited, live, trimmed** posts, two or three, where **36
of 44 read "all positive" — 82%, not 12%**. The number was not wrong; it answered a different question than the card
asks. Same shape as reporting #143 fixed while production still disagreed on 5 of 25.

### Where Everything Stopped

| Branch / PR                                | State                                                                                                                                                                  |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **#165**                                   | Open, green — an earlier docs checkpoint                                                                                                                               |
| **#144**                                   | Open, green, **blocked on three one-word answers from the owner** (Peer 2's): disclosure one-tap or always-open, whether the model blurb returns, dot density for #141 |
| **`feat/gmaps-discovery-wip`** (`250c602`) | **Unverified.** `discover()` for #157, never run against a signed-in browser; `LIST_JS` is a guess at the results-feed DOM. Do not merge because it compiles           |
| Peer 2                                     | Parked clean at `80511ce`, preview deploy-verified                                                                                                                     |
| Peer 3                                     | Parked, record at `scratchpad/UAT-ROUND2.md`                                                                                                                           |

**Peer 3's one open question**: on Peer 2's preview `834d3d2`, `1919餐馆` returned 3 cards with **no sentiment line
found**. They explicitly flag this as probably their own selector — they matched a quoted copy string literally — and it
needs a 1440 and a non-lean run. **Assume the instrument until someone checks.**

**Next up is #157**, Maps venue discovery — the ceiling on everything else and the thing a real tester actually
complained about. All three sessions agree it precedes the copilot, whose schema is settled and whose client half Peer 2
has already built.

---

---

## Earlier Sessions

The full run log for August 2026 — every session, every measured figure, every instrument that agreed with itself and
was wrong — is in [`archive/PROGRESS-2026-08.md`](archive/PROGRESS-2026-08.md). It is kept verbatim rather than
summarised, because the numbers in it are the evidence for decisions this file only states.
