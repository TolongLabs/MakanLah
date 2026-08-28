# Embedding Model — Three-Language Retrieval Test

**Date:** 2026-08-27 · **Decides:** the one open row in [`../../TRD.md`](../../TRD.md#the-embedding-decision)

`TRD.md` said to decide the embedding model **by measurement, not argument**, and named the test: a held-out set of KL
venues, queried in each of English, Malay and Chinese, checking whether the same venue is retrieved regardless of the
language the question was asked in.

**Result: `text-embedding-v3` on DashScope, 1024 dimensions.** Free under the existing key, Singapore-hosted.

## Numbers

    model: text-embedding-v3  dim: 1024  venues: 8

      en  top-1 8/8  (100%)
      ms  top-1 7/8  (88%)
      zh  top-1 8/8  (100%)

      same venue retrieved in all three languages: 7/8 (88%)

      misses:
        [ms] yut_kee -> ho_kow

      VERDICT: weakest language 88%. a language is behind — see misses above

## Reading It

**No language collapses.** The failure mode `PRODUCT.md` names as risk #3 is a pipeline that works in one language and
silently biases against the others; that is not what this shows. English and Chinese are perfect, Malay drops one.

**The single miss is a near-miss, not a language failure.** `chicken chop Hainan di kedai kopi lama` retrieved Ho Kow
Hainam Kopitiam instead of Yut Kee. Both are old Hainanese kopitiams in the same part of KL, and the query names
neither. A human given those two documents and that query could reasonably pick either.

## Limitations, Which Are Not Small

- **Eight venues.** One miss moves the Malay score by 12.5 points, so the gap between 88% and 100% is a single item and
  well inside noise. This does not establish that Malay is weaker, only that it is not obviously broken
- **Hand-written documents**, not real corpus rows. They were written to be realistically mixed-script, but they were
  written by the same process that wrote the queries
- **Queries deliberately never name the venue.** Naming it would measure string matching rather than retrieval, but it
  also makes this harder than the real query distribution, where users sometimes do name a place
- **No comparison run.** Cohere `embed-multilingual-v3` and BGE-M3 were not measured. `text-embedding-v3` was taken
  because it clears the bar at zero marginal cost, not because it beat anything

## When To Revisit

Re-run against **real venue rows once the corpus has a few hundred**, and only then against a paid alternative. The
number that matters is cross-language agreement — the same venue coming back regardless of query language — because a
model can score well per-language and still return a different venue for each phrasing.

Reproduce: `uv run python makanlah/research/embedding_language_test.py`

## One Implementation Note

DashScope rejects an embedding batch larger than **10** for this model with a bare `HTTP 400` and no explanatory body.
The client chunks at 10. This is a correctness concern rather than a throughput one — a batch of 24 fails outright.
