import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { messageFor, saveSession, signIn, signInAsGuest } from '../auth'
import { AuthLayout } from '../components/AuthLayout'

export function SignIn() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState<'form' | 'guest' | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function attempt(kind: 'form' | 'guest') {
    setBusy(kind)
    setError(null)
    try {
      saveSession(kind === 'guest' ? await signInAsGuest() : await signIn(email, password))
      navigate('/taste')
    } catch (err) {
      // Never dressed as a wrong password when the route simply does not exist yet.
      setError(messageFor(err))
    } finally {
      setBusy(null)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void attempt('form')
  }

  return (
    <AuthLayout>
      <div className="auth">
        <header className="auth-head">
          <h1 className="h-section">Sign In</h1>
          <p className="body-soft section-lede">An account remembers your taste answers. Searching never needs one.</p>
        </header>

        <form className="auth-form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn-primary btn-wide" disabled={busy !== null}>
            {busy === 'form' ? 'Signing In…' : 'Sign In'}
          </button>
        </form>

        <p className="auth-alt">
          No account yet?{' '}
          <Link className="link" to="/sign-up">
            Create One
          </Link>
        </p>

        <GuestBlock busy={busy === 'guest'} disabled={busy !== null} onClick={() => void attempt('guest')} />
      </div>
    </AuthLayout>
  )
}

/**
 * Guest is one shared public account, so the disclosure has to be understood before
 * the click rather than discovered after it. It is set at body size in full-strength
 * ink, sits above the button, and is not softened: issue #8 and docs/TRD.md both make
 * this a disclosure requirement rather than copy.
 */
export function GuestBlock({ busy, disabled, onClick }: { busy: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <section className="guest">
      <h2 className="h-sub">Sign In As Guest</h2>
      <div className="guest-disclosure">
        <p>
          Guest is <strong>one account that everybody shares</strong>. It exists so the app can be demonstrated without
          anyone handing over an email.
        </p>
        <p>
          Anything you do while signed in as Guest, including your taste answers, is visible to every other guest, and
          any of them can change it. Do not put anything private in it.
        </p>
        <p>Continuing is your consent to that.</p>
      </div>
      <button type="button" className="btn btn-quiet btn-wide" onClick={onClick} disabled={disabled}>
        {busy ? 'Signing In…' : 'Continue As Guest'}
      </button>
    </section>
  )
}
