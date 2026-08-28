import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../api'
import { MIN_PASSWORD, messageFor } from '../auth'
import { SignIn } from '../routes/SignIn'

const signIn = () =>
  render(
    <MemoryRouter>
      <SignIn />
    </MemoryRouter>
  )

describe('the guest disclosure', () => {
  it('says all three things before the click', () => {
    // Issue #8 and docs/TRD.md make this a disclosure requirement, not copy: the
    // account is shared, other guests can see and change what you do, and continuing
    // is consent.
    signIn()
    const text = document.querySelector('.guest-disclosure')?.textContent ?? ''
    expect(text).toMatch(/one account that everybody shares/i)
    expect(text).toMatch(/visible to every other guest/i)
    expect(text).toMatch(/consent/i)
  })

  it('is above the button, not after it', () => {
    // "Before the click" is a DOM-order claim, so it gets asserted as one. A
    // disclosure that renders below its own button has not disclosed anything.
    signIn()
    const disclosure = document.querySelector('.guest-disclosure')
    const button = screen.getByRole('button', { name: /Continue As Guest/i })
    expect(disclosure).toBeTruthy()
    // Node.DOCUMENT_POSITION_FOLLOWING: the button comes after the disclosure.
    expect(disclosure?.compareDocumentPosition(button) ?? 0).toBe(4)
  })

  it('is not fine print', () => {
    // It reads at body size in full strength ink. If a later change drops it into a
    // .field-help or a footnote class, this fails.
    signIn()
    expect(document.querySelector('.guest-disclosure')?.className).not.toMatch(/field-help|foot|sr-only/)
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
