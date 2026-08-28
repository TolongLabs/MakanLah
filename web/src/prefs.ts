import type { Prefs } from './api'

const KEY = 'makanlah.prefs'

/**
 * The wizard's answers. Written exactly once, by the final CTA, so a half-finished
 * wizard leaves nothing behind and `/discover` can tell "never answered" from
 * "answered and came back".
 */
export function loadPrefs(): Prefs | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return isPrefs(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function savePrefs(prefs: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs))
  } catch {
    // Private mode, or storage is full. The wizard still hands its answers to
    // /discover through the router, so losing the copy costs the next visit only.
  }
}

/** Scraped input is the least trustworthy data in the project, and so is anything
    that has been through localStorage. Parse it, never spread it. */
function isPrefs(v: unknown): v is Prefs {
  if (typeof v !== 'object' || v === null) return false
  const p = v as Record<string, unknown>
  if (!Array.isArray(p.craving) || p.craving.some((c) => typeof c !== 'string')) return false
  if (p.range_m !== undefined && typeof p.range_m !== 'number') return false
  for (const k of ['company', 'mood', 'budget'] as const) {
    if (p[k] !== undefined && typeof p[k] !== 'string') return false
  }
  return true
}

/** The wizard's craving answers become the search string. Free text the user typed
    is kept verbatim and never rewritten. */
export function queryFrom(prefs: Prefs): string {
  return prefs.craving.join(', ')
}

const COMPANY_LABEL: Record<NonNullable<Prefs['company']>, string> = {
  solo: 'On my own',
  couple: 'Two of us',
  family: 'Family',
  group: 'A group'
}

const MOOD_LABEL: Record<NonNullable<Prefs['mood']>, string> = {
  comfort: 'Something familiar',
  adventurous: 'Something new'
}

const BUDGET_LABEL: Record<NonNullable<Prefs['budget']>, string> = {
  cheap: 'Cheap',
  mid: 'Mid',
  splurge: 'Splurge'
}

export function summarise(prefs: Prefs): { term: string; value: string }[] {
  const rows: { term: string; value: string }[] = []
  if (prefs.craving.length) rows.push({ term: 'Craving', value: prefs.craving.join(', ') })
  if (prefs.company) rows.push({ term: 'With', value: COMPANY_LABEL[prefs.company] })
  if (prefs.range_m) rows.push({ term: 'Within', value: `${(prefs.range_m / 1000).toFixed(prefs.range_m < 1000 ? 1 : 0)} km` })
  else if (prefs.range_m === 0) rows.push({ term: 'Within', value: 'All of KL' })
  if (prefs.mood) rows.push({ term: 'Mood', value: MOOD_LABEL[prefs.mood] })
  if (prefs.budget) rows.push({ term: 'Budget', value: BUDGET_LABEL[prefs.budget] })
  return rows
}
