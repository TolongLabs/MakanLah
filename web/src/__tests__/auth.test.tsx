import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { ApiError } from '../api'
import { MIN_PASSWORD, messageFor, saveSession } from '../auth'
import { Shell } from '../components/Shell'
import { SignIn } from '../routes/SignIn'

const signIn = () =>
  render(
    <MemoryRouter>
      <SignIn />
    </MemoryRouter>
  )

describe('the guest button', () => {
  it('is the button and nothing else', () => {
    // The heading and the consent paragraphs were removed at the owner's instruction.
    // Asserted so a later change cannot quietly reinstate a block this screen is not
    // supposed to have, and so the removal is a decision on the record rather than a
    // diff nobody reads.
    signIn()
    expect(document.querySelector('.guest-disclosure')).toBeNull()
    expect(screen.queryByRole('heading', { name: /Sign In As Guest/i })).toBeNull()
    expect(screen.getByRole('button', { name: /Continue As Guest/i })).toBeTruthy()
  })

  it('sits under the credential fields, not above them', () => {
    // "Under the Email/Password fields" is a DOM-order claim, so it is asserted as one.
    signIn()
    const form = document.querySelector('.auth-form')
    const button = screen.getByRole('button', { name: /Continue As Guest/i })
    expect(form).toBeTruthy()
    expect(form?.contains(button)).toBe(false)
    // Node.DOCUMENT_POSITION_FOLLOWING: the guest button comes after the whole form.
    expect(form?.compareDocumentPosition(button) ?? 0).toBe(4)
  })

  it('offers guest without demanding an email first', () => {
    signIn()
    expect(screen.getByRole('button', { name: /Continue As Guest/i }).hasAttribute('disabled')).toBe(false)
  })
})

describe('auth error copy', () => {
  it('gives one message for a wrong password and an unknown account', () => {
    // The API returns the same 401 for both on purpose, so the form cannot be used to
    // discover who has an account. The copy has to match that or it leaks it back.
    expect(messageFor(new ApiError(401, 'x'))).toBe('Email or password is incorrect.')
  })

  it('does not dress a missing route as a rejected credential', () => {
    expect(messageFor(new ApiError(404, 'x'))).toMatch(/not switched on yet/i)
  })

  it('has a real state for the rate limiter', () => {
    // The guest button is the easiest one for a demo audience to hammer.
    expect(messageFor(new ApiError(429, 'x'))).toMatch(/too many attempts/i)
  })

  it('says search still works when accounts do not', () => {
    // Auth never gates /recommend, so no auth failure should read as a dead end.
    expect(messageFor(new Error('network'))).toMatch(/without an account/i)
  })

  it('matches the password minimum the API enforces', () => {
    expect(MIN_PASSWORD).toBe(8)
  })
})

describe('the nav while signed in', () => {
  afterEach(() => localStorage.clear())

  function shell() {
    return render(
      <MemoryRouter>
        <Shell>
          <p>body</p>
        </Shell>
      </MemoryRouter>
    )
  }

  it('keeps saying the guest account is shared, not just at sign-in', () => {
    // Disclosing once and never again lets somebody forget mid-session that every
    // other guest can see what they are doing.
    saveSession({ token: 't', user: { is_guest: true, shared: true } })
    shell()
    expect(screen.getByText(/Guest, Shared/i)).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Sign In' })).toBeNull()
  })

  it('names a real account by its email', () => {
    saveSession({ token: 't', user: { email: 'someone@example.com', is_guest: false, shared: false } })
    shell()
    expect(screen.getByText('someone@example.com')).toBeTruthy()
  })

  it('offers sign-in when there is no session', () => {
    shell()
    expect(screen.getByRole('link', { name: 'Sign In' })).toBeTruthy()
  })
})
