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

/**
 * The auth backend is issue #9 and is not deployed yet, so every one of these can
 * come back 404. That is reported as itself rather than dressed as a wrong password:
 * a sign-in form that says "incorrect credentials" when the route does not exist
 * sends the user to reset a password that was never stored.
 */
export const NOT_LIVE = 'accounts-not-live'

export function isNotLive(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 404 || err.status === 405 || err.status === 501)
}

export function messageFor(err: unknown): string {
  if (isNotLive(err)) return 'Accounts are not switched on yet. You can still search without one.'
  if (err instanceof ApiError && err.status === 401) return 'That email and password do not match.'
  if (err instanceof ApiError && err.status === 409) return 'That email is already registered.'
  if (err instanceof ApiError && err.status === 422) return 'Check the email and password and try again.'
  return 'We could not reach the accounts service. You can still search without an account.'
}

const post = (path: string, body: unknown) => apiFetch<Session>(path, { method: 'POST', body: JSON.stringify(body) })

export const signUp = (email: string, password: string) => post('/auth/signup', { email, password })
export const signIn = (email: string, password: string) => post('/auth/login', { email, password })
export const signInAsGuest = () => post('/auth/guest', {})

export function putPrefs(token: string, prefs: Prefs): Promise<{ prefs: Prefs }> {
  return apiFetch<{ prefs: Prefs }>('/auth/prefs', {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ prefs })
  })
}
