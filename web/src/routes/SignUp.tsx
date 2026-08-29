import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MIN_PASSWORD, messageFor, saveSession, signInAsGuest, signUp } from '../auth'
import { AuthLayout } from '../components/AuthLayout'
import { GuestBlock } from './SignIn'

export function SignUp() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState<'form' | 'guest' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mismatch = confirm.length > 0 && confirm !== password
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD
  const ready = email.length > 0 && password.length >= MIN_PASSWORD && confirm === password

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy('form')
    setError(null)
    try {
      saveSession(await signUp(email, password))
      navigate('/taste')
    } catch (err) {
      setError(messageFor(err))
    } finally {
      setBusy(null)
    }
  }

  async function guest() {
    setBusy('guest')
    setError(null)
    try {
      saveSession(await signInAsGuest())
      navigate('/taste')
    } catch (err) {
      setError(messageFor(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <AuthLayout>
      <div className="auth">
        <header className="auth-head">
          <h1 className="h-section">Create An Account</h1>
          <p className="body-soft section-lede">
            Email and password only. There is no sign-in with Google or Apple here.
          </p>
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
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby="password-help"
            />
            <p className="field-help" id="password-help">
              {`At least ${MIN_PASSWORD} characters. Nothing else is required, and length beats punctuation.`}
            </p>
            {tooShort && <p className="field-error">{`That is ${password.length} of ${MIN_PASSWORD} characters.`}</p>}
          </div>
          <div className="field">
            <label htmlFor="confirm">Confirm Password</label>
            <input
              id="confirm"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            {mismatch && <p className="field-error">Those two do not match.</p>}
          </div>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn-primary btn-wide" disabled={!ready || busy !== null}>
            {busy === 'form' ? 'Creating…' : 'Create Account'}
          </button>
        </form>

        <p className="auth-alt">
          Already have one?{' '}
          <Link className="link" to="/sign-in">
            Sign In
          </Link>
        </p>

        <GuestBlock busy={busy === 'guest'} disabled={busy !== null} onClick={() => void guest()} />
      </div>
    </AuthLayout>
  )
}
