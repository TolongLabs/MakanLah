# DESIGN — The Visual System

**Owns the design system**: palette, type pairing, radius and border treatment, spacing scale. `AGENTS.md` owns code
conventions; this file owns how it looks. Where they disagree about a screen, this file wins.

> **The premise.** A hungry person decides in under two minutes, and **the evidence is the product**. A layout that
> treats the cited post as a footnote has inverted the thing being sold. Every decision below follows from that one
> sentence.

---

## The Core Idea: Testimony, Not Cards

The thing on screen is **somebody's writing about a restaurant**, not a database row with a quote attached.

So the excerpt carries the most visual weight on a result, and the venue name is the **label on the testimony** rather
than a headline with a citation beneath it. This is the single structural decision the whole system serves, and it is
what keeps the design from becoming a generic listings app.

**The device that carries it: chrome is set in a grotesque, testimony is set in a serif.** That contrast is not
decoration — it tells you at a glance which words are ours and which are the writer's. Nothing else in the interface is
allowed to use the serif.

---

## What This Must Not Look Like

From [`../AGENTS.md`](../AGENTS.md#design-standards). Named here because a tell is easier to avoid when it is written
down:

Warm cream ground with a serif display face and a terracotta accent · near-black with one acid green or vermilion pop ·
a purple-to-blue gradient hero on white · Inter or Space Grotesk as the safe default · everything centre aligned · one
large corner radius on every surface · a coloured rail down the side of a rounded card · numbered markers on content
that is not a sequence · three items in a list because three feels balanced · glassmorphism with no reason for depth · a
dark dashboard with neon chart lines.

**Numbering is the one to watch here.** A shortlist genuinely is ranked, so numbering results is honest and stays. It
must never spread to anything unordered.

---

## Palette

Paper and ink, with **one** accent that is reserved for a single job. The ground is cooled with green-grey rather than
warmed toward cream, specifically to avoid the cream-and-terracotta tell.

| Token            | Light     | Dark      | Used For                                                   |
| ---------------- | --------- | --------- | ---------------------------------------------------------- |
| `--paper`        | `#F7F7F4` | `#12130F` | Page ground                                                |
| `--paper-raised` | `#FFFFFF` | `#1A1B16` | Input surfaces only. Not a card                            |
| `--ink`          | `#16180F` | `#F2F2EC` | Body text, venue names                                     |
| `--ink-soft`     | `#5C5F52` | `#9B9E90` | Metadata: area, distance, author, date                     |
| `--ink-faint`    | `#8A8D7E` | `#6E7164` | Placeholders, disabled, dividers-as-text                   |
| `--rule`         | `#D9DAD0` | `#2C2E25` | Hairlines. The primary separator in the whole system       |
| `--enamel`       | `#0B6B5E` | `#3FA697` | **The accent.** Source attribution and citation links only |
| `--enamel-quiet` | `#E3EFEC` | `#15302C` | The accent's tint, for the source chip ground              |
| `--warn`         | `#8A5A00` | `#D9A441` | Degraded state, stale corpus                               |

**`--enamel` has exactly one job: marking where evidence comes from.** Deep enamel green-blue, the colour of old
kopitiam signage. If it appears on a button, a border, or a heading, that is a bug — the accent stops meaning "this is
sourced" the moment it decorates something.

Both themes are defined on tokens. Light is the base; dark redefines only the token values.

---

## Type

| Role          | Face                               | Why                                                                                      |
| ------------- | ---------------------------------- | ---------------------------------------------------------------------------------------- |
| **Chrome**    | Instrument Sans → system sans      | Ours: nav, labels, buttons, venue names, metadata. Has character; not Inter, not Grotesk |
| **Testimony** | Newsreader → Noto Serif SC → serif | Theirs: post excerpts, and nothing else                                                  |
| **Numerals**  | Instrument Sans, tabular           | Distances and ranks must not shift width as they change                                  |

**CJK is not a fallback afterthought.** Chinese glyphs sit on a different vertical rhythm to Latin, so the testimony
style sets `line-height: 1.75` — loose enough that a mixed EN/MS/ZH sentence does not crowd — and never sets
`letter-spacing`, which mangles CJK.

Scale, in `rem`: `0.75 · 0.8125 · 0.875 · 1 · 1.25 · 1.625 · 2.25`. Venue name at `1.25`, excerpt at `1`, metadata at
`0.8125`.

---

## Structure

**Hairlines, not cards.** Results are separated by a 1px `--rule`, not by shadow, radius or a filled panel. This is what
stops it looking like every other recommendation app, and it puts the ink budget on the words.

**Radius is near-zero and varies by role**, so it carries information instead of being a uniform coat: `0` on rules and
result rows, `2px` on the search field, `999px` on the source chip only. Never one radius on every surface.

**Alignment is left.** Centre alignment is reserved for genuinely symmetric moments — the empty state and nothing else.

**Spacing scale**, in `px`: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 72`. Nothing between.

### Anatomy Of A Result

Ordered by visual weight, top to bottom:

1. **Rank numeral** — small, `--ink-faint`, hanging in the left margin. Honest: the list is ranked
2. **Venue name** — as written, in its own script. The largest chrome text on the row
3. **Metadata line** — area · distance · dishes, in `--ink-soft` at `0.8125rem`, separated by middots
4. **The excerpt** — serif, `--ink`, the largest block on the row. **This is the row's centre of gravity**
5. **Source chip** — `--enamel` on `--enamel-quiet`, naming the platform and author, linking to the live post

**Why sits between 3 and 4**, one line, in chrome type. It is our claim, so it must not be dressed as testimony.

---

## Language

**TitleCase** for nav items, buttons, section headings, card titles, table headers, tab labels, menu items, modal titles
and form labels. **Sentence case** for body copy, helper text, placeholders, tooltips, errors, empty states and toasts.
`Find Food`, but `We could not reach that source, showing what we have.`

**Never translate a venue name or a dish in the UI.** Both render in the script the writer used. The interface may add a
gloss beside an excerpt; it may never replace one.

---

## Degraded And Empty States

Honesty is a design requirement here, not a nicety, because [`PRD.md`](PRD.md#fr6--honest-degradation) makes it one.

| State                           | Shows                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------ |
| **Corpus stale or source down** | A `--warn` line above the results. Results still render                                    |
| **No results**                  | Centre aligned. Says what was searched and offers a wider radius. Never a shrug            |
| **Location refused**            | Falls back to KL-wide and says so in one sentence. **Never a dead end**                    |
| **API unreachable**             | Says the corpus is unavailable and what to do. Never an empty list dressed as zero results |

---

## Testing Before Anything Ships

Nothing visual is done until all four hold, and they get stated in the report:

1. `impeccable critique` has run, findings addressed or consciously declined
2. The `design-taste-frontend` pre-flight check passes
3. Viewed at **360px**, not only in a wide editor pane
4. TitleCase checked against **rendered** text, not source

**Test every string-bearing surface with all three languages, never lorem ipsum.** A Malay place name runs longer than
its English gloss and Chinese glyphs have different metrics; a layout proven only in English is not proven.
