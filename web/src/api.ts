export type Citation = {
  post_url: string
  excerpt: string | null
  platform: string
  author_handle: string | null
  posted_at: string | null
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

export type RecommendResponse = {
  results: Result[]
  degraded: boolean
  /** Why it is degraded, in plain language. Shown to the user, not logged. */
  degraded_reasons?: string[]
  sources_used: string[]
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
