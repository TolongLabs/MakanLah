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

**Overridden 2026-08-30, by the owner, for `/discover` and the site footer: cards with a glassmorphism background.** The
tell above is glassmorphism _with no reason for depth_, and that qualifier is what the override satisfies rather than
ignores. #141's dotted ground gave the page a real texture, so a frosted card over it reads as a surface sitting above
the page; the same treatment over flat paper would still be the tell. Two rules keep it honest: the glass stays above
55% opacity so an excerpt never sits on a moving background, and it degrades to a solid `--paper-raised` under
`prefers-reduced-transparency` and where `backdrop-filter` is unsupported.

**And the rule it replaces: hairlines instead of cards.** Result rows were separated by a single `--rule` hairline. They
are cards now. The hairline rule still holds everywhere else.

**Every control and surface is solid or glass, never in between.** A partly-transparent background with nothing
filtering behind it is what makes a control look unfinished. `scripts/opaque-check.mjs` reads computed styles from a
real browser across both themes and fails on any element that is neither.

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

**Every token pair above clears WCAG AA (4.5:1) against the ground it sits on**, in both themes. `--ink-faint` was
originally `#8A8D7E`, which measured **3.39:1** on the input surface: legible-looking and non-compliant. Placeholder
text is exactly where that goes unnoticed, because a designer reading the mock already knows what the field is for.

**`--enamel` has exactly one job: marking where evidence comes from.** Deep enamel green-blue, the colour of old
kopitiam signage. If it appears on a button, a border, or a heading, that is a bug — the accent stops meaning "this is
sourced" the moment it decorates something.

Both themes are defined on tokens. Light is the base; dark redefines only the token values.

---

## Type

| Role          | Face                               | Why                                                                                      |
| ------------- | ---------------------------------- | ---------------------------------------------------------------------------------------- |
| **Chrome**    | Archivo → system sans              | Ours: nav, labels, buttons, venue names, metadata. Has character; not Inter, not Grotesk |
| **Testimony** | Newsreader → Noto Serif SC → serif | Theirs: post excerpts, and nothing else                                                  |
| **Numerals**  | Instrument Sans, tabular           | Distances and ranks must not shift width as they change                                  |

**CJK is not a fallback afterthought.** Chinese glyphs sit on a different vertical rhythm to Latin, so the testimony
style sets `line-height: 1.75` — loose enough that a mixed EN/MS/ZH sentence does not crowd — and never sets
`letter-spacing`, which mangles CJK.

Scale, in `rem`: `0.75 · 0.8125 · 0.875 · 1 · 1.25 · 1.625 · 2.25 · 3.25`, then a fluid display step of
`clamp(2.25, 6.4vw, 4.5)`. Venue name at `1.25`, excerpt at `1`, metadata at `0.8125`.

**The two steps above `2.25` were added when the landing page was built**, because a hero set at the old ceiling reads
as a paragraph rather than a headline, and scale contrast is most of what separates a designed page from a competent
one. Neither adds a value between existing steps. The display step is capped at `4.5rem`: past roughly `6rem` a page is
shouting rather than designing.

---

## Structure

**Hairlines, not cards.** Results are separated by a 1px `--rule`, not by shadow, radius or a filled panel. This is what
stops it looking like every other recommendation app, and it puts the ink budget on the words.

**Radius is near-zero and varies by role**, so it carries information instead of being a uniform coat: `0` on rules,
result rows and floating chrome, `2px` on anything you can type in or select, `999px` on the source chip only. Never one
radius on every surface.

The pill is the source chip's alone, and that is a rule with teeth: the wizard's floating island is the obvious second
place a rounded shape wants to appear, and it stays square. The moment a pill means "floating panel" as well as "this
came from somewhere", the accent shape stops carrying information.

**Alignment is left.** Centre alignment is reserved for genuinely symmetric moments — the empty state and nothing else.

**Spacing scale**, in `px`: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 72 · 96 · 144`. Nothing between. The last two are section
rhythm at desktop and are not used inside a component.

### Anatomy Of A Result

Ordered by visual weight, top to bottom:

1. **Rank numeral** — small, `--ink-faint`, hanging in the left margin. Honest: the list is ranked
2. **Venue name** — as written, in its own script. The largest chrome text on the row
3. **Metadata line** — area · distance · dishes, in `--ink-soft` at `0.8125rem`, separated by middots
4. **The excerpt** — serif, `--ink`, the largest block on the row. **This is the row's centre of gravity**
5. **Source chip** — `--enamel` on `--enamel-quiet`, naming the platform and author, linking to the live post

**Why sits between 3 and 4**, one line, in chrome type. It is our claim, so it must not be dressed as testimony. When
the API reports `match.basis`, a second faint line follows it saying why the entry is present at all. `semantic` is the
one that earns its place: it means nothing the user typed appears anywhere in the post, and admitting that is worth a
line.

### Corroboration Is A Layout, Not A Label

**When two platforms carry the same venue, both excerpts render side by side, each under its own source chip.** One
platform, and the single excerpt runs full width.

Nothing writes the words "two sources agree", because the reader can see it. This is the one place the design makes an
argument Google Maps structurally cannot: two strangers, two platforms, often two languages, the same verdict. A caption
asserting it would be weaker than the thing itself.

Two posts from **one** platform is not corroboration. It is one source saying it twice, and it renders as one excerpt.
`evidenceOf()` in `web/src/evidence.ts` is the single derivation, shared by the row, the venue page and the mascot, so
the face and the layout can never disagree about what the corpus holds.

### A Count Must Match What Is Rendered, Or Name What It Counts

**Four bugs in this project were one bug.** `#87` stamped "Corroborated by two independent sources" on cards rendering
one testimony. `#111` counted dead citations toward a number whose whole meaning was that a reader could go and check
them. `#153` printed "1 post" on a venue where three different people had written, because a Maps URL is not a post
identity. And the sentiment line read "Of the 3 posts here" beside a card that shows at most two excerpts and a dialog
that deliberately renders dead ones.

Every one was **true by its own rule and false as English**, which is why unit tests passed through all four.

> **Any count a surface renders must either equal the number of items visible on that surface, or name the property it
> counts.** `3 posts still open` passes by naming. `Of the 3 posts here` fails, because "here" is a claim about the page
> and the page shows something else.

The second half is the usable one, because the counts here legitimately differ from what renders: excerpts are capped at
two per card, citations are trimmed to `per_venue` before they ship, and dead posts are shown but not counted. **The fix
is never to hide the record to make a number true** — a stamp reading four posts over a page showing one invites exactly
the doubt the stamp exists to answer. Name the property instead.

The columns are keyed to the **container**, not the viewport. The same pair renders inside a full-width result row and
inside the landing page's specimen, which is half as wide; a viewport query splits the specimen into two columns too
narrow to read Chinese in.

---

## Language

**TitleCase** for nav items, buttons, section headings, card titles, table headers, tab labels, menu items, modal titles
and form labels. **Sentence case** for body copy, helper text, placeholders, tooltips, errors, empty states and toasts.
`Find Food`, but `We could not reach that source, showing what we have.`

**Never translate a venue name or a dish in the UI.** Both render in the script the writer used. The interface may add a
gloss beside an excerpt; it may never replace one.

---

## Imagery

**The default is none, and that default is load-bearing.** A generated or stock photograph of food, placed anywhere a
pick's evidence appears, would be a fabricated image on the one screen whose entire claim is that nothing here is
fabricated. No image may sit inside, beside, or above a cited result.

Three exceptions, and the reasoning is the same in each: none of them can be mistaken for evidence.

| Asset                      | Where                              | Why It Is Allowed                                                                                    |
| -------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **The mark**               | Icon, favicon, share card          | A quotation mark in `--enamel` on `--paper`. It depicts nothing and claims nothing                   |
| **The closing photograph** | Landing page, final section only   | Atmosphere in a section that names no venue. No signage, no faces, no identifiable place, no dish    |
| **The mascot**             | `/taste`, and the `/discover` rail | A rendered character, not a photograph. It reports evidence strength and is dismissible              |
| **The map**                | The All Sources dialog, once       | Depicts a location, not an opinion. Makes no claim about the food, which is all the citations attest |

**The map is a fourth exception and the reasoning is the same as the other three: it cannot be mistaken for evidence.**
It shows where a place is, not whether the food is good, and whether the food is good is the only thing the citations
are evidence _of_. **The product already stakes more on those coordinates than the map does** — every card prints a
distance from the same geocode and the whole list is ordered by it, so if the pin is wrong the distance was already
wrong. The map makes an existing claim visible rather than adding a new one.

**It is served from our side, never fetched from a tile server by the browser.** The image is pulled once per venue at
ingestion and stored. Rendering OSM rasters client-side was built, worked, and was reverted: OSM's tile usage policy is
explicit about bulk use by applications, and a tile request per viewer per venue is a rate limit on infrastructure we
neither own nor pay for. Attribution travels with the image wherever it is served from.

**The mark is a quotation mark, not a bowl.** Every food app is a bowl. The differentiator here is that somebody was
quoted, so the mark is the quote. It resolves at 16px and uses exactly two colours, `#0B6B5E` and `#F7F7F4`, with no
third value anywhere in the file.

### The One Inversion

The landing page's closing section is full bleed over a dark photograph and is **the only place the page inverts**. It
is allowed once, deliberately, and it owns its own colours rather than reading tokens, so it does not flip with the
theme and cannot be mistaken for a section that lost its background.

Two things are required of it, and both are measured rather than assumed:

- **A scrim.** Text contrast over a photograph otherwise depends on the photograph. The gradient guarantees the floor,
  and the rendered pixels behind every text box measure **7.0:1 or better** at both widths
- **Left alignment inside a right-hand block.** Pushing each child right individually shrinks every one to its own text
  width, which reads as right-aligned text. One block moves; its contents do not

**A DOM walk cannot measure this section.** Neither an `<img>` nor an `::after` scrim is a `background-color`, so a
contrast checker that climbs the tree finds the body's paper and reports invisible text. It has to be sampled from
rendered pixels, which is the same lesson as [`AUTONOMY.md`](AUTONOMY.md) on verifying a fix with its own definition.

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

## The Landing Page Is Allowed To Sell

It is the one surface that shouts, and the constraint on it is not volume but truth. **Every boast is a number this
repository can produce**, because the pitch is "nothing here is invented" and a page opening with an invented statistic
refutes itself above the fold.

| Allowed                                                           | Not allowed                                                |
| ----------------------------------------------------------------- | ---------------------------------------------------------- |
| `1,507 posts` — read live from `/health`                          | "Loved by thousands" — there are no thousands              |
| `247 places` — same                                               | "10x faster" — than what, measured how                     |
| `0 picks we made up` — `rank.py` enforces it                      | "AI-powered" — says nothing and sounds like everything     |
| "Loved By Malaysians" — of the **places**, and 1,507 posts say so | The same words aimed at the app, which nobody has used yet |

The display scale is capped at **5.5rem**, under the 6rem ceiling: past that a two-line headline stops being a sentence
and becomes a poster to decode. `h-display` is landing-only — the product's own screens stay on the quieter scale,
because a dashboard that shouts cannot be read twice.

**Reveals enhance a default that is already visible.** No section is hidden waiting for an observer. This was shipped
wrong once, with a comment stating the rule directly above CSS that broke it, and every section below the hero rendered
blank.

---

## The Companion

She hosts the onboarding wizard: a Live2D character in the rail, a speech bubble carrying the question she is asking,
and a voice toggle. The register is fun and cute, and it is the one place on the site allowed to be.

**She is decoration, and the whole design rests on her staying that way.** Every other surface in this product is bound
to the citation trail. She is bound the opposite way: she sees no corpus row, names no venue, and makes no claim, so
there is no evidence for her to get wrong. `makanlah/companion.py` drops any line that names a place, recommends, rates,
quotes a price or carries a URL, and falls back to a scripted one. **A cheerful sentence that recommended a restaurant
would be exactly the hallucination-with-a-rating this product exists to not ship.**

| Rule                          | Why                                                                                                                                                                                                            |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **The bubble is never empty** | The scripted line is on screen in the frame the step changes. The server's line replaces it when it lands                                                                                                      |
| **She never speaks unasked**  | Chrome and Safari refuse `speak()` before a user gesture, so a voice defaulting on is silent on step one and startling on step two. The toggle is the gesture                                                  |
| **The choice sticks**         | Persisted per browser. Nobody should have to switch a voice off twice                                                                                                                                          |
| **One line at a time**        | Every `speak()` cancels the last. Stepping quickly used to queue four questions and answer the last one long after the user moved on                                                                           |
| **She is gone below 56rem**   | Not hidden — never mounted. `display: none` alone still downloaded 500 KB of pixi and allocated a WebGL context for a 1×1 canvas. Her bubble stays                                                             |
| **The line is English**       | It is read by a browser speech synthesiser. A Chinese glyph in an English voice is skipped or spelled out letter by letter, and the corpus excerpts beside her are the ones that must stay in their own script |

**The mouth is an approximation and the code says so.** The Web Speech API exposes word boundaries, not amplitude or
visemes, so a real lip sync is not available to ask for. An oscillation timed to actual speech reads as talking; a still
face beside a voice reads as broken.

**She is not the results mascot.** `Mascot.tsx` reports evidence strength on `/discover` and is bound to what the corpus
holds. `Companion.tsx` asks the wizard's questions and is bound to nothing. They share a stage and share no job.

---

## The Chrome Is Ours

Scrollbars, text selection, focus rings, `accent-color`, the caret, Chrome's yellow autofill, tooltips and the nav
drawer. These are the parts most often left at the operating system default, and they are the parts that give away that
a page is a document rather than a product. **They also do not follow a theme on their own**: a Windows scrollbar stays
light grey on a dark page.

`scripts/chrome_check.mjs` asserts each of them in **both** schemes, and the assertion is that the value _moves_ rather
than that it exists. That is what caught a nested `:root` inside `:root` — a descendant selector that never matches —
which had left the **entire dark theme dead** while every token still resolved to something.

**Three states, never two.** Auto, Light, Dark. A two-state toggle cannot express "follow my machine", so the first tap
silently takes it from somebody whose laptop flips at sunset.

---

## Testing Before Anything Ships

Nothing visual is done until all four hold, and they get stated in the report:

1. `impeccable critique` has run, findings addressed or consciously declined
2. The `design-taste-frontend` pre-flight check passes
3. Viewed at **360px**, not only in a wide editor pane
4. TitleCase checked against **rendered** text, not source

**Three and four are measurable, so measure them.** Driving headless Chrome over every route and reading back the
computed styles catches what a screenshot does not: contrast against the actual composited background, tap targets under
24px, and horizontal overflow. It found a real one that reading the CSS would not have. A source chip refuses to wrap,
grid and flex items default to `min-width: auto`, and one long author handle was therefore setting the minimum width of
the whole result row: at 390px the document measured 399.

**A measuring script is code and can be wrong.** The same pass first reported the light theme failing contrast at
1.16:1, which would have been invisible text. It was the checker: `color-mix()` serializes as `color(srgb 0.96 …)`, and
the parser read 0-to-1 floats as 0-to-255. Confirm a finding against the rendered page before changing a token to
satisfy it.

**Test every string-bearing surface with all three languages, never lorem ipsum.** A Malay place name runs longer than
its English gloss and Chinese glyphs have different metrics; a layout proven only in English is not proven.
