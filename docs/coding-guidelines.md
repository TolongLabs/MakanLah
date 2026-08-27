# Coding Guidelines (Andrej Karpathy)

Standing reference, moved out of `AGENTS.md` so it is not reloaded into every session. **`AGENTS.md` outranks this file
wherever they disagree**, and the callout below is where they actually do.

Behavioural guidelines that reduce common LLM coding mistakes, from
[Karpathy's observations](https://x.com/karpathy/status/2015883857489522876).

> **Where this conflicts with [How To Work](../AGENTS.md#how-to-work), that section wins.** Guideline 1 says to stop and
> ask when something is unclear. In this repo you mostly do not. Pick the reading that ships, state the assumption, and
> keep going. Stop only for the six cases in **Stop and ask only for these six**. The rest of guideline 1, surfacing
> tradeoffs and not hiding confusion, still applies: say the assumption out loud, just do not wait on an answer.
>
> **One place where guideline 1 is not softened:** the open-decisions table in [`PRODUCT.md`](PRODUCT.md). An unresolved
> row there is the single most common thing that stops an unattended run
> ([`SWARM.md`](SWARM.md#6-unattended-long-runs)). Resolve it or pre-authorise a default before starting, rather than
> discovering it at hour three.

## 1. Think Before Coding

- State assumptions explicitly.
- If multiple interpretations exist, say so, then pick one and proceed.
- If a simpler approach exists, say so. Push back when warranted.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No flexibility or configurability that was not requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask: would a senior engineer call this overcomplicated? If yes, simplify.

## 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Do not improve adjacent code, comments, or formatting.
- Do not refactor what is not broken.
- Match existing style even if you would do it differently.
- Notice unrelated dead code? Mention it, do not delete it.
- Remove imports and variables that **your** change orphaned. Leave pre-existing dead code alone unless asked.

The test: every changed line traces directly to what was asked.

## 4. Goal-Driven Execution

Turn tasks into verifiable goals, then loop until verified.

- "Add validation" becomes "write tests for invalid inputs, then make them pass"
- "Fix the bug" becomes "write a test that reproduces it, then make it pass"
- "Refactor X" becomes "ensure tests pass before and after"

Strong success criteria let you loop on your own. Weak criteria force check-ins, which is exactly the cost **Proceed
Without Asking** exists to avoid.
