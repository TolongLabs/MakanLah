import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from '../App'
import type { Result } from '../api'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, recommend: vi.fn() }
})

function result(over: Partial<Result> = {}): Result {
  return {
    venue: {
      id: 'v1',
      name: '兴记肉骨茶 Hing Kee Bakuteh',
      area: 'Jalan Ipoh',
      lat: 3.2,
      lng: 101.67,
      maps_url: 'https://www.google.com/maps/search/?api=1&query=x',
      dishes: ['肉骨茶', 'nasi lemak', 'ayam goreng berempah']
    },
    score: 0.78,
    why: 'Rich herbal broth, and the locals keep going back.',
    distance_m: 1200,
    citations: [
      {
        post_url: 'https://www.rednote.com/explore/abc',
        excerpt: '汤底浓郁药材香，肉质软烂入味，配白饭简直绝配！Sedap sangat.',
        platform: 'rednote',
        author_handle: 'author_ab12',
        posted_at: 'Feb 17'
      }
    ],
    ...over
  }
}

async function renderWith(results: Result[]) {
  const api = await import('../api')
  vi.mocked(api.recommend).mockResolvedValue({ results, degraded: false, sources_used: ['rednote'] })
  const { default: userEventDefault } = await import('@testing-library/react')
  void userEventDefault
  const view = render(<App />)
  const input = screen.getByLabelText('What you feel like eating')
  const { fireEvent } = await import('@testing-library/react')
  fireEvent.change(input, { target: { value: 'bak kut teh' } })
  fireEvent.click(screen.getByRole('button', { name: 'Find Food' }))
  await screen.findByText(/兴记肉骨茶/)
  return view
}

describe('a result', () => {
  it('renders mixed EN/MS/ZH text without dropping any of it', async () => {
    // PRD acceptance criterion A7. Chinese glyphs, a Malay phrase and English
    // all appear in one row, and none of them may be lost or transliterated.
    await renderWith([result()])
    expect(screen.getByText(/兴记肉骨茶 Hing Kee Bakuteh/)).toBeTruthy()
    expect(screen.getByText(/Sedap sangat/)).toBeTruthy()
    expect(screen.getByText(/汤底浓郁药材香/)).toBeTruthy()
  })

  it('shows the excerpt verbatim, not translated', async () => {
    await renderWith([result()])
    const quote = screen.getByText(/汤底浓郁药材香/)
    expect(quote.textContent).toContain('配白饭简直绝配')
  })

  it('links to the real post', async () => {
    await renderWith([result()])
    const link = screen.getByRole('link', { name: /RedNote/ })
    expect(link.getAttribute('href')).toBe('https://www.rednote.com/explore/abc')
  })

  it('does not render a result that carries no citation', async () => {
    // The invariant, at the last possible moment. It should never arrive.
    await renderWith([result({ citations: [] }), result()])
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('omits distance rather than inventing one when there is no coordinate', async () => {
    // Showing "0 m" would claim the venue is where the user is standing. A
    // venue with null coordinates stays rankable by preference instead.
    const { container } = await renderWith([result({ distance_m: null })])
    const meta = container.querySelector('.meta')
    expect(meta?.textContent).not.toMatch(/\d+\s*(m|km)\b/)
  })

  it('does show distance when there is a coordinate', async () => {
    const { container } = await renderWith([result({ distance_m: 1200 })])
    expect(container.querySelector('.meta')?.textContent).toContain('1.2 km')
  })
})
