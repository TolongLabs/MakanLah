import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Taste } from '../routes/Taste'

// The craving options are generated from the clock, so an unfrozen suite passes at
// 08:00 and fails at 12:00. Pinned to a morning: the labels below are the breakfast
// band, and the generator has its own coverage across all four bands in prefs.test.ts.
beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.setSystemTime(new Date(2026, 7, 28, 8, 0, 0))
  vi.stubGlobal('navigator', { ...navigator, geolocation: undefined })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const wizard = () =>
  render(
    <MemoryRouter>
      <Taste />
    </MemoryRouter>
  )

const click = (name: RegExp | string) => fireEvent.click(screen.getByRole('button', { name }))
const choose = (name: RegExp | string) => fireEvent.click(screen.getByLabelText(name))

describe('the wizard', () => {
  it('opens on the first of four steps', () => {
    wizard()
    expect(screen.getByText('Step 1 of 4')).toBeTruthy()
    expect(screen.getByRole('heading', { name: /craving/i })).toBeTruthy()
  })

  it('will not continue until the step is answered', () => {
    wizard()
    expect(screen.getByRole('button', { name: 'Continue' }).hasAttribute('disabled')).toBe(true)
    choose(/Own Words/i)
    fireEvent.change(screen.getByLabelText('In Your Own Words'), { target: { value: 'something soupy' } })
    expect(screen.getByRole('button', { name: 'Continue' }).hasAttribute('disabled')).toBe(false)
  })

  it('writes nothing until the final CTA', () => {
    // Issue #8 makes this explicit, and it is the reason the wizard is worth having:
    // somebody who opens it and changes their mind leaves nothing behind, so
    // /discover can tell "never answered" from "answered and came back".
    wizard()
    choose(/Roti Canai/i)
    click('Continue')
    choose(/On My Own/i)
    click('Continue')
    choose(/Anywhere In KL/i)
    click('Continue')
    expect(screen.getByText('Step 4 of 4')).toBeTruthy()
    expect(localStorage.getItem('makanlah.prefs')).toBeNull()

    choose(/Something Familiar/i)
    click('Find Food')
    expect(localStorage.getItem('makanlah.prefs')).not.toBeNull()
  })

  it('records every answer, including the craving text, on that one write', () => {
    wizard()
    choose(/Roti Canai/i)
    click('Continue')
    choose(/A Group/i)
    click('Continue')
    choose(/Anywhere In KL/i)
    click('Continue')
    choose(/Something New/i)
    click('Find Food')
    const saved = JSON.parse(localStorage.getItem('makanlah.prefs') ?? '{}')
    expect(saved.company).toBe('group')
    expect(saved.mood).toBe('adventurous')
    expect(saved.range_m).toBe(0)
    expect(saved.craving).toHaveLength(1)
  })

  it('leaves budget out rather than inventing one when no preference is chosen', () => {
    wizard()
    choose(/Roti Canai/i)
    click('Continue')
    choose(/On My Own/i)
    click('Continue')
    choose(/Anywhere In KL/i)
    click('Continue')
    choose(/Something Familiar/i)
    click('Find Food')
    expect(JSON.parse(localStorage.getItem('makanlah.prefs') ?? '{}').budget).toBeUndefined()
  })

  it('goes back without losing the answer', () => {
    wizard()
    choose(/Roti Canai/i)
    click('Continue')
    click('Back')
    expect(screen.getByText('Step 1 of 4')).toBeTruthy()
    expect((screen.getByLabelText(/Roti Canai/i) as HTMLInputElement).checked).toBe(true)
  })

  it('does not dead-end when the browser cannot give a location', () => {
    // Refusing location falls back to KL-wide and says so. docs/DESIGN.md makes this
    // a design requirement rather than an error path.
    wizard()
    choose(/Roti Canai/i)
    click('Continue')
    choose(/On My Own/i)
    click('Continue')
    choose(/Walking Distance/i)
    expect(screen.getByText(/searches all of KL/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Continue' }).hasAttribute('disabled')).toBe(false)
  })
})
