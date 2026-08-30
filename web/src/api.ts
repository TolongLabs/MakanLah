export type Citation = {
  post_url: string
  /** The post's own identity (#153). **Not the same thing as `post_url`**, and the
      gap is not an edge case: Google Maps has no per-review URL, so `review_url()`
      returns the venue's page and about eight reviews share one address. Measured:
      1388 Maps mentions across 178 distinct URLs. Deduping on the URL therefore
      collapsed three different people into one testimony and denied the venue a
      corroboration stamp it had earned.

      Optional because a client build can outrun the API; `citable()` falls back to
      the URL, which is the old behaviour and errs toward showing less. */
  post_id?: string | null
  /** Other venues in the SAME response backed by this same post (#87). A listicle
      backing ranks 1, 2 and 3 is one voice, and the reader cannot see that without
      being told. Optional: the API does not send it yet. */
  shared_with?: string[]
  excerpt: string | null
  platform: string
  author_handle: string | null
  posted_at: string | null
  /** Whether the post still resolves (#83). `true` = measured dead, `null` or
      absent = never checked, which is NOT the same thing and is treated as live.
      The API sends it; a card that ignores it links the reader to a wall. */
  dead?: boolean | null
}

/** docs/TRD.md "API Contract". `basis` lets the UI say why an entry is present
    instead of asserting a number. The API does not send it yet, so it is optional. */
export type Match = {
  basis?: 'dish' | 'text' | 'semantic'
  /** The dish the query matched on, null when the match was not a dish match. */
  dish?: string | null
  /** Retrieval cosine. Never rendered, for the same reason as `score`. See issue #7. */
  similarity?: number
}

export type Venue = {
  id: string
  name: string
  area: string | null
  lat: number | null
  lng: number | null
  maps_url: string
  dishes: string[]
  /** A short qualifier that tells this venue apart from a same-named sibling, or
      null when the corpus genuinely cannot tell them apart. **Null is a real
      answer here, not a missing one** (#58): the UI must never invent a label to
      fill it, because the whole point is admitting the ambiguity. */
  disambiguator?: string | null
  /** Which of the response's `coverage_gaps` a real post about THIS venue actually
      mentions. Empty means nobody wrote about it either way, which is not the same
      as "no" and must never be rendered as one. */
  gap_mentions?: string[]
  /** Distinct counts behind this venue, added for #87. "Two independent sources"
      is only true when `authors >= 2` AND `posts >= 2`: two mentions from one
      author on one post are one voice however many platforms carry it. Optional
      because the API does not send it yet -- absent means "cannot claim it". */
  corroboration?: { posts: number; authors: number; platforms: number }
  /** How the posts about this venue actually split (#142). Counts, never an
      average: 871 of 1653 mentions sit at exactly 1.0, so a mean reads "positive"
      on nearly every card and discriminates nothing.

      **The buckets are asymmetric on purpose** -- `positive >= 0.6`, `negative
      <= -0.2`. The scale is crowded at the top so positive needs a high bar to
      mean anything, while one person saying a place was bad is worth surfacing
      even when nine disagree. A `negative: 1` is therefore a real complaint and
      not a rounding artefact, which is why the copy leads with it.

      Optional: the API does not send it until #142 deploys. */
  sentiment?: { positive: number; mixed: number; negative: number } | null
  /** A small static map of the venue, fetched ONCE at ingestion and served from our
      side. Not rendered from coordinates in the browser: OSM's tile usage policy is
      explicit about bulk use by applications, and a tile request per viewer per
      venue is a rate limit on infrastructure we do not own. Absent until the
      ingestion pass has run, and absent forever for a venue with no geocode. */
  map_image_url?: string | null
  /** True when another venue in the corpus reads as the same name. Two rows is the
      correct rendering -- they are different restaurants -- but the reader has to
      be told, or it looks like a duplicate. */
  ambiguous_with_sibling?: boolean
}

export type Result = {
  venue: Venue
  /** The position the re-rank assigned. Optional: the live API still sends `score`. */
  rank?: number
  /** Retrieval cosine, ordered by a different pass. Never rendered. See issue #7. */
  score?: number
  why: string
  match?: Match
  distance_m: number | null
  citations: Citation[]
}

/** The corpus carries the dish and cannot show anybody writing about it: every
    venue serving it was dropped because its posts no longer resolve (#98). Present
    only in that case, and `results` is empty when it is -- five semantically-close
    venues under a note conceding they are not what was asked for is the thing
    docs/TRD.md says is worse than returning nothing. */
export type EvidenceGap = {
  term: string
  /** Named rather than counted. That a post said something is unverifiable once
      the post is gone; that the restaurant exists is checkable in ten seconds. */
  venues: { name: string; area: string | null; maps_url: string }[]
  /** How many carry it in total. The list is capped; the count is not, so a
      bounded list never reads as the whole answer. */
  total: number
}

/** The corpus knows the dish and nothing within the radius serves it. Distinct from
    `evidence_gap`, which is "every venue serving it has lost its posts" — that is a
    fact about the EVIDENCE, this is a fact about the DISTANCE, and the two need
    different sentences because the user's next move differs. Here, widening the
    search actually works.

    **`nearest` mixes two evidence classes and `verifiable` is what separates them.**
    Some entries have live citations; some are the #101 all-dead-citation venues,
    suppressed from ranked results but still real restaurants. `85b9220` added the
    per-entry flag, so the surface can say which is which rather than naming every
    entry identically and offering evidence for none of them. */
export type DistanceGap = {
  term: string
  /** At most three, nearest first. Every one genuinely carries the dish. */
  nearest: {
    name: string
    area: string | null
    distance_m: number
    maps_url: string
    /** Posts that still resolve. Named rather than shown: this surface carries no
        venue id, so the count is the whole claim it is able to make. */
    live_citations?: number
    /** Whether anything survives to be read at all.

        OPTIONAL because an older API does not send it, and the two absent fields
        must not read as `false`. Undefined means "this build cannot tell", and the
        surface then claims nothing -- which is exactly what it did before the flag
        existed. Defaulting a missing flag to false would turn "we do not know" into
        "nobody wrote about this", which is the one thing the flag was added to stop
        this surface doing. */
    verifiable?: boolean
  }[]
}

export type RecommendResponse = {
  results: Result[]
  degraded: boolean
  /** Why it is degraded, in plain language. Shown to the user, not logged. */
  degraded_reasons?: string[]
  sources_used: string[]
  /** What the corpus cannot answer about this query, as keys rather than prose so
      the client owns the wording. `['halal']` means the corpus holds no halal
      signal at all — a completely different sentence from "these are not exact
      matches", and the reader is entitled to the first one. */
  coverage_gaps?: string[]
  evidence_gap?: EvidenceGap
  distance_gap?: DistanceGap
  error?: string
}

export type Health = {
  ok: boolean
  corpus_size: number
  venues?: number
  oldest_capture: string | null
  newest_capture: string | null
}

/** The `/taste` wizard's output. Optional on every call: a bare query must keep
    working, because auth never gates `/recommend`. */
export type Prefs = {
  craving: string[]
  company?: 'solo' | 'couple' | 'family' | 'group'
  range_m?: number
  mood?: 'adventurous' | 'comfort'
  budget?: 'cheap' | 'mid' | 'splurge'
}

/** The re-rank is one model call, so a slow answer is normal and a silent one is not. */
const TIMEOUT_MS = 30_000

const DEFAULT_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

/**
 * The API is not deployed yet, so a hosted page has no backend to talk to and a
 * browser blocks an https page calling http://127.0.0.1 anyway. `?api=<url>`
 * repoints it and is remembered, so this page works against a tunnel today and
 * against the real API the moment one exists, without a rebuild.
 */
export function apiBase(): string {
  try {
    const fromQuery = new URLSearchParams(window.location.search).get('api')
    if (fromQuery) {
      localStorage.setItem('makanlah.api', fromQuery)
      return fromQuery
    }
    return localStorage.getItem('makanlah.api') ?? DEFAULT_BASE
  } catch {
    return DEFAULT_BASE
  }
}

/** Thrown when the API answered but said no. `status` lets a caller tell a route that
    does not exist yet from one that rejected the request. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  // A request with no deadline leaves the user on "Finding..." forever. Observed on
  // the hosted page, where the browser neither completes nor rejects a call to an API
  // it cannot reach. A visible failure beats an invisible wait.
  const abort = new AbortController()
  const timer = setTimeout(() => abort.abort(), TIMEOUT_MS)
  try {
    const res = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
      signal: abort.signal
    })
    if (!res.ok) throw new ApiError(res.status, `api ${res.status}`)
    return (await res.json()) as T
  } finally {
    clearTimeout(timer)
  }
}

export type RecommendBody = {
  query: string
  lat?: number
  lng?: number
  radius_m?: number
  limit?: number
  prefs?: Prefs
}

export function recommend(body: RecommendBody): Promise<RecommendResponse> {
  return apiFetch<RecommendResponse>('/recommend', { method: 'POST', body: JSON.stringify(body) })
}

export function health(): Promise<Health> {
  return apiFetch<Health>('/health')
}

/**
 * One venue's full citation trail. `rank`, `why` and `match` come back null by
 * construction: nothing was ranked and nothing was matched, so the API declines to
 * invent a position for a direct lookup. 404 means the venue carries no citations,
 * which is not a result.
 */
export function venue(id: string, at?: { lat: number; lng: number }): Promise<Result> {
  const q = at ? `?lat=${encodeURIComponent(at.lat)}&lng=${encodeURIComponent(at.lng)}` : ''
  return apiFetch<Result>(`/venue/${encodeURIComponent(id)}${q}`)
}

/** One spoken line for the onboarding companion. `source` says whether a model or
    the scripted fallback wrote it; the UI renders both the same way, and the field
    exists so a dead lane is visible in a log rather than indistinguishable. */
export type CompanionLine = { text: string; source: 'model' | 'script'; reason?: string }

/**
 * The companion's line for one wizard step.
 *
 * The only generated text in the product, and safe to be: it sees no corpus row,
 * names no venue and carries no citation, which the API enforces rather than
 * hopes for. `picked` is the labels the user just tapped and nothing else.
 */
export function companionLine(step: string, picked: string[]): Promise<CompanionLine> {
  return apiFetch<CompanionLine>('/companion', { method: 'POST', body: JSON.stringify({ step, picked }) })
}

/** A dish the corpus actually has posts about. The label is a database string, never
    model text: the model that orders these chips returns indices, so it cannot invent
    a dish and a chip can never lead to an empty result page. */
export type Chip = { label: string; query: string; posts: number; venues: number }

export type Suggestions = { chips: Chip[]; band: string; source: 'model' | 'corpus' | 'unavailable' }

export function suggestions(): Promise<Suggestions> {
  return apiFetch<Suggestions>('/suggestions')
}

/** One question about one venue, answered from its citations or not at all.
    `covered: false` is a correct answer and carries no citations by construction. */
export type AskResponse = {
  covered: boolean
  answer: string
  citations: Citation[]
  venue?: { id: string; name: string; area: string | null } | null
}

export function ask(venueId: string, question: string): Promise<AskResponse> {
  return apiFetch<AskResponse>('/ask', {
    method: 'POST',
    body: JSON.stringify({ venue_id: venueId, question })
  })
}

/**
 * One step the copilot took before answering.
 *
 * The tool trace is not a debug view. It is the evidence claim made watchable:
 * `makanlah/copilot.py` enforces that she answers from stored excerpts or not at
 * all, and until now that guarantee was invisible — the user was told she had
 * looked. Watching `read_citations → 4 posts` happen is the same claim, checkable.
 * It also makes `covered: false` stronger: she is seen looking and finding nothing.
 */
export type ToolStep = {
  id: string
  /** Human-readable by contract. `read_citations`, never `_fn_0`. */
  name: string
  args?: Record<string, unknown>
  /** One line, rendered as-is. The raw payload is deliberately not sent. */
  summary?: string
  count?: number
}

export type AskEvent =
  | ({ type: 'tool_call' } & Omit<ToolStep, 'summary' | 'count'>)
  | { type: 'tool_result'; id: string; summary: string; count?: number }
  | { type: 'delta'; text: string }
  | { type: 'done'; covered: boolean; answer?: string; citations: Citation[] }

export type AskTurn = { role: 'user' | 'assistant'; content: string }

/** Thrown when the streaming route is not deployed. The caller falls back to the
    one-shot `/ask`, which is why `POST /ask` must keep working unchanged. */
export class NoStream extends Error {}

/**
 * The copilot, as a stream of events rather than one answer.
 *
 * Parses SSE and NDJSON with the same reader: a `data:` prefix is stripped if
 * present and the rest is JSON either way, so whichever the API settles on works
 * without a client change.
 *
 * An unparseable line is skipped rather than killing the stream. A malformed frame
 * mid-answer should cost that frame, not the conversation.
 */
export async function* askStream(venueId: string, messages: AskTurn[], signal?: AbortSignal): AsyncGenerator<AskEvent> {
  let res: Response
  try {
    res = await fetch(`${apiBase()}/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ venue_id: venueId, messages }),
      signal
    })
  } catch {
    throw new NoStream('unreachable')
  }
  // 404 and 405 are "not deployed yet", which is a normal state and not an error.
  if (res.status === 404 || res.status === 405) throw new NoStream(`status ${res.status}`)
  if (!res.ok || !res.body) throw new ApiError(res.status, `ask/stream ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      // The last fragment may be half an event; it waits for the next chunk.
      buffer = lines.pop() ?? ''
      for (const raw of lines) {
        const line = raw.trim()
        if (!line || line.startsWith(':')) continue
        const json = line.startsWith('data:') ? line.slice(5).trim() : line
        if (!json || json === '[DONE]') continue
        try {
          yield JSON.parse(json) as AskEvent
        } catch {
          // One bad frame costs that frame, not the conversation.
        }
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}
