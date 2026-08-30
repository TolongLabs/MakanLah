import type { Citation, Result, Venue } from './api'
import { count, dishLine, distance } from './format'

/**
 * How much evidence stands behind a pick. This is the one derivation shared by the
 * result row, the venue page and the mascot, so the face and the layout can never
 * disagree about what the corpus actually holds.
 */
export type Evidence = 'corroborated' | 'single' | 'none'

/**
 * Only a citation that can be opened counts. An excerpt with no post behind it is the
 * thing this product exists not to show.
 *
 * Deduped by URL as well: the corpus can carry the same post twice for one venue, and
 * showing it twice inflates the apparent evidence behind a pick, which is the one
 * number on the page nobody should be able to inflate by accident. It also fixes the
 * duplicate React key that surfaced on /discover, but that was the symptom.
 */
export function citable(citations: Citation[]): Citation[] {
  const seen = new Set<string>()
  return citations.filter((c) => {
    if (!c.post_url || seen.has(c.post_url)) return false
    seen.add(c.post_url)
    return true
  })
}

/** Two posts from one account is one person saying it twice. Corroboration means two
    platforms, which is the part a single platform going dark cannot fake. */
/** Citations a reader can actually open: deduped by post, and not measured dead.
    `dead` is tri-state and only `true` counts against a citation -- `null` is
    unchecked, and treating unchecked as dead deletes real testimony. */
export function openable(citations: Citation[]): Citation[] {
  return citable(citations).filter((c) => c.dead !== true)
}

/**
 * #111. This counted a DEAD post toward "Two sources", so the companion could say
 * "Two platforms carry this one, written by different people" beside a card
 * rendering exactly one testimony -- because `leadPair` had correctly refused the
 * dead citation that `evidenceOf` had just counted. Two functions in this file
 * disagreeing about what a source is.
 *
 * Measured on prod: 7 of 48 results across 15 queries overclaimed. Latent only
 * because Discover passes the top pick alone, and a 15% base rate makes that a
 * question of which query rather than whether.
 */
export function evidenceOf(result: Result): Evidence {
  const cited = openable(result.citations)
  if (!cited.length) return 'none'
  return new Set(cited.map((c) => c.platform)).size >= 2 ? 'corroborated' : 'single'
}

/** The lead excerpt, then the best excerpt from a different platform. Returns one
    entry when nothing corroborates it, and never two from the same source.

    **A post that no longer resolves is not corroboration.** Measured on prod: 阿喜
    and 三美肉骨茶 lead with a live Google Maps citation and carry nothing but dead
    RedNote ones, so the second chip -- chosen only for being a different platform --
    linked the reader to a wall on 3 of 5 cards. The server's `prefer_live` had done
    its half correctly and the lead was right on 5 of 5; this is the other half.

    `dead` is tri-state and the distinction matters: `true` is measured dead, `null`
    or absent is never checked. Unchecked counts as live, because collapsing unknown
    into dead deletes real evidence -- the 兴记肉骨茶 citation was exactly that case
    and re-probing resolved it live. */
export function leadPair(citations: Citation[]): Citation[] {
  const cited = citable(citations)
  const withText = cited.filter((c) => c.excerpt?.trim())
  const alive = (c: Citation) => c.dead !== true
  // A dead lead should be unreachable -- the API drops an entry whose every citation
  // is dead -- but if one arrives, showing it beats showing nothing. A card that
  // cannot say where it came from is not a card this product is allowed to render.
  const lead = withText.find(alive) ?? withText[0] ?? cited[0]
  if (!lead) return []
  const second = withText.find((c) => c.platform !== lead.platform && alive(c))
  return second ? [lead, second] : [lead]
}

/**
 * Why this entry is in the list at all. docs/TRD.md replaced the old `score` with this
 * for a reason: a cosine a reader cannot interpret is not an explanation, and
 * `semantic` in particular is worth admitting to, because it means nothing the user
 * typed actually appears anywhere in the post.
 */
export function basisLine(basis: string | undefined): string | null {
  switch (basis) {
    case 'dish':
      return 'A post about this place names that dish outright, which is the strongest signal the corpus carries.'
    case 'text':
      return 'Your words appear in the writing about this place, though no dish was tagged.'
    case 'semantic':
      // Deliberately blunt, and #140 is why: `canonical_for_query` resolves only
      // curated dish names, so every ingredient word -- chicken, crab, noodle --
      // routes here by construction. A reader looking at a Hainanese chicken rice
      // shop under a `crab` query deserves to be told this is the weak lane.
      return 'No post here uses your words. This one is only near them in meaning, which is a weaker reason than a named dish.'
    default:
      return null
  }
}

/**
 * The basis shared by every entry, if they share one. A list where all ten rows say
 * "here because it is close in meaning" has printed the same sentence ten times and
 * told the reader nothing they could not get from one. Hoisted, it is a real caveat
 * about the whole list; repeated, it is furniture.
 */
export function sharedBasis(results: { match?: { basis?: string } }[]): string | undefined {
  const bases = results.map((r) => r.match?.basis)
  const first = bases[0]
  if (!first || bases.some((b) => b !== first)) return undefined
  return first
}

export function listBasisLine(basis: string | undefined): string | null {
  switch (basis) {
    case 'dish':
      return 'Every one of these is a post naming that dish.'
    case 'text':
      return 'Every one of these has your words in a post.'
    case 'semantic':
      return 'None of these match your words exactly. They are the closest in meaning the corpus has.'
    default:
      return null
  }
}

export type MascotMood = 'curious' | 'pleased' | 'skeptical' | 'concerned'

/** Where the page is, which the mood alone cannot say: nothing searched yet,
    searched and empty, or holding picks. */
export type CompanionPhase = 'idle' | 'empty' | 'picks'

/**
 * Binds the mascot to evidence strength rather than to sentiment, per issue #11.
 * A face that only ever smiles has stopped carrying information, so `degraded`
 * outranks everything: if the corpus is stale, no pick gets a pleased reading.
 */
export function moodFor(evidence: Evidence | null, degraded = false): MascotMood {
  if (degraded) return 'concerned'
  if (evidence === null) return 'curious'
  if (evidence === 'corroborated') return 'pleased'
  if (evidence === 'single') return 'skeptical'
  return 'concerned'
}

/**
 * `phase` separates two states the `curious` mood used to collapse.
 *
 * "Nothing has been searched yet" and "a search ran and came back with nothing"
 * are different facts, and reading them as one told a user who had just answered
 * four onboarding questions to go and answer four onboarding questions -- directly
 * under a line reciting the answers they had given. Two elements on one screen
 * contradicting each other, and the companion's was the false one.
 *
 * Same family as the empty state that blamed the corpus for a radius (#82): a
 * surface asserting a reason it had not checked.
 */
export function readingFor(mood: MascotMood, phase: CompanionPhase = 'idle'): { read: string; note: string } {
  switch (mood) {
    case 'pleased':
      return { read: 'Two sources', note: 'Two platforms carry this one, written by different people.' }
    case 'skeptical':
      return { read: 'One source', note: 'Only one post backs this. Worth a look, not a promise.' }
    case 'concerned':
      return { read: 'Thin evidence', note: 'A source was unreachable at the last refresh, so this may be incomplete.' }
    default:
      return phase === 'empty'
        ? { read: 'Nothing to read', note: 'That search came back with nothing I can back up.' }
        : { read: 'Listening', note: 'Answer the four questions and this fills in.' }
  }
}

/**
 * Where a citation's link should actually go.
 *
 * A Google Maps "post" is a review, and reviews have no individual URL, so the
 * corpus stores a **name search** -- `maps/search/?api=1&query=<name> Kuala
 * Lumpur`. For a name like `ALVA` or `一见钟情` that can land on the wrong place
 * entirely, and it did on 23 of 23 venues in UAT.
 *
 * The venue's own `maps_url` is built server-side and carries `query_place_id`
 * when the corpus has one, which is exact. Same destination, no guessing. The
 * fallback stays the citation's own URL, because a venue without a place_id has
 * nothing better and a RedNote post URL is already exact.
 */
export function citationHref(citation: Citation, venue?: { maps_url?: string; place_id?: string | null }): string {
  if (citation.platform === 'google_maps' && venue?.maps_url?.includes('query_place_id=')) return venue.maps_url
  return citation.post_url
}

/**
 * May this venue be called corroborated?
 *
 * Two excerpts from two platforms USED to be enough, and it was wrong in a way UAT
 * caught: one listicle backed three of the top five picks and every card claimed
 * "Corroborated by two independent sources". True per card by the old rule, false
 * as English. Two mentions from one author on one post are one voice however many
 * platforms carry it.
 *
 * Until the API sends `corroboration`, this falls back to the layout rule -- but it
 * requires two DISTINCT post URLs, which is the part the old check never made.
 */
export function independentlyBacked(result: Result): boolean {
  const c = result.venue.corroboration
  // TWO DISTINCT POSTS IS THE FLOOR, and then two distinct VOICES.
  //
  // `authors >= 2` alone was wrong and inverted the claim: Google Maps citations
  // carry `author_handle: null`, so an anonymous reviewer never counts. The stamp
  // ended up rewarding RedNote-only venues and withholding itself from four venues
  // backed by BOTH a RedNote post and a Maps review -- while the companion beside
  // it said "Two platforms carry this one, written by different people".
  //
  // A Maps reviewer we cannot name is still not the person who wrote the RedNote
  // post, so two platforms is two voices even when one of them is anonymous.
  // `posts >= 2` is what actually fixes #87: one listicle backing three venues
  // gives each of them one post, and one post is never corroboration.
  if (c) return c.posts >= 2 && (c.authors >= 2 || c.platforms >= 2)
  const posts = new Set(result.citations.map((x) => x.post_url))
  const platforms = new Set(result.citations.map((x) => x.platform))
  return posts.size >= 2 && platforms.size >= 2
}

/** Venues in this same response that lean on the same post as this citation. */
export function sharedPostCount(citation: Citation): number {
  return citation.shared_with?.length ?? 0
}

/**
 * What the corpus cannot answer, said as a sentence rather than a key.
 *
 * UAT, Malay persona: `tempat makan halal untuk keluarga` returned a list under
 * **"None of these match your words exactly"** — a RELEVANCE disclaimer standing
 * in for a COVERAGE one. "We do not hold halal information" and "these are not
 * exact matches" are completely different sentences, and she only ever saw the
 * second. `coverage_gaps` was in the payload the whole time and nothing rendered
 * it, so the page stayed silent about the one thing she came to find out.
 *
 * The wording is deliberately about US and not about the venues. The corpus
 * holding nothing is a fact about the corpus; whether a restaurant is halal is a
 * fact about the restaurant, and this line may not be read as either answer.
 */
export function coverageLine(gap: string): string {
  switch (gap) {
    case 'halal':
      return 'We hold no halal information. Nothing here is a halal listing, and no absence below means no.'
    default:
      // Named rather than dropped. A gap the client has no copy for is still a
      // gap, and silently ignoring an unknown key is how a corpus limitation
      // becomes invisible the moment somebody adds a second one.
      return `We hold no ${gap} information for any of these.`
  }
}

/** What a post about THIS venue actually mentions, as a sentence. Never a claim
    about the venue: somebody writing 清真友好 is a person's word, not a
    certification, and the row says which of those it is. */
export function mentionLine(gap: string): string {
  switch (gap) {
    case 'halal':
      return 'Somebody writing about this one mentions halal. Read it below and judge for yourself.'
    default:
      return `Somebody writing about this one mentions ${gap}.`
  }
}

/**
 * How the posts about one venue actually split, as counts.
 *
 * **`livePosts` is not optional and the reason is measured.** `sentiment` counts
 * MENTION rows, and a mention is not a post: across ten live `nasi lemak` results,
 * nine disagreed with the card's own post count, several by nine to one. Village
 * Park reads three openable posts and fifteen sentiment entries. Printed naively
 * this card would say "1 post" in its subtitle and "All 9 posts positive" four lines
 * below it — self-contradicting, and inflating the evidence behind a pick in exactly
 * the way #111 did when dead citations were counted toward corroboration.
 *
 * So the line renders only when the two counts describe the same set. That is a real
 * invariant rather than a workaround: a sentiment breakdown the reader cannot trace
 * to posts they can open is the unverifiable assertion this product exists not to
 * make. It lights up on its own once the API filters mentions to live posts (#143).
 *
 * **Negative leads wherever it appears.** `makanlah` buckets at `positive >= 0.6`
 * and `negative <= -0.2`, deliberately asymmetric, so a single negative is somebody
 * with a real complaint rather than a mild review rounded down. Burying that under a
 * positive majority is the one thing this line must not do.
 *
 * **Unanimity prints too**, and that reversed an earlier call. The first draft stayed
 * silent when every post agreed, reasoning that a label reading "positive" everywhere
 * discriminates nothing. Measured, the reasoning was backwards: 163 of 186
 * multi-mention venues span more than one bucket, so agreement is the 12% case and is
 * the informative one.
 *
 * Silent on a single mention: with one post the excerpt directly below IS the
 * sentiment, and labelling it restates what the reader is already looking at.
 */

/**
 * **Off, and this is the second thing that had to be true before the line could
 * ship.** The first was that the counts describe the same posts, which #147 fixed —
 * production now reads 33/33 agreeing on an independent query sample, and the gate
 * below correctly lit up. The second is that the BUCKETS ARE RIGHT, and they are
 * not.
 *
 * Measured across four queries, of the ten venues carrying a negative bucket,
 * **eight contain no negative language whatsoever** while carrying positive
 * language. Confirmed by eye rather than only by keyword, which matters because a
 * crude instrument can manufacture its own finding:
 *
 * - `王美记 Restoran Wong Mei Kee` buckets **0 positive, 2 negative**. Its excerpts
 *   say "Siew Yok 烧肉 deserves 5 stars with thick meat and crispy surface" and
 *   "definitely worth checking out".
 * - `山海 Shan hai udon` buckets one negative off a review whose only complaint is
 *   that a yuzu drink "taste quite weird", beside "Very delicious" and "Love their
 *   tempura".
 * - Three separate bak kut teh shops bucket 0 positive / 1 negative on excerpts
 *   carrying only praise.
 *
 * `negative <= -0.2` is catching mild qualification, and this module then renders it
 * as "critical" — a verdict about a real restaurant that the posts do not support.
 * That is the exact failure this product exists not to commit.
 *
 * **Rendering only the positive half is NOT the fix and would be worse**: suppressing
 * unfavourable readings while printing favourable ones biases every card toward good
 * news. Either the split is trustworthy and both halves show, or neither does.
 *
 * One line to flip once the threshold is right. Tracked as #149.
 */
const CLASSIFICATION_TRUSTED = false
export function sentimentLine(s: Venue['sentiment'], livePosts: number): string | null {
  return CLASSIFICATION_TRUSTED ? sentimentPhrase(s, livePosts) : null
}

/**
 * The wording, separated from the decision to show it.
 *
 * Kept exported and under test while the line is held. Copy that is switched off and
 * untested rots quietly, and the whole point of a one-line flag is that flipping it
 * ships something already known to be correct.
 */
export function sentimentPhrase(s: Venue['sentiment'], livePosts: number): string | null {
  if (!s) return null
  const total = s.positive + s.mixed + s.negative
  if (total < 2) return null
  // Different units, so the breakdown is not about the posts this card can show.
  if (total !== livePosts) return null

  if (s.negative > 0) {
    const rest: string[] = []
    if (s.positive > 0) rest.push(`${s.positive} positive`)
    if (s.mixed > 0) rest.push(`${s.mixed} mixed`)
    const tail = rest.length > 0 ? `, ${rest.join(', ')}` : ''
    return `${s.negative} of ${count(total, 'post')} critical${tail}.`
  }
  if (s.mixed === 0) return `All ${count(total, 'post')} positive.`
  if (s.positive === 0) return `All ${count(total, 'post')} mixed.`
  return `${s.positive} of ${count(total, 'post')} positive, ${s.mixed} mixed.`
}

/** One fact in a result's why-row. `lead` marks the answer to "why is this here",
    which is typeset apart from the context tokens that follow it. */
export type WhyToken = { key: string; text: string; lead?: boolean }

/**
 * Why this result is on screen, as facts rather than prose.
 *
 * The information was always here. `basisLine` has said "Here because a post names
 * this dish" since the first version — as the EIGHTH line of the card, in the same
 * grey as two neighbouring sentences that answer different questions. The owner read
 * his own results page and reported that nothing said why anything was there. He was
 * right about the experience and the data was never the problem: an answer formatted
 * like a footnote is not an answer.
 *
 * So it moves to the subtitle, absorbs the metadata line that used to sit there, and
 * gains the corroboration counts. One row replaces three and says more than all of
 * them did.
 *
 * NO SIMILARITY NUMBER, EVER, and this is now measured rather than assumed.
 * `api.ts` has always said `similarity` is never rendered (issue #7). Sampling 35
 * live results across five queries: **15 of them carry `basis: 'dish'` with
 * `similarity: 0.0`** — 63% of every dish match in the sample. 興记肉骨茶 is the
 * clearest case, a strong lexical hit the vector lane simply never saw. Printed as a
 * percentage that is "0% match" on one of the best answers the corpus has.
 */
export function whyRow(result: Result): WhyToken[] {
  const tokens: WhyToken[] = []
  const { venue, match } = result

  const matched = matchToken(match)
  if (matched) tokens.push({ key: 'match', text: matched, lead: true })

  // Live citations only — `add_corroboration` already excludes the dead ones, which
  // is why this can be trusted next to a stamp that makes the same claim.
  const c = venue.corroboration
  if (c && c.posts > 0) {
    // The people clause only where it MEANS something. "1 post, 1 person" says the
    // same thing twice, and 12 of the 35 sampled results carry `authors: 0` because
    // Google Maps reviewers are anonymous — no card ever prints "0 people".
    const people = c.authors >= 2 ? `, ${count(c.authors, 'person', 'people')}` : ''
    tokens.push({ key: 'evidence', text: `${count(c.posts, 'post')}${people}` })
  }

  const far = distance(result.distance_m)
  if (far) tokens.push({ key: 'distance', text: far })

  // Absent on 19 of 35 sampled results, so it is the last token and never load-bearing.
  if (venue.area) tokens.push({ key: 'area', text: venue.area })

  return tokens
}

function matchToken(match: Result['match']): string | null {
  switch (match?.basis) {
    case 'dish':
      // `match.dish` is null on every semantic result and populated on dish ones, so
      // the fallback is a guard rather than a case that fires.
      return match.dish ? `Names ${match.dish}` : 'Names the dish'
    case 'text':
      return 'Your exact words'
    case 'semantic':
      return 'Close in meaning'
    default:
      return null
  }
}

/**
 * Everything the fact row had no room for, behind a per-card disclosure.
 *
 * "More informative AND briefer at once" is a contradiction taken literally, and
 * progressive disclosure is the only honest way to serve both halves: four lines by
 * default, the rest one tap away. What it must never be is a control that opens onto
 * nothing, so this returns an empty list where the row already said everything, and
 * the card renders no disclosure at all.
 */
export function whyDetail(result: Result, sharedWith = 0): string[] {
  const lines: string[] = []
  const { venue, match } = result

  const basis = basisLine(match?.basis)
  if (basis) lines.push(basis)

  // Only where it ADDS to the row. The row already carries the post count, and the
  // people count whenever there are two or more, so a line repeating both back is
  // the same buried-restatement this whole rework exists to remove. More than one
  // platform is the one fact the row has no room for.
  const c = venue.corroboration
  if (c && c.posts > 0 && c.platforms > 1) {
    const who = c.authors > 0 ? ` by ${count(c.authors, 'person', 'people')}` : ''
    lines.push(`${count(c.posts, 'post')}${who}, across ${count(c.platforms, 'platform')}.`)
  }

  const feeling = sentimentLine(venue.sentiment, venue.corroboration?.posts ?? 0)
  if (feeling) lines.push(feeling)

  // The matched dish is already the lead token, so repeating it here is noise. Folded
  // rather than translated: the corpus holds 肉骨茶 and the query said bak kut teh,
  // and both are what people actually wrote.
  const named = match?.dish?.trim().toLowerCase()
  const others = venue.dishes.filter((d) => d.trim().toLowerCase() !== named)
  const also = dishLine(others, 5)
  if (also) lines.push(`Also serves: ${also}`)

  if (sharedWith > 0) {
    lines.push(
      `One of these posts also backs ${sharedWith === 1 ? 'another pick' : `${sharedWith} other picks`} in this list.`
    )
  }

  return lines
}
