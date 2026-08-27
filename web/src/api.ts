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
  sources_used: string[]
  error?: string
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

export async function recommend(body: {
  query: string
  lat?: number
  lng?: number
  radius_m?: number
  limit?: number
}): Promise<RecommendResponse> {
  const res = await fetch(`${BASE}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`api ${res.status}`)
  return (await res.json()) as RecommendResponse
}
