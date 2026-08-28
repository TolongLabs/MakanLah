# Evals

Ranking quality, measured. Not part of `pytest`: these need the live corpus and spend model quota, and
[`TRD.md`](../docs/TRD.md) rules out a CI suite depending on either.

```bash
uv run python evals/build_truth.py   # regenerate labels from the corpus (do this deliberately)
uv run python evals/run.py --quick   # 1 repeat, dish queries only  ~43k tokens
uv run python evals/run.py --label "what changed"   # 3 repeats, everything  ~134k tokens
```

## It Costs Real Quota

**A full run is ~134,000 tokens.** The DashScope free allowance is 1,000,000 per model, expiring 2026-10-13 and not
refilling, so a full run is **13% of the budget for that lane** and the allowance covers about **7 of them**.

Measured: one re-rank prompt is ~2,286 input tokens (16 candidates, two excerpts each) plus ~200 out, and a full run
makes 54 calls at 3 repeats.

**Use `--quick` while iterating** and spend a full run only on a decision you are going to record. On 2026-08-28 a
single afternoon of measurement consumed ~815k of the lane's allowance, and the largest single item was a `max_tokens`
A/B that returned a **negative** result. Finding that out was worth it once; it is not worth it twice, which is why the
numbers are written down in `TRD.md` rather than left to be re-measured.

## Metrics

| Metric   | Means                                                           |
| -------- | --------------------------------------------------------------- |
| **p@5**  | Share of the top 5 that genuinely serve the dish                |
| **fp@5** | Share whose tagged dishes are entirely the **opposite cuisine** |
| **wd@5** | Share with ≥2 tagged dishes, **none** of them the one asked for |
| **top1** | How often the first result is correct, across repeats           |

**`fp@5` is nearly useless on its own and is kept only as a floor.** The failure that started this work was
`bak kut teh` returning 首都茶室 and 何九茶室 — both Malaysian, so an opposite-cuisine rule scores that **0.000 and
calls the ranker perfect**. `wd@5` is the metric that sees it.

**Every case runs three times.** The re-ranker returned 2, 10 and 10 results for three identical calls, so a single run
measures the roll rather than the ranker.

## Limits, Stated Rather Than Hidden

- **Dish coverage is 486/1705 mentions.** A venue with no dish tag is _unknown_, never negative. Only venues carrying ≥2
  canonical tags enter a negative set
- **Mood queries are unscored.** No dish ground truth exists for "somewhere light for breakfast", so they are reported
  for shape and latency and never folded into a number
- Labels come from the corpus itself, so a systematic extraction error would be invisible here
