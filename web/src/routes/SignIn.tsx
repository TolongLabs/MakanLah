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
      navigate('/dashboard')
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

        <GuestBlock busy={busy === 'guest'} disabled={busy !== null} onClick={() => void attempt('guest')} />

        <p className="auth-alt">
          No account yet?{' '}
          <Link className="link" to="/sign-up">
            Create One
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}

export function GuestBlock({ busy, disabled, onClick }: { busy: boolean; disabled: boolean; onClick: () => void }) {
  // Button only, directly under the credential fields. The heading and the three
  // paragraphs of consent copy are gone at the owner's instruction.
  //
  // The account really is shared, so the disclosure has not vanished from the product:
  // the nav renders "Guest, Shared" for the whole session, which is where somebody is
  // actually at risk of forgetting. Worth knowing that this screen no longer says it
  // before the click.
  return (
    <button type="button" className="btn btn-quiet btn-wide guest-btn" onClick={onClick} disabled={disabled}>
      {busy ? 'Signing In…' : 'Continue As Guest'}
    </button>
  )
}
