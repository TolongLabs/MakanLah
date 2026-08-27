export type Citation = {
  post_url: string
  excerpt: string | null
  platform: string
  author_handle: string | null
  posted_at: string | null
}

export type Result = {
  venue: {
    id: string
    name: string
    area: string | null
    lat: number | null
    lng: number | null
    maps_url: string
    dishes: string[]
  }
  score: number
  why: string
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

const DEFAULT_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

/**
 * The API is not deployed yet, so a hosted page has no backend to talk to and a
 * browser blocks an https page calling http://127.0.0.1 anyway. `?api=<url>`
 * repoints it and is remembered, so this page works against a tunnel today and
 * against the real API the moment one exists — without a rebuild.
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

export async function recommend(body: {
  query: string
  lat?: number
  lng?: number
  radius_m?: number
  limit?: number
}): Promise<RecommendResponse> {
  const res = await fetch(`${apiBase()}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`api ${res.status}`)
  return (await res.json()) as RecommendResponse
}
