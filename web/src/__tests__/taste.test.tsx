import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SCRIPT } from '../companion/lines'
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

/** A speech synthesiser jsdom does not have. Returns the spy on speak(). */
function stubVoice() {
  const speak = vi.fn()
  vi.stubGlobal('speechSynthesis', {
    speak,
    cancel: vi.fn(),
    getVoices: () => [{ name: 'Samantha', lang: 'en-GB' }],
    speaking: false
  })
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      text: string
      voice: unknown = null
      lang = ''
      pitch = 1
      rate = 1
      constructor(text: string) {
        this.text = text
      }
    }
  )
  return speak
}

/** Push past SPEAK_BY_MS AND the promises behind the fetch and the voice list.
    Advancing timers alone leaves the .then() chain unflushed, which made an earlier
    version of the "stays quiet" assertion pass against a companion that did speak. */
async function settle() {
  await act(async () => {
    vi.advanceTimersByTime(3000)
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('the companion', () => {
  it('has something to say in the frame the step appears', () => {
    // The bubble is never empty while a request is in flight. The scripted line is
    // on screen before the fetch is even issued.
    wizard()
    const said = document.querySelector('.companion-bubble')?.textContent ?? ''
    expect(Object.values(SCRIPT.craving)).toContain(said)
  })

  it('changes what she is asking when the step changes', () => {
    wizard()
    choose(/Roti Canai/i)
    click('Continue')
    const said = document.querySelector('.companion-bubble')?.textContent ?? ''
    expect(Object.values(SCRIPT.company)).toContain(said)
  })

  it('says the same thing again when you step back', () => {
    wizard()
    const first = document.querySelector('.companion-bubble')?.textContent
    choose(/Roti Canai/i)
    click('Continue')
    click('Back')
    expect(document.querySelector('.companion-bubble')?.textContent).toBe(first)
  })

  it('stays quiet until the voice is switched on', async () => {
    // Chrome and Safari refuse speak() before a user gesture, so a companion that
    // spoke on arrival would be silent on step one and startling on step two. This
    // asserts the product decision, not the browser's: nothing is spoken unasked.
    const speak = stubVoice()
    wizard()
    await settle()
    expect(speak).not.toHaveBeenCalled()
  })

  it('speaks on the click that turns the voice on, and remembers the choice', async () => {
    const speak = stubVoice()
    wizard()
    click(/Voice Off/i)
    await settle()
    expect(speak).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('makanlah.companion.voice')).toBe('1')
    expect(screen.getByRole('button', { name: /Voice On/i }).getAttribute('aria-pressed')).toBe('true')
  })

  it('speaks the line that is actually on screen', async () => {
    const speak = stubVoice()
    wizard()
    click(/Voice Off/i)
    await settle()
    const utterance = speak.mock.calls[0]?.[0] as { text: string }
    expect(utterance.text).toBe(document.querySelector('.companion-bubble')?.textContent)
  })

  it('does not queue a second line over the first', async () => {
    // Stepping quickly used to queue an utterance per step and answer the last one
    // long after the user had moved on. cancel() before every speak is the fix.
    const speak = stubVoice()
    const cancel = (globalThis.speechSynthesis as unknown as { cancel: ReturnType<typeof vi.fn> }).cancel
    wizard()
    click(/Voice Off/i)
    await settle()
    choose(/Roti Canai/i)
    click('Continue')
    await settle()
    expect(speak).toHaveBeenCalledTimes(2)
    expect(cancel.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('offers no voice control on a browser that cannot speak', () => {
    // jsdom has no speechSynthesis, which is also true of some mobile browsers. A
    // toggle for a thing that cannot happen is worse than no toggle.
    wizard()
    expect(screen.queryByRole('button', { name: /Voice/i })).toBeNull()
  })
})
