import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const recommend = vi.fn()
const suggestions = vi.fn()

vi.mock('../api', async () => {
  const real = await vi.importActual<typeof import('../api')>('../api')
  return { ...real, recommend: (...a: unknown[]) => recommend(...a), suggestions: () => suggestions() }
})

// The Live2D chunk is 500 KB of pixi behind a lazy import and never resolves in
// jsdom. The panel is not what these assertions are about.
vi.mock('../components/AskCompanion', () => ({ AskCompanion: () => null }))

import { Discover } from '../routes/Discover'

const empty = { results: [], degraded: false, sources_used: [] }

function show(state: Record<string, unknown>) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/discover', state }]}>
      <Discover />
    </MemoryRouter>
  )
}

beforeEach(() => {
  localStorage.clear()
  recommend.mockReset().mockResolvedValue(empty)
  suggestions.mockReset().mockResolvedValue({ chips: [], band: 'lunch', source: 'corpus' })
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('the empty state tells the truth about why', () => {
  it('blames the distance when a distance was actually applied', async () => {
    // Peer 3 at her Klang office on 3 km was told "nothing in the corpus matches
    // nasi lemak yet" -- and Search All Of KL right after returned ten picks. The
    // corpus was never the reason.
    show({ prefs: { craving: ['nasi lemak'], range_m: 3000 }, geo: { lat: 3.04, lng: 101.44 } })
    const box = await screen.findByText(/Nothing for/i)
    expect(box.textContent).toMatch(/within 3 km of you/i)
    expect(screen.getByRole('button', { name: /Search All Of KL/i })).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/Nothing in the corpus/i)
  })

  it('never claims a radius when geolocation never resolved', async () => {
    // radius is selected but run() drops it without a fix, so the search was
    // KL-wide. Saying "within 3 km of you" would be the same lie in reverse.
    show({ prefs: { craving: ['nasi lemak'], range_m: 3000 }, geoRefused: true })
    await screen.findByText(/Nobody has written about/i)
    expect(document.body.textContent).not.toMatch(/km of you/i)
  })

  it('does not point at suggestions that are not on screen', async () => {
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await screen.findByText(/Nobody has written about/i)
    expect(document.body.textContent).not.toMatch(/suggestions above/i)
  })

  it('points at the suggestions when there are some', async () => {
    suggestions.mockResolvedValue({
      chips: [{ label: '肉骨茶', query: '肉骨茶', posts: 14, venues: 9 }],
      band: 'lunch',
      source: 'model'
    })
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await waitFor(() => expect(document.body.textContent).toMatch(/suggestions above/i))
  })
})

describe('the craving can be dropped', () => {
  it('stops sending it and stops advertising it', async () => {
    show({ prefs: { craving: ['nasi lemak bumbung supper'], company: 'solo', range_m: 0 } })
    const drop = await screen.findByRole('button', { name: /Drop The Craving/i })
    expect(document.body.textContent).toMatch(/nasi lemak bumbung supper/i)

    drop.click()
    await waitFor(() => expect(document.body.textContent).not.toMatch(/nasi lemak bumbung supper/i))

    // The claim and the request have to agree: it must be gone from BOTH.
    const last = recommend.mock.calls.at(-1)?.[0] as { prefs?: { craving?: string[] } }
    expect(last?.prefs?.craving).toEqual([])
  })
})

describe('the search field', () => {
  it('is empty on arrival', async () => {
    // It used to be prefilled from the wizard, so it had to be cleared before it
    // could be used, and it made the answers look like a query the user typed.
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await waitFor(() => expect(recommend).toHaveBeenCalled())
    expect((screen.getByLabelText(/hungry for/i) as HTMLInputElement).value).toBe('')
  })

  it('still runs the wizard answers as the first search', async () => {
    show({ prefs: { craving: ['肉骨茶'], range_m: 0 } })
    await waitFor(() => expect(recommend).toHaveBeenCalled())
    const first = recommend.mock.calls[0]?.[0] as { query: string } | undefined
    expect(first?.query).toBe('肉骨茶')
  })
})
