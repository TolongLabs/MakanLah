# Source Material

Raw captured inputs, kept verbatim so we cite them instead of relying on memory. This is the record we check when a
summary and reality disagree.

Empty for now. The first thing that lands here is the spike's output.

---

## What Belongs Here

Platform behaviour we observed rather than assumed, and anything an outside party published that a decision rests on:

| Kind                         | Example                                                                                                           |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Measured platform limits** | Observed Xiaohongshu rate limits, the shape of a fingerprint challenge, what a session cookie actually gates      |
| **Captured payloads**        | A real post's JSON or HTML, redacted of anything identifying, as the fixture the corpus schema is written against |
| **Third-party docs**         | Scrapling, Firecrawl or Hermes Agent pages that a decision cites, captured with the date read                     |
| **Spike logs**               | The raw run output behind a reported number, so "34 of 50" can be checked                                         |

**Not here:** interpretations, rankings or a locked decision. Those go in `../TRD.md` or `../superpowers/research/`.

---

## Conventions

| Rule                     | Detail                                                                                                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Append-only**          | Never rewrite these to match later beliefs. Corrections go in the doc that cites them                                                                      |
| **Transcribe**           | Do not summarise. Summaries belong in `../PRODUCT.md` or `../TRD.md`                                                                                       |
| **One file per source**  | `<topic>.md`, or `<topic>-<YYYY-MM-DD>.md` when the same source recurs — and platform behaviour recurs, because it changes                                 |
| **Head with provenance** | What the source was, how it was captured, when. **Name the tool, not your path to it** — a teammate does not have your `~/CS/...` or `C:\Users\...` layout |
| **Date every capture**   | A measured rate limit is true on a date and not after. An undated observation is unusable within a month                                                   |
| **Mark uncertainty**     | `[inaudible]` rather than a guess in a transcript; `[ASSUMPTION]` where behaviour was inferred rather than observed                                        |

---

## What Never Lands Here

**No personal data, and no bulk harvest.** A fixture is one post, redacted — not a corpus dump. Scraped content at
volume lives in `data/raw/`, which is gitignored, and the git guard blocks a force-add of it.

**No credentials, cookies or session tokens**, including inside a captured payload. Strip them before the file is
written, not before it is committed.

Audio and video are gitignored. **Commit the transcript, not the recording.**
