import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const health = vi.fn()
vi.mock('../api', async () => {
  const real = await vi.importActual<typeof import('../api')>('../api')
  return { ...real, health: () => health() }
})

import { Dashboard } from '../routes/Dashboard'

const CORPUS = {
  ok: true,
  corpus_size: 1507,
  venues: 247,
  oldest_capture: null,
  newest_capture: '2026-08-27T21:20:22Z'
}

function dash() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  )
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  health.mockReset().mockResolvedValue(CORPUS)
})

afterEach(() => vi.clearAllMocks())

describe('the dashboard routes to the pages that exist', () => {
  it('offers Discover and the wizard', async () => {
    dash()
    expect(screen.getByRole('link', { name: /Find Somewhere To Eat/i }).getAttribute('href')).toBe('/discover')
    expect(screen.getByRole('link', { name: /Your Taste/i }).getAttribute('href')).toBe('/taste')
  })

  it('offers exactly those two, not a third to balance the grid', () => {
    // docs/DESIGN.md names "three items in every list because three feels
    // balanced" as a tell. MakanLah has two other main pages; a third card would
    // be a slot filled rather than a destination.
    const { container } = dash()
    expect(container.querySelectorAll('.dash-card')).toHaveLength(2)
  })
})

describe('the hero prints the corpus rather than a claim about it', () => {
  it('shows what /health measured', async () => {
    dash()
    await waitFor(() => expect(screen.getByText('1,507')).toBeTruthy())
    expect(screen.getByText('247')).toBeTruthy()
  })

  it('prints no figure at all when /health cannot be reached', async () => {
    // A zero is a measurement. An unreachable API has not made one, and a
    // skeleton in the shape of a number is a promise that one is coming.
    health.mockReset().mockRejectedValue(new Error('down'))
    const { container } = dash()
    await waitFor(() => expect(screen.getByText(/Counting what the corpus holds/i)).toBeTruthy())
    expect(container.querySelector('.dash-figures')).toBeNull()
    expect(screen.queryByText('0')).toBeNull()
  })
})

describe('the rail says what it knows and no more', () => {
  it('admits an empty history rather than inventing one', () => {
    // venueCache is sessionStorage, so this is the commonest state on the page:
    // the visit straight after signing in.
    dash()
    expect(screen.getByText(/Nothing yet/i)).toBeTruthy()
  })

  it('lists what the last search parked, with the post count behind each', async () => {
    sessionStorage.setItem(
      'makanlah.lastResults',
      JSON.stringify([
        {
          venue: { id: 'v1', name: '兴记肉骨茶', area: 'Klang', lat: null, lng: null, maps_url: '', dishes: [] },
          rank: 1,
          why: '',
          distance_m: null,
          citations: [
            { post_url: 'a', excerpt: 'x', platform: 'rednote', author_handle: null, posted_at: null },
            { post_url: 'b', excerpt: 'y', platform: 'google_maps', author_handle: null, posted_at: null }
          ]
        }
      ])
    )
    dash()
    const link = screen.getByRole('link', { name: /兴记肉骨茶/ })
    expect(link.getAttribute('href')).toBe('/r/v1')
    // The count is the honesty, same as everywhere else in this product.
    expect(screen.getByText(/2 posts/)).toBeTruthy()
  })
})
