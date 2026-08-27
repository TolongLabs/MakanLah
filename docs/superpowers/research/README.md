# Research

Cited findings from exploration, kept so a later agent or a teammate with none of your context can reuse them without
redoing the work.

The folder name records that this research is driven by the **superpowers** skills. It carries no obligation to use them
for every file that lands here.

---

## What Belongs Here

One file per topic, named `<topic>.md`. The questions this project will actually need answered:

| Topic                       | The Question                                                                                  |
| --------------------------- | --------------------------------------------------------------------------------------------- |
| **Scraper stack**           | Scrapling vs Firecrawl vs both, measured against login-walled content rather than argued      |
| **Fallback sources**        | Which platforms carry enough KL restaurant signal to keep the app alive when RedNote does not |
| **Ranking approach**        | Embedding similarity vs LLM re-rank vs hybrid, and what metric decides between them           |
| **Multilingual extraction** | How EN/MS/ZH code-switching degrades whichever extraction path is chosen                      |
| **Mobile delivery**         | PWA vs native shell, costed against the install friction it introduces                        |

Each maps to an open-decisions row in [`../../PRODUCT.md`](../../PRODUCT.md). **A file here is how a row gets closed.**

**Not here:** organizer or third-party material (`../../source/`), or a locked decision. Research informs a decision;
the decision lives in `../../TRD.md`.

---

## How To Write It

| Rule                        | Why                                                                        |
| --------------------------- | -------------------------------------------------------------------------- |
| **Lead with the finding**   | Then the evidence. Not a narrative of the search                           |
| **Cite every claim**        | Publisher, title, date, URL, date accessed. An uncited number is unusable  |
| **Separate interpretation** | From evidence, and say in the text which is which                          |
| **Mark gaps**               | `[ASSUMPTION]` for believed but unchecked, `[NEEDS SOURCE]` for unverified |
| **Tables over paragraphs**  | TitleCase headings                                                         |

Never present an assumption as a researched fact, or an AI-generated statement as user research.

**Measured beats argued, and this project has a specific version of that.** Platform-access questions are not settled by
reading — they are settled by a run with a number attached. A finding that says "Firecrawl should handle this" is worth
less than one that says "Firecrawl returned 3 of 50, all login walls, on 2026-08-28."

When a round is superseded, move it to `archive/round-N/` with a short note on **why it was cut**. A documented dead end
stops being repeated; a deleted one gets walked again — and with an arms-race data source, the same dead end is very
walkable twice.
