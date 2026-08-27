# AGENTS.md

Canonical, tool-agnostic project instructions. Every agentic tool works from this file; `CLAUDE.md` only points here.
**Read [`docs/PRODUCT.md`](docs/PRODUCT.md) before acting** — what MakanLah is, what is in scope, and which decisions
are still open.

> **This project runs mostly unattended.** Nobody is watching, and a session that stops to ask has failed the task
> rather than paused it. [`docs/AUTONOMY.md`](docs/AUTONOMY.md) carries the owner's standing authorization to resolve
> blockers on your own judgment, a pre-made default for every open decision, and the four things that genuinely stop
> you. **Read it before deciding you are blocked.**

---

## Project

**MakanLah** — a web and mobile-friendly app that recommends restaurants near you, ranked by personal preference,
drawing on real recommendations Malaysians actually write. Primarily Xiaohongshu / RedNote, plus other social platforms.
Repo: `github.com/TolongLabs/MakanLah`.

**Status: pre-scaffold.** No application code exists. What exists is this instruction file, the tooling around it, and
three documents stating intent.

The differentiator is **showing the evidence**. A pick that cites the post it came from is trustworthy in a way a
generated blurb is not. Anything that breaks the citation trail breaks the product.

---

## The Spike Gates Everything

> **Nothing gets built until the Xiaohongshu spike returns.** RedNote gates content behind login, fingerprints devices
> and rate-limits hard. If structured data cannot be pulled at usable volume, MakanLah has no product — and every hour
> of scaffolding spent before that is proven is wasted.

The question it answers, and the only one:

> Can we pull ~50 KL restaurant posts with structured fields — name, location, dish, sentiment — into a normalized
> record?

One orchestrator session, timeboxed, no workers. Exploratory work fails in ways no test anticipates, which is exactly
the case where fan-out is wrong ([`docs/SWARM.md`](docs/SWARM.md#which-phases-actually-fan-out)).

**If application work is requested while the spike is unresolved, run the spike first and say that you did.** Do not
ask, and do not build on an unproven corpus. The spike is short by design; running it is always cheaper than scaffolding
around an assumption.

**A partial result resolves the gate.** 30 of 50 posts with three of four fields is a pass — write the numbers into
`docs/PROGRESS.md` and proceed. Only a total failure across every source is a stop, and that case is
[`docs/AUTONOMY.md`](docs/AUTONOMY.md#what-still-stops-you) #4.

---

## Non-Negotiables

From [`docs/PRODUCT.md`](docs/PRODUCT.md). These are architectural commitments, not preferences:

1. **No single source may be load-bearing.** Not for legal cover — for uptime. Any one platform can go dark mid-sprint,
   and a data layer with a single point of failure goes dark with it. Aggregate across platforms so the app degrades
   rather than dies
2. **Never fetch live on a user request.** The app reads a normalized local corpus; the corpus is refreshed in the
   background. Freshness is a background concern, never a request-path one
3. **Two workloads, two runtimes.** Interactive copilot (low latency, a user is waiting) and batch ingestion
   (throughput, nobody is waiting) have opposite characteristics. Coupling them means a scraping run degrades the
   interactive experience. Keep them separate from the first commit, not as a later refactor
4. **Every result cites its source post.** A ranked entry without a real post behind it is not a result, it is a
   hallucination with a rating

**Language mix is a correctness requirement, not a polish item.** Posts are English, Malay and Chinese, often inside one
sentence. Extraction and ranking that handle only one will silently bias results toward whichever language the pipeline
handles best — and it will look like it is working.

---

## How To Work

**Proceed without asking** on anything you can name a sensible default for: picking a library, file layout, naming or
approach; installing a dependency; refactoring your own code mid-task; writing tests, docs or types you judge necessary;
fixing a bug in code you are already touching. If two approaches are close, pick one and say which. **A reversible
decision made now beats a correct decision made after a ten minute conversation** — and in an unattended run, that
conversation never happens at all.

**Nobody is at the keyboard. Decide, record, continue.** [`docs/AUTONOMY.md`](docs/AUTONOMY.md) pre-authorizes this and
pre-answers every open decision in `docs/PRODUCT.md`. When something blocks you, walk its ladder — take the default, cut
scope, stub the boundary, skip the unit and continue the batch, change approach, or park it and pick up the next
independent task. **Six rungs before stopping is an option.**

**Only four things stop you**, and they are the boundary of the authorization rather than problems to solve: spending
real money; an irreversible action outside this repo; a platform-terms question no technical default answers; or
evidence the product premise is dead. [`docs/AUTONOMY.md`](docs/AUTONOMY.md#what-still-stops-you) is canonical on all
four. For the first three, record the finding, open an issue, and **continue with whatever independent work remains**.

**Say what you assumed, do not wait on it.** Surfacing a tradeoff and blocking on one are different acts. Do the first,
never the second.

**The bar for shipping.** Work is ready when CI is green and it does what was asked. It need not be complete, elegant or
final. If you are behind, cut scope, not the quality of what ships. **Never claim it works without having run it and
read the output** — nobody is checking behind you.

---

## The Gate Before Implementation

**No implementation starts until `docs/` holds all three.** Cheap to write, expensive to skip: without them the first
days produce code nobody agreed to.

| File              | Answers                                                                         | Owns                                      |
| ----------------- | ------------------------------------------------------------------------------- | ----------------------------------------- |
| `docs/PRODUCT.md` | **Who and why.** The user, their problem, the core loop, scope, open decisions  | The spine. Everything downstream cites it |
| `docs/PRD.md`     | **What.** Requirements, user stories, acceptance criteria, what is out of scope | Scope                                     |
| `docs/TRD.md`     | **How.** Architecture, API contracts, data models, schemas, decision rationale  | Technical truth. Canonical over this file |

`docs/PRODUCT.md` and `docs/TRD.md` exist. **`PRD.md` does not** — write it and proceed; do not stop for it.
`docs/DESIGN.md` joins them when frontend work starts, and owns the design system: palette, type pairing, radius and
border treatment, spacing scale.

**The gate is binary, and it is not a stopping point.** If the three are not all present, the answer to "can I start
building" is no — so **write the missing one, then build**. It is an hour of work against defaults already
pre-authorized in [`docs/AUTONOMY.md`](docs/AUTONOMY.md#pre-authorized-defaults), not a decision to escalate. The
`session-brief` hook reports gate state at the start of every session.

**The corpus schema is the highest-value thing `TRD.md` carries.** Ingestion, ranking and the UI all read it, and it is
the one contract a worker can be given a failing test against.

---

## How To Report

If reading your message takes longer than doing the thing, you have cost time.

- **Lead with what happened.** First sentence answers "what is the state of things now?" No preamble, no restating the
  request
- **Three to five sentences** for a normal update. Longer only when something broke and the detail is needed
- **Say what a human should do, or say nothing is needed.** Never leave someone guessing whether they are blocked
- **No status theatre.** Do not narrate steps, list what you rejected, or summarise what you already said
- **When something breaks, give the error verbatim.** Paste the trace, then say in one plain sentence what it means
- **Report a scrape result as a number.** "Pulled 34 of 50 posts, 6 missing a location field" — never "ingestion is
  working"

---

## Tech Stack And Commands

| Tool                                 | Role                                                                      |
| ------------------------------------ | ------------------------------------------------------------------------- |
| **Bun**                              | Package manager and script runner                                         |
| **Biome**                            | Lint and format for JS, TS, JSON, CSS, HTML                               |
| **Prettier**                         | Format for Markdown and YAML, the two Biome does not cover                |
| **TypeScript**                       | `tsc --noEmit`; strict, `noUncheckedIndexedAccess`                        |
| **uv**                               | Python runner and dependency resolver. `pyproject.toml` pins the project  |
| **Ruff**                             | Lint and format for Python. Mirrors Biome: 120 columns, single quotes     |
| **commitlint + husky + lint-staged** | Conventional Commits on `commit-msg`; staged files linted on `pre-commit` |
| **GSD**                              | Orchestration. `npm i -g get-shit-done`                                   |

```bash
bun install          # dev tooling; also wires husky hooks
bun run lint         # biome + prettier + ruff check + ruff format --check
bun run format       # biome + prettier + ruff format
bun run typecheck    # tsc --noEmit, once src/ exists
```

**Application framework and hosting are not chosen yet.** They get chosen and justified in `docs/TRD.md`; this table is
an inventory of what is installed. **The Python stack now exists** — the scrape spike created it, as `uv` plus `ruff`,
wired into `lint-staged` and `bun run lint` at the same time. `pyproject.toml` is its root.

**The scraper stack is settled by the spike**: CDP against a signed-in Chrome for RedNote, Nominatim for geocoding,
neither needing an API key. Firecrawl stays for open-web fallbacks. See `docs/TRD.md`.

**Prettier owns Markdown and YAML, Biome owns everything else**, split by file extension rather than an ignore file.
`.prettierrc.json` mirrors every formatter setting `biome.json` states, so both wrap at 120 and neither can undo the
other. `embeddedLanguageFormatting` is off, so fenced code samples are never rewritten.

`rtk` and `graphify`, both optional and per-machine, are documented in [`docs/agent-tooling.md`](docs/agent-tooling.md).
The layout tree lives in [`docs/README.md`](docs/README.md#layout), because a reviewer must read it without opening this
file. Source layout is not decided; add it there when it is.

---

## Building With Workers

[`docs/SWARM.md`](docs/SWARM.md) is the full contract. Four things from it that change behaviour even if you never open
it:

**A task belongs to a worker only if you can write a failing test for it first.** Forced by two measured failure modes:
a worker that produced no output, no error and no log; and output that reads correctly and fails hidden tests. Neither
is visible in a worker's self-report. If you cannot write the failing test, it is not a worker task — do it yourself.

**Never merge on a worker's self-report.** Assert the expected artifact exists, then run the hidden test the worker
never saw. These two steps are the ones routinely skipped, and they are why a swarm can report a clean run over a
codebase with holes in it.

**Do not hand-roll dispatch.** GSD is already a multi-agent framework with 33 typed roles and wave-based parallel
execution. The swarm is GSD; the cheap model is fuel. All 33 roles are declared `inherit`, so the session model sets the
burn for every one of them — use `/gsd-config --profile balanced` rather than reaching for a frontier model globally.

**Keep dispatch model-agnostic.** Two cliffs land near production: GLM-5.3-Flash promo pricing ends **2026-09-09**, and
the free SWE-1.7 tier lapses with Devin Pro on **2026-09-23**. Hardcoding `devin -p` buys a rewrite at the worst
possible moment.

Not everything fans out. Scrape spike, Hermes prompts, optimization and cutover are orchestrator-only; scaffold and test
hardening go wide; the data layer is narrow because schema validation is a natural acceptance test.

---

## CLI First, Always

Reach for a CLI before a dashboard: `gh` for GitHub, `bun` for Node, `devin` for workers. Clicking through a dashboard
leaves no trace, cannot be handed to a teammate, and cannot be repeated tomorrow.

**If the CLI is missing, say so immediately and give the install command.** Do not route a human through the web UI as a
workaround.

**If no CLI exists, drive the browser yourself.** Pick by whether the task needs a logged-in session:

| Task                                                              | Tool                                                                     |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Behind a login: Xiaohongshu, a provider dashboard, OAuth          | `claude-in-chrome`. Read its `SKILL.md` first; it carries banned actions |
| Our own deployed app: smoke tests, screenshots, checking a render | Playwright, headless. Scriptable, needs no human                         |

Headless Chromium cannot see the desktop browser's cookies, which is the whole reason that split exists — and is also
why the spike's session handling is fiddly rather than trivial.

**Never type a password, card number or API key into a form** for someone, and never accept terms or submit a form on
their behalf. Read the screen, do the navigation, hand back the one action that is theirs. **Screenshot what you did.**

---

## Code Style

- **Biome is authoritative:** single quotes, no semicolons, no trailing commas, 120-char lines, 2-space indent. Do not
  hand-format against it
- **Types:** no `any`; prefer `unknown` plus narrowing. **Validate at every system boundary** — scraped input is the
  least trustworthy data in the project and must be parsed into the corpus schema, never spread into it
- **Error handling:** validate at boundaries; do not wrap internal framework calls in try/catch. An ingestion failure is
  a normal outcome, not an exception — record it and continue the batch
- **Comments:** default to none. Comment only when the _why_ is non-obvious. Never describe _what_ the code does
- **Changes are surgical.** See [guideline 3](docs/coding-guidelines.md#3-surgical-changes)

---

## Documentation Hygiene

- **TitleCase for every heading, subheading, bold lead-in label and table header.** Body prose, full sentences and
  commit subjects stay sentence case. Acronyms and proper names keep their form: AI, API, PR, KL, GSD, MYT, Xiaohongshu,
  RedNote
- **Forward-looking only.** Apply this to what you write or touch. Do not sweep existing docs to conform
- **Do not reformat received sources, transcripts or installed skills.** `docs/source/` is append-only and is the
  verbatim record
- **No clumped prose.** No block over four lines. Three or more consecutive bolded-lead-in paragraphs are a table. An
  enumeration of three or more items inside a sentence is a list
- **Never drop a measured figure, a citation, a section reference or a limitation** to save space. Reformatting must be
  lossless. `docs/SWARM.md` §7 is measurement, not narrative — its caveats travel with its numbers
- **Never create a second file overlapping an existing one.** Update the existing file

### README vs TRD

Both may describe architecture. They differ in **depth and audience**, not subject.

|              | `docs/README.md`                                                 | `docs/TRD.md`                                  |
| ------------ | ---------------------------------------------------------------- | ---------------------------------------------- |
| **Audience** | Anyone landing on the repo                                       | Developers implementing against it             |
| **Depth**    | High-level narrative: the whats, hows and whys                   | Canonical implementation-level reference       |
| **Contains** | Architecture overview, diagrams, setup, constraints, limitations | API contracts, data models, schemas, rationale |
| **Rule**     | Anything an outside reader needs must live here                  | Never duplicate the README. Go deeper instead  |

"It is in the TRD" is a valid answer for implementation detail, **not** for anything an outside reader needs. It lives
in `docs/`, not the repo root, and GitHub renders it as the landing page, so keep links relative to `docs/`.

---

## Design Standards

The app is the product, and its whole promise is that a hungry person decides in under two minutes. **A screen that is
merely competent has failed that, not partly met it.**

The bar: **the work must not look generated.** The tells to avoid:

- Warm cream ground, serif display face, terracotta accent
- Near black with a single acid green or vermilion pop
- A purple to blue gradient hero on white
- Inter or Space Grotesk as the safe default
- Everything centre aligned
- One large corner radius on every surface
- A coloured rail down the side of a rounded card
- Numbered markers on content that is not a sequence
- Three items in every list because three feels balanced
- Glassmorphism with no reason for depth
- A dark dashboard with neon chart lines and no data behind them

**Structure must mean something.** If a design uses numbering, an eyebrow, a divider or a state chip, that device has to
carry real information. A numbered list of unordered things is a lie told in layout. **The cited post is the design
problem**, not a footnote to it — the evidence is the feature, and a layout that buries it has inverted the product.

**UI text follows Documentation Hygiene.** TitleCase for nav items, buttons, section headings, card titles, table
headers, tab labels, menu items, modal titles and form labels. Sentence case for body copy, helper text, placeholders,
tooltips, errors, empty states and toasts. `Save Changes`, but `We could not reach that source, showing what we have.`

**Mixed-language text breaks layouts.** Chinese glyphs have different metrics to Latin ones, and a Malay place name is
longer than its English gloss. Test every string-bearing surface with all three, not with lorem ipsum.

**Claude Code cannot generate images.** Delegate to Codex, which needs no API key:

```bash
codex exec --skip-git-repo-check "<prompt>. Use your image generation tool. Save to /absolute/path/<name>.png"
```

Give it an absolute path, and resize before anything lands in the repo. Use the `brandkit` skill for art direction
rather than hand-writing a prompt.

**Nothing visual is done until all four are true.** State them when you report:

1. `impeccable critique` has run and its findings are addressed or consciously declined
2. The `design-taste-frontend` pre-flight check passes
3. The screen has been viewed at phone width, not just in a wide editor pane
4. TitleCase has been checked against rendered text, not source

---

## How Work Ships

**`main` is PR-gated. No stray commits.** `.claude/hooks/guard-git.sh` enforces it.

1. **Branch.** `<type>/<short-slug>`, matching the commit types below
2. **Commit** in [Conventional Commits](https://www.conventionalcommits.org/) form: `<type>[scope]: <description>`, a
   single imperative sentence, lowercase, no trailing period. Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`,
   `chore`, `style`, `perf`
3. **Push the branch** and open a PR with `gh pr create`
4. **A human merges** with `gh pr merge --squash --delete-branch`. Merging is denied to agents in
   `.claude/settings.json`

Small fixes still go through a branch. The overhead is one command; the alternative is a `main` nobody can review or
revert cleanly. **This matters more with workers than without them** — an ungated `main` is exactly where
plausible-but-wrong output lands unreviewed.

**Unattended, CI is the reviewer.** Step 4 has nobody to perform it, so an unattended run stalls at the first PR unless
`scripts/unattended.sh on` is active. That allows self-merge **only on green CI**, leaves the branch-and-PR record
complete, and does not touch the git guard. Turn it on before a long run, off after; `scripts/preflight.sh` reports
which mode is live. A red check is a human saying no — treat it that way.

**Checkpoint to files, not to conversation.** [`docs/PROGRESS.md`](docs/PROGRESS.md) survives compaction and is printed
by the session brief at every start; conversation history survives neither. Rewrite it whenever you finish a unit, make
a decision, route around a blocker, or a `PreCompact` hook tells you to. It holds session state — where you were, what
you skipped and why — and never the backlog, which stays in Issues.

**TODOs live in GitHub Issues**, not a markdown checklist, a `docs/plan.md`, or a code comment. A checklist in a file
goes stale, conflicts on merge, and is invisible to anyone not in that file. Reference the issue in the PR so merging
closes it: `Closes #12`. A short-lived, in-session task list is fine; anything that outlives the session is not.

```bash
gh issue list                          # what is open
gh issue create -t "..." -b "..."      # add one
gh issue close <n>                     # done
```

---

## Critical Do-Nots

- **Do not** stop an unattended run on a blocker you could route around. Six rungs in
  [`docs/AUTONOMY.md`](docs/AUTONOMY.md#the-rule) come before stopping is an option
- **Do not** ask a question `docs/AUTONOMY.md` already answers. Every open decision in `docs/PRODUCT.md` has a
  pre-authorized default
- **Do not** let one failed unit halt a batch. Retry ≤3, mark it failed, continue, open an issue
- **Do not** disable, skip or narrow a check to make CI green. Narrow the _change_ instead — unattended, CI is the only
  reviewer there is
- **Do not** end a session without rewriting `docs/PROGRESS.md`. The next session starts with none of your context
- **Do not** start application work before the spike resolves. It gates the project
- **Do not** make one data source load-bearing, or fetch from a platform on the request path
- **Do not** couple the copilot and ingestion runtimes
- **Do not** return a recommendation without the post it came from
- **Do not** treat evasion as a strategy. It is an arms race against someone else's release schedule and breaks without
  warning. Multi-source aggregation and caching are the durable answers; evasion is at best a stopgap. Where a
  platform's terms or rate limits apply, keep collection modest, cached, attributed, and easy to turn off
- **Do not** commit scraped content. `data/raw/` and `data/corpus/` are gitignored and the git guard blocks a force-add.
  Commit the schema and small fixtures instead
- **Do not** commit `.env` or any `sk-…` key. `.env.example` carries key names, never values
- **Do not** copy a cookie jar or session file into the repo. Point `.env` at where it already lives — a browser profile
  is a live credential ([`docs/CREDENTIALS.md`](docs/CREDENTIALS.md))
- **Do not** commit directly to `main`, force-push, rewrite published history, or delete a branch other than a merged
  feature branch
- **Do not** merge your own PR. Propose it; a human merges
- **Do not** merge a worker's output on its self-report. Assert the artifact, run the hidden test
- **Do not** hand-roll worker dispatch around GSD, or hardcode `devin -p` as the only lane
- **Do not** track TODOs in a markdown file
- **Do not** create `docs/architecture.md` or a second README
- **Do not** start implementation before `PRODUCT.md`, `PRD.md` and `TRD.md` all exist
- **Do not** rewrite `docs/source/`. It is the verbatim record
- **Do not** commit a path that only exists on your machine. `~/CS/...`, `/home/<you>/...`, `C:\Users\...`,
  `\\wsl.localhost\...` and scratch dirs under `/tmp` are invisible to everyone else. Name the tool, not your copy of
  it. Machine-independent locations like `~/.claude/` are fine
- **Do not** add Python tooling before the spike decides the scraper stack

---

## Skills, Subagents And Hooks

**30 skills are committed** and all are optional: invoke one when the task matches, not as a checkpoint before every
action. Your tool already lists them with descriptions, so the inventory is not repeated here. Provenance and what was
deliberately not taken: [`.agents/skills/VENDORED.md`](.agents/skills/VENDORED.md).

Two things the listing does not tell you:

- **`brainstorming` is not the ideation skill.** It shapes a build once a concept is locked. `docs/PRODUCT.md` already
  locks the concept, so reach for it at phase boundaries rather than at the top
- **Taste sets the target, `impeccable` hits it.** Do not start with `impeccable`

**No subagents.** This is deliberate: `docs/SWARM.md` §2 says the swarm is GSD, and a hand-rolled dispatch subagent
would compete with GSD's 33 typed roles rather than add to them. If a genuinely single-owner artifact appears later —
one directory, one job, nobody else writing to it — that is when a subagent earns its place.

**Four hooks** are wired in `.claude/settings.json`, each exiting 0 on internal failure so a broken guard never wedges a
session. Only one can stop you: `guard-git.sh` blocks a direct or force push to `main`, `git add .env`, and a force-add
of a scraped corpus. The other three are informational — `session-brief.sh` reports branch state, docs-gate state and
days remaining on the two model cliffs; `env-drift.mjs` reports a local `.env` that disagrees with the repository
without ever printing a value; `format-edited.sh` formats what you just wrote.

---

## Appendix: Standing References

Moved out of this file so they are not reloaded into every session. **The sections above outrank them wherever they
disagree.**

| Reference                               | Lives In                                                                           | Applies                                                                                 |
| --------------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **Autonomy Charter**                    | [`docs/AUTONOMY.md`](docs/AUTONOMY.md)                                             | Any time you think you are blocked. Canonical on defaults and on what stops a run       |
| **Credentials And Logins**              | [`docs/CREDENTIALS.md`](docs/CREDENTIALS.md)                                       | Before an unattended run, and whenever a session or key expires                         |
| **Agent Swarm Workflow**                | [`docs/SWARM.md`](docs/SWARM.md)                                                   | Whenever workers are dispatched. Canonical over the summary above                       |
| **Coding Guidelines (Andrej Karpathy)** | [`docs/coding-guidelines.md`](docs/coding-guidelines.md)                           | Always. Guideline 1 is overridden by **How To Work** above; the file says so at the top |
| **RTK (Rust Token Killer)**             | [`docs/agent-tooling.md`](docs/agent-tooling.md#rtk-rust-token-killer)             | Only if `which rtk` finds it                                                            |
| **Graphify**                            | [`docs/agent-tooling.md`](docs/agent-tooling.md#graphify-codebase-knowledge-graph) | Only if `which graphify` finds it, and only once there is real code                     |

Two rules from them that change behaviour even if you never open them:

- **Changes are surgical.** Every changed line traces to what was asked. Do not refactor, reformat or improve adjacent
  code you were not sent to touch
- **`rtk` does not defeat the git guard, but it does defeat the deny list.** The hook matches the command substring, so
  `rtk git push origin main` is blocked. The `permissions.deny` entries are prefix-matched and are not. That is why both
  exist
