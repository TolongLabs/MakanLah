import type { Citation, Result } from './api'

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
      return 'Here because a post names this dish.'
    case 'text':
      return 'Here because those words appear in a post.'
    case 'semantic':
      return 'Here because it is close in meaning. No exact match on your words.'
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
