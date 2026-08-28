import type { Result } from './api'

const KEY = 'makanlah.lastResults'

/**
 * The venue page needs the full citation trail for one pick. There is no
 * GET /venue/{id} in the API yet (requested from the backend session; until it lands
 * this is the stub), so /discover parks what it already fetched and /r/:id reads it.
 *
 * sessionStorage, not localStorage: a citation trail is a snapshot of one search, and
 * showing yesterday's copy of it next week would be a quieter kind of lying.
 */
export function cacheResults(results: Result[]): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(results))
  } catch {
    // Quota or private mode. The venue page falls back to its cold-load state.
  }
}

export function cachedVenue(id: string): Result | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    const hit = parsed.find((r: unknown) => {
      if (typeof r !== 'object' || r === null) return false
      const venue = (r as { venue?: unknown }).venue
      return typeof venue === 'object' && venue !== null && (venue as { id?: unknown }).id === id
    })
    return (hit as Result | undefined) ?? null
  } catch {
    return null
  }
}
