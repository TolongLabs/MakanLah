import { cleanup, render, screen } from '@testing-library/react'
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

  function shell(path = '/discover') {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Shell>
          <p>body</p>
        </Shell>
      </MemoryRouter>
    )
  }

  it('no longer labels the guest account in the bar', () => {
    saveSession({ token: 't', user: { is_guest: true, shared: true } })
    shell()
    const bar = document.querySelector('.nav')
    expect(bar?.textContent).not.toMatch(/Guest, Shared/i)
  })

  it("does not disclose the sharing anywhere, which is the owner's decision", () => {
    // Asked directly after the topbar label was removed, and answered "no need to
    // bother". Asserted rather than left silent so the next person reads it as a
    // decision and not as something that fell out during a refactor: a guest is no
    // longer told that other guests can see what they are doing.
    saveSession({ token: 't', user: { is_guest: true, shared: true } })
    shell()
    expect(document.body.textContent).not.toMatch(/shared/i)
  })

  it('names a real account by its email, in the same place as the guest notice', () => {
    // Identity moved out of the bar with the guest label. Both account types are
    // named in one place rather than one in the chrome and one behind a tap.
    saveSession({ token: 't', user: { email: 'someone@example.com', is_guest: false, shared: false } })
    shell()
    expect(document.querySelector('.nav')?.textContent).not.toMatch(/someone@example.com/)
    expect(document.querySelector('[data-nav-drawer]')?.textContent).toMatch(/someone@example.com/)
  })

  it('offers one way in when there is no session, and only one', () => {
    // The bar carries a single action. A Sign In link beside Get Started is two
    // doors to the same room.
    shell()
    expect(screen.getByRole('link', { name: 'Get Started' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Discover' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Sign In' })).toBeNull()
  })

  it('offers only a way out when there is a session', () => {
    saveSession({ token: 't', user: { email: 'someone@example.com', is_guest: false, shared: false } })
    shell()
    expect(screen.getByRole('button', { name: 'Sign Out' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Get Started' })).toBeNull()
  })

  it('lets somebody choose a theme, including following the machine', () => {
    // Three states, not two. A two-state toggle cannot express "follow my OS", so
    // the first tap would silently take that away.
    shell()
    for (const name of [/Auto/i, /Light/i, /Dark/i]) {
      expect(screen.getByRole('radio', { name })).toBeTruthy()
    }
  })

  it('leads with the menu, not the wordmark, once you are inside', () => {
    // It REPLACES the brand rather than sitting beside it: two marks on one bar
    // said the same thing twice and pushed the only working control to the far
    // side of the screen.
    shell()
    const bar = document.querySelector('.nav')
    const first = bar?.querySelector('.wordmark, [data-nav-drawer-toggle]')
    expect(first?.hasAttribute('data-nav-drawer-toggle')).toBe(true)
    expect(bar?.querySelector('.wordmark')).toBeNull()
  })
})

/**
 * The landing bar is a different bar, and its one control does not move.
 *
 * A page whose only job is to start you must not rename or relocate its own door
 * between visits. Where it GOES changes with the session, because sending somebody
 * already signed in back to a sign-up form is a dead end wearing the right label.
 */
describe('the landing bar', () => {
  afterEach(() => localStorage.clear())

  const landing = () =>
    render(
      <MemoryRouter initialEntries={['/']}>
        <Shell>
          <p>body</p>
        </Shell>
      </MemoryRouter>
    )

  it('says Get Started whether or not somebody is signed in', () => {
    landing()
    expect(screen.getByRole('link', { name: 'Get Started' })).toBeTruthy()
    cleanup()
    saveSession({ token: 't', user: { email: 'a@b.c', is_guest: false, shared: false } })
    landing()
    expect(screen.getByRole('link', { name: 'Get Started' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Sign Out' })).toBeNull()
  })

  it('sends a signed-in visitor onward rather than back to a form', () => {
    saveSession({ token: 't', user: { email: 'a@b.c', is_guest: false, shared: false } })
    landing()
    expect(screen.getByRole('link', { name: 'Get Started' }).getAttribute('href')).toBe('/taste')
  })

  it('sends a stranger to sign up', () => {
    landing()
    expect(screen.getByRole('link', { name: 'Get Started' }).getAttribute('href')).toBe('/sign-up')
  })

  it('carries no menu control at all', () => {
    landing()
    expect(document.querySelector('.nav [data-nav-drawer-toggle]')).toBeNull()
  })
})
