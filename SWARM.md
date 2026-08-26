# Agent Swarm Workflow

How MakanLah gets built: GSD supplies the orchestration spine, a free external model
supplies the typing, and a contract between them derived from measurement rather than
intuition.

---

## 1. The rule everything follows

**A task belongs to a worker only if the orchestrator can write a failing test for it
first.**

Forced by two failure modes observed under benchmark (§7):

- **Silent death** — 1 of 8 concurrent workers produced no output, no error, no log.
- **Plausible-but-wrong** — output that reads correctly and fails hidden tests.

Neither is visible in a worker's self-report. Both are caught by an independent test
the worker never sees. A benchmark in which the model wrote its own tests scored 100%
and was worthless; only the hidden-test version discriminated.

If you cannot write the failing test, it is not a worker task.

---

## 2. Two layers

GSD is already a multi-agent framework — 33 typed agent roles with wave-based parallel
execution. **Do not hand-roll dispatch.** The swarm is GSD; the cheap model is fuel.

| Layer | What runs | Model | Cost |
|---|---|---|---|
| **Spine** | GSD's 33 typed roles — research, plan, verify, review | Claude, via model profile | Max 5x quota |
| **Muscle** | `devin -p --model swe-1-7` | SWE-1.7 | **free** |

They meet at one seam: `gsd-executor` shells out to `devin -p` via Bash for bulk
implementation. Planning and verification intelligence stays on Claude; the typing is
free.

### Cost control — the thing that actually matters

**All 33 GSD agents are declared `inherit`.** None carries a model override, so every
subagent runs on whatever the session model is. Setting the session to a frontier model
does not double one agent's burn — it doubles all 33, including `gsd-doc-classifier`
and `gsd-pattern-mapper`, which have no need of frontier capability.

The supported lever is model profiles:

```bash
/gsd-config --profile balanced     # quality | balanced | budget | inherit
```

Requires `gsd-sdk` on PATH (`npm i -g get-shit-done`); it hard-stops without it.

**On orchestrator choice:** Fable 5 is available on Max 5x (`cc fable`) and is more
capable, but it is priced at $10/$50 per Mtok against Opus 5's $5/$25, and Max
allowances are weighted by model cost. It roughly halves the runway before a usage
limit stops an unattended run — spending the exact resource autonomy depends on. Its
strength is long single-shot reasoning; an orchestrator's job is many small decisions.
**Default to Opus 5 at `xhigh`. Invoke `cc fable` deliberately** for two or three
genuinely hard problems — ingestion architecture and ranking design are the candidates.

---

## 3. GSD lifecycle mapped to MakanLah

| Step | Command | Swarm | Notes |
|---|---|---|---|
| Spike | *(none — manual)* | Orchestrator only | Xiaohongshu access. Gates everything |
| Bootstrap | `/gsd-new-project` | 6 agents | 4 researchers → synthesizer → roadmapper |
| Per phase | `/gsd-spec-phase` | 1 | Clarify WHAT before HOW |
| | `/gsd-discuss-phase` | 1–3 | +1 advisor per gray area |
| | `/gsd-plan-phase` | 4 | researcher, pattern-mapper, planner, plan-checker |
| | `/gsd-execute-phase` | **N** | one per plan, dependency waves |
| | `/gsd-verify-work` | 1 | conversational UAT |
| | `/gsd-code-review` | 1–2 | |
| Ship | `/gsd-ship` | 1–2 | PR + review |

**≈ 11–16 agents per phase**, N typically 3–5. At ~6 phases (spike, scaffold, corpus,
ingestion, app, ship): **roughly 80–110 agent invocations total.** Not concurrent —
waves cap parallelism at dependency width, usually 3–5 at once.

`/gsd-autonomous` runs discuss→plan→execute per phase without stopping between them.

### Which phases actually fan out

| Phase | Swarm | Rationale |
|---|---|---|
| Scrape spike | **Orchestrator only** | Exploratory; fails in ways no test anticipates |
| Scaffold | **Wide** | Mechanical; file exists, imports resolve, lints clean |
| Corpus / data layer | **Narrow** | Schema validation is a natural acceptance test |
| Ingestion pipeline | Orchestrator + verify | Fragile by nature; failure needs judgment |
| Hermes prompts | **Orchestrator only** | No acceptance test for "the copilot feels good" |
| Ranking | Orchestrator designs, workers implement | Metric must exist before fan-out |
| UI | Orchestrator + 1 worker | Visual judgment does not parallelise |
| Test hardening | **Wide** | Tests are the contract |
| Optimization | **Orchestrator only** | Needs measurement and judgment |
| Cutover / ship | **Orchestrator only** | Irreversible |

The common mistake is treating "build" as one phase. Inside it the data layer fans out
well and prompt design does not fan out at all.

---

## 4. Worker contract

```
1. Orchestrator writes the failing test.     # worker never sees it
2. Dispatch: task + source file(s) + spec.
3. Timeout 120s.                              # measured tail was 271s
4. Assert the expected artifact exists.       # catches silent death
5. Run the hidden test.
6. Retry ≤3 on failure.                       # 3 attempts → 15/15
7. Never merge on a worker's self-report.
```

Steps 4 and 7 are routinely skipped, and they are why a swarm can report a clean run
over a codebase with holes in it.

Invocation shape:

```bash
devin --model swe-1-7 --permission-mode dangerous \
      --respect-workspace-trust false -p -- "<task>"
```

**Keep dispatch model-agnostic.** The free tier expires with the Devin Pro plan on
**2026-09-23**; GLM-5.3-Flash promo pricing ends **2026-09-09**. Both cliffs land near
production. Hardcoding `devin -p` buys a rewrite at the worst moment.

---

## 5. Lanes

| Lane | Model | Work |
|---|---|---|
| Orchestrator | Claude Opus 5 `xhigh` (Max 5x) | Architecture, spike, prompts, ranking, ship |
| Hard problems | Claude Fable 5 (`cc fable`) | Deliberate, 2–3 invocations |
| Workers | SWE-1.7 via `devin -p` | Bulk implementation. Free, 262K ctx |
| Second opinion | GPT-5.6 Sol (Codex Plus) | Scraper — flat latency suits unpredictable failure |
| Overflow / fallback | GLM-5.3-Flash (OpenRouter) | >262K context; primary after 2026-09-23 |

---

## 6. Unattended long runs

The model is not the binding constraint. In order of what actually stops sessions:

1. **Unmade decisions.** The most common cause by a distance. Every unresolved row in
   `PRODUCT.md`'s open-decisions table is a guaranteed stop. Resolve or pre-authorize
   a default before starting.
2. **Usage limits.** Pace with `/gsd-execute-phase --wave N`, which exists specifically
   for "quota management" and to "stay inside usage limits."
3. **Context exhaustion.** Checkpoint to *files*. A `PROGRESS.md` the orchestrator
   rewrites survives compaction; conversation history does not.
4. **Blocking failures.** Worker fails → retry ≤3 → mark failed → **continue the
   batch.** Never let one straggler halt the run.
5. **No terminal condition.** `PRODUCT.md` defines done; point the run at it.

Permission prompts are already handled — the `cc` alias passes
`--dangerously-skip-permissions`.

---

## 7. Measurements

Hidden-test benchmark: 4 Python tasks, 8 planted defects across 20 tests, models saw
only the buggy source.

| Task | Baseline fails | SWE-1.7 | GPT-5.6 Sol (high) |
|---|---|---|---|
| interval merge | 1 | 6/6 · 15s | 6/6 · 119s |
| LRU eviction | 2 | 4/4 · 34s | 4/4 · 115s |
| semver prerelease | 4 | 6/6 · 41s | 6/6 · 128s |
| rate-limiter slots | 1 | 4/4 · **271s** | 4/4 · 110s |
| **Total** | 8 | **20/20 · 361s** | **20/20 · 472s** |

Tied on correctness. SWE-1.7 is 3–8× faster on legible fixes and collapses on
state-over-time reasoning; Sol is slower but flat.

**For fan-out, tail latency beats mean latency.** A batch finishes when its slowest
worker finishes, so SWE-1.7's 271s tail can lose to Sol's 128s ceiling despite winning
on average. Hence the 120s timeout and retry rather than waiting out a straggler.

Reliability:

| Condition | Result |
|---|---|
| SWE-1.7 sequential, 6 runs | 6/6 |
| SWE-1.7, 8 concurrent | 7/8 — one silent death, no error |
| GLM-5.3-Flash, 90 requests | ~73%, flat across concurrency 2/4/8 |
| GLM-5.3-Flash + 3 retries | 15/15, +13% calls |

GLM's failure surfaces in an `.error` field while `.choices[]` returns empty — a harness
reading only the content field records it as a **successful empty result.** Parse the
error field explicitly.

Costs: SWE-1.7 free (three counters unmoved over 15 runs; Cognition docs confirm free
models do not draw quota). GLM-5.3-Flash $0.075/M in, $0.25/M out under a promo ending
2026-09-09, doubling thereafter.

---

## 8. Caveats on this evidence

Four tasks, one run each, all Python, all single-file bug fixes. It justifies SWE-1.7 as
the default worker and nothing broader. It says nothing about multi-file refactors,
long-context work, or tasks where 262K becomes binding — which includes most of the
ingestion pipeline. Re-measure before trusting workers with those.

Agent counts in §3 are read from GSD skill definitions and agent descriptions; the
per-phase totals are estimates, not guarantees. `execute-phase` in particular scales
with plan count, which is not known until `plan-phase` runs.
