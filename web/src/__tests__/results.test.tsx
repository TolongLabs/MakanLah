import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Result } from '../api'
import { ResultRow } from '../components/ResultRow'
import { citation, result } from './fixtures/result'

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
    expect(container.querySelector('.why-row')?.textContent ?? '').not.toMatch(/\d+\s*(m|km)\b/)
  })

  it('does show distance when there is a coordinate', () => {
    const { container } = renderRow(result({ distance_m: 1200 }))
    expect(container.querySelector('.why-row')?.textContent).toContain('1.2 km')
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
    expect(container.querySelector('.why-lead')).toBeNull()
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

/**
 * What the corpus cannot answer, on the page rather than only in the payload.
 *
 * UAT, Malay persona: `tempat makan halal untuk keluarga` returned a list under
 * "None of these match your words exactly" — a RELEVANCE disclaimer standing in
 * for a COVERAGE one. `coverage_gaps: ['halal']` was in the response the whole
 * time and nothing rendered it, so the page stayed silent about the one thing
 * she came to find out. Her verdict was MAYBE, and this is why.
 *
 * The live payload for that query, which these fixtures mirror: rank 1 Hock Kee
 * with `gap_mentions: ['halal']` — a real person wrote 清真友好 — and rank 2 鱼你
 * with `[]`.
 */
describe('a coverage gap is said on the row that earned it and nowhere else', () => {
  const withGap = (mentions: string[]) =>
    result({
      venue: {
        id: 'v9',
        name: 'Hock Kee Heritage',
        area: null,
        lat: null,
        lng: null,
        maps_url: '',
        dishes: [],
        gap_mentions: mentions
      }
    })

  it('says so where somebody actually wrote about it', () => {
    render(
      <MemoryRouter>
        <ResultRow result={withGap(['halal'])} rank={1} gaps={['halal']} />
      </MemoryRouter>
    )
    expect(screen.getByText(/mentions halal/i)).toBeTruthy()
  })

  it('stays silent on a row nobody wrote about', () => {
    // The important half. "No halal information" on every other card converts a
    // fact about the corpus into an implied verdict on the restaurant, which is
    // the one error a Malaysian user will not forgive.
    render(
      <MemoryRouter>
        <ResultRow result={withGap([])} rank={2} gaps={['halal']} />
      </MemoryRouter>
    )
    expect(screen.queryByText(/halal/i)).toBeNull()
  })

  it('says nothing at all when the query raised no gap', () => {
    render(
      <MemoryRouter>
        <ResultRow result={withGap(['halal'])} rank={1} gaps={[]} />
      </MemoryRouter>
    )
    expect(screen.queryByText(/mentions halal/i)).toBeNull()
  })

  it('never states the venue IS halal', () => {
    // #123: `Dinyatakan halal` overstates 清真友好. A person's word is not a
    // certification, and the row must report who said it rather than assert it.
    render(
      <MemoryRouter>
        <ResultRow result={withGap(['halal'])} rank={1} gaps={['halal']} />
      </MemoryRouter>
    )
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/Somebody writing about this one mentions halal/i)
    expect(text).not.toMatch(/is halal|halal certified|Dinyatakan halal/i)
  })
})
