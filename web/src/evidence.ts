import type { Citation, Result } from './api'

/**
 * How much evidence stands behind a pick. This is the one derivation shared by the
 * result row, the venue page and the mascot, so the face and the layout can never
 * disagree about what the corpus actually holds.
 */
export type Evidence = 'corroborated' | 'single' | 'none'

/** Only a citation that can be opened counts. An excerpt with no post behind it is
    the thing this product exists not to show. */
export function citable(citations: Citation[]): Citation[] {
  return citations.filter((c) => c.post_url)
}

/** Two posts from one account is one person saying it twice. Corroboration means two
    platforms, which is the part a single platform going dark cannot fake. */
export function evidenceOf(result: Result): Evidence {
  const cited = citable(result.citations)
  if (!cited.length) return 'none'
  return new Set(cited.map((c) => c.platform)).size >= 2 ? 'corroborated' : 'single'
}

/** The lead excerpt, then the best excerpt from a different platform. Returns one
    entry when nothing corroborates it, and never two from the same source. */
export function leadPair(citations: Citation[]): Citation[] {
  const cited = citable(citations)
  const withText = cited.filter((c) => c.excerpt?.trim())
  const lead = withText[0] ?? cited[0]
  if (!lead) return []
  const second = withText.find((c) => c.platform !== lead.platform)
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

export type MascotMood = 'curious' | 'pleased' | 'skeptical' | 'concerned'

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

export function readingFor(mood: MascotMood): { read: string; note: string } {
  switch (mood) {
    case 'pleased':
      return { read: 'Two sources', note: 'Two platforms carry this one, written by different people.' }
    case 'skeptical':
      return { read: 'One source', note: 'Only one post backs this. Worth a look, not a promise.' }
    case 'concerned':
      return { read: 'Thin evidence', note: 'A source was unreachable at the last refresh, so this may be incomplete.' }
    default:
      return { read: 'Listening', note: 'Answer the four questions and this fills in.' }
  }
}
