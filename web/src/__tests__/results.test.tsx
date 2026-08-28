import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Citation, Result } from '../api'
import { ResultRow } from '../components/ResultRow'

function citation(over: Partial<Citation> = {}): Citation {
  return {
    post_url: 'https://www.rednote.com/explore/abc',
    excerpt: '汤底浓郁药材香，肉质软烂入味，配白饭简直绝配！Sedap sangat.',
    platform: 'rednote',
    author_handle: 'author_ab12',
    posted_at: 'Feb 17',
    ...over
  }
}

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
    rank: 1,
    why: 'Rich herbal broth, and the locals keep going back.',
    distance_m: 1200,
    citations: [citation()],
    ...over
  }
}

function renderRow(r: Result) {
  return render(
    <MemoryRouter>
      <ol>
        <ResultRow result={r} rank={1} />
      </ol>
    </MemoryRouter>
  )
}

describe('a result', () => {
  it('renders mixed EN/MS/ZH text without dropping any of it', () => {
    // PRD acceptance criterion A7. Chinese glyphs, a Malay phrase and English all
    // appear in one row, and none of them may be lost or transliterated.
    renderRow(result())
    expect(screen.getByText(/兴记肉骨茶 Hing Kee Bakuteh/)).toBeTruthy()
    expect(screen.getByText(/Sedap sangat/)).toBeTruthy()
    expect(screen.getByText(/汤底浓郁药材香/)).toBeTruthy()
  })

  it('shows the excerpt verbatim, not translated', () => {
    renderRow(result())
    expect(screen.getByText(/汤底浓郁药材香/).textContent).toContain('配白饭简直绝配')
  })

  it('links to the real post', () => {
    renderRow(result())
    expect(screen.getByRole('link', { name: /RedNote/ }).getAttribute('href')).toBe(
      'https://www.rednote.com/explore/abc'
    )
  })

  it('does not render a result that carries no citation', () => {
    // The invariant at the last possible moment. It should never arrive.
    const { container } = renderRow(result({ citations: [] }))
    expect(container.querySelectorAll('li.result')).toHaveLength(0)
  })

  it('omits distance rather than inventing one when there is no coordinate', () => {
    // Showing "0 m" would claim the venue is where the user is standing. A venue with
    // null coordinates stays rankable by preference instead.
    const { container } = renderRow(result({ distance_m: null }))
    expect(container.querySelector('.meta-line')?.textContent).not.toMatch(/\d+\s*(m|km)\b/)
  })

  it('does show distance when there is a coordinate', () => {
    const { container } = renderRow(result({ distance_m: 1200 }))
    expect(container.querySelector('.meta-line')?.textContent).toContain('1.2 km')
  })

  it('never renders the retrieval score, which orders nothing the user sees', () => {
    // docs/TRD.md dropped `score` because it reported retrieval cosine while ordering
    // came from the re-rank, so a higher number could appear below a lower one.
    const { container } = renderRow(result({ score: 0.5705 }))
    expect(container.textContent).not.toContain('0.57')
  })
})

describe('evidence on a row', () => {
  it('shows both excerpts when two platforms carry the venue', () => {
    // The layout is the corroboration claim, so this is the assertion that the claim
    // is actually being made.
    const { container } = renderRow(
      result({
        citations: [
          citation(),
          citation({ post_url: 'https://maps.example/1', platform: 'google_maps', excerpt: 'Queue means something.' })
        ]
      })
    )
    expect(container.querySelectorAll('.excerpt')).toHaveLength(2)
    expect(container.querySelector('.evidence-pair')).toBeTruthy()
  })

  it('shows one excerpt when the same platform carries it twice', () => {
    // Two posts from one platform is one source saying it twice. Rendering that as a
    // pair would dress a single source up as agreement.
    const { container } = renderRow(
      result({
        citations: [citation(), citation({ post_url: 'https://www.rednote.com/explore/def', excerpt: '也很好吃' })]
      })
    )
    expect(container.querySelectorAll('.excerpt')).toHaveLength(1)
    expect(container.querySelector('.evidence-pair')).toBeNull()
  })

  it('pairs every excerpt with its own source chip', () => {
    const { container } = renderRow(
      result({
        citations: [
          citation(),
          citation({ post_url: 'https://maps.example/1', platform: 'google_maps', excerpt: 'Queue means something.' })
        ]
      })
    )
    for (const fig of container.querySelectorAll('figure.testimony')) {
      expect(within(fig as HTMLElement).getByRole('link')).toBeTruthy()
    }
  })

  it('says why an entry is present when the API reports a basis', () => {
    renderRow(result({ match: { basis: 'semantic' } }))
    expect(screen.getByText(/close in meaning/i)).toBeTruthy()
  })

  it('says nothing about basis when the API does not report one', () => {
    const { container } = renderRow(result())
    expect(container.querySelector('.basis')).toBeNull()
  })
})

describe('the rank numeral', () => {
  it('shows the position the re-rank assigned, not the row it happens to occupy', () => {
    // A result whose citations are all unreachable does not render. Counting positions
    // in the list would renumber everything below it and quietly disagree with the API.
    const { container } = render(
      <MemoryRouter>
        <ol>
          <ResultRow result={result({ citations: [] })} rank={1} />
          <ResultRow result={result({ rank: 2 })} rank={2} />
        </ol>
      </MemoryRouter>
    )
    expect(container.querySelector('.rank')?.textContent).toBe('2')
  })
})

describe('the landing page never puts an image near evidence', () => {
  it('has no img inside a result row', async () => {
    // docs/DESIGN.md: a generated image beside a cited pick is a fabricated image on
    // the one surface claiming nothing is fabricated. The closing band is the only
    // photograph on the site and it names no venue.
    const { container } = renderRow(result())
    expect(container.querySelectorAll('img')).toHaveLength(0)
  })
})
