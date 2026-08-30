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

/** How a radius reads on screen. Shared so the filter line and the summary cannot
    describe the same distance two different ways. */
export function rangeLabel(m: number): string {
  return m > 0 ? `${(m / 1000).toFixed(m < 1000 ? 1 : 0)} km` : 'All of KL'
}

export function summarise(prefs: Prefs): { term: string; value: string }[] {
  const rows: { term: string; value: string }[] = []
  if (prefs.craving.length) rows.push({ term: 'Craving', value: prefs.craving.join(', ') })
  // The label tables are the validation. `isPrefs` checks `company`, `mood` and
  // `budget` are STRINGS and not that they are known ones, so a value that has been
  // through localStorage -- an older build's vocabulary, a hand-edited key -- maps to
  // undefined and used to be pushed as a row anyway. It rendered as
  // "Answered: 肉骨茶, Family, 3 km, ." on the dashboard card, a stray separator with
  // nothing behind it. An unrecognised answer is not an answer; drop the row.
  if (prefs.company && COMPANY_LABEL[prefs.company]) rows.push({ term: 'With', value: COMPANY_LABEL[prefs.company] })
  if (prefs.range_m !== undefined) rows.push({ term: 'Within', value: rangeLabel(prefs.range_m) })
  if (prefs.mood && MOOD_LABEL[prefs.mood]) rows.push({ term: 'Mood', value: MOOD_LABEL[prefs.mood] })
  if (prefs.budget && BUDGET_LABEL[prefs.budget]) rows.push({ term: 'Budget', value: BUDGET_LABEL[prefs.budget] })
  return rows
}
