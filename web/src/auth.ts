import { ApiError, apiFetch, type Prefs } from './api'

/** docs/TRD.md "API Contract". `shared` is what makes the guest disclosure a
    requirement rather than a nicety: every guest is the same row. */
export type User = {
  id?: string
  email?: string | null
  is_guest?: boolean
  shared?: boolean
}

export type Session = { token: string; user: User }

const KEY = 'makanlah.session'

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    const s = parsed as Record<string, unknown>
    if (typeof s.token !== 'string' || typeof s.user !== 'object' || s.user === null) return null
    return { token: s.token, user: s.user as User }
  } catch {
    return null
  }
}

export function saveSession(session: Session | null): void {
  try {
    if (session) localStorage.setItem(KEY, JSON.stringify(session))
    else localStorage.removeItem(KEY)
  } catch {
    // Private mode. The session lives in memory for this tab and that is enough.
  }
}

/** The API takes at least 8 and at most 1024. Checked here too, so a short password
    is caught before it costs a round trip and a 422. */
export const MIN_PASSWORD = 8
export const MAX_PASSWORD = 1024

/** An API that is reachable but has no auth routes. Kept because the deployed API can
    be older than the client that talks to it. */
function isNotLive(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 404 || err.status === 405 || err.status === 501)
}

export function messageFor(err: unknown): string {
  if (isNotLive(err)) return 'Accounts are not switched on yet. You can still search without one.'
  // One message for a wrong password and for an address that was never registered.
  // Telling them apart would turn the sign-in form into a way to find out who has an
  // account here, so the API returns the same 401 for both and the copy matches it.
  if (err instanceof ApiError && err.status === 401) return 'Email or password is incorrect.'
  if (err instanceof ApiError && err.status === 409) return 'That email is already registered.'
  if (err instanceof ApiError && err.status === 422) return 'Check the email and password and try again.'
  if (err instanceof ApiError && err.status === 429)
    return 'Too many attempts just now. Wait a few minutes and try again.'
  return 'We could not reach the accounts service. You can still search without an account.'
}

const post = (path: string, body: unknown) => apiFetch<Session>(path, { method: 'POST', body: JSON.stringify(body) })

export const signUp = (email: string, password: string) => post('/auth/signup', { email, password })
export const signIn = (email: string, password: string) => post('/auth/login', { email, password })
export const signInAsGuest = () => post('/auth/guest', {})

/** Best effort. The local session is cleared either way: a sign-out that fails
    because the network is down must still sign the person out of this browser. */
export async function signOut(token: string): Promise<void> {
  try {
    await apiFetch('/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
  } catch {
    // Already expired, or unreachable. Nothing here changes what the caller does next.
  }
}

export function putPrefs(token: string, prefs: Prefs): Promise<{ prefs: Prefs }> {
  return apiFetch<{ prefs: Prefs }>('/auth/prefs', {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ prefs })
  })
}
