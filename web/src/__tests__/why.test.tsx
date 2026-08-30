import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Result } from '../api'
import { ResultRow } from '../components/ResultRow'
import { VenueTrail } from '../components/VenueTrail'
import { citable, sentimentLine, sentimentPhrase, whyDetail, whyRow } from '../evidence'
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

describe('the why-row answers the question the old card buried', () => {
  it('leads with what matched', () => {
    const tokens = whyRow(result({ match: { basis: 'dish', dish: 'bak kut teh', similarity: 0.57 } }))
    expect(tokens[0]?.lead).toBe(true)
    expect(tokens[0]?.text).toBe('Names bak kut teh')
  })

  it('NEVER renders a similarity, including the 0.0 a strong lexical hit carries', () => {
    // The measured case, not a hypothetical. Sampling 35 live results across five
    // queries: 15 carry `basis: 'dish'` with `similarity: 0.0` -- 63% of every dish
    // match. 興记肉骨茶 is one of them, a venue the lexical lane found and the vector
    // lane never saw. Printed as a percentage that reads "0% match" on one of the
    // best answers the corpus holds.
    const { container } = renderRow(
      result({ venue: { name: '興记肉骨茶' }, match: { basis: 'dish', dish: 'bak kut teh', similarity: 0.0 } })
    )
    const text = container.textContent ?? ''
    expect(text).toContain('Names bak kut teh')
    expect(text).not.toMatch(/0\.0|0\s*%/)
  })

  it('never says people when the corpus has no author for them', () => {
    // 12 of the 35 sampled results carry `authors: 0` -- Google Maps reviewers are
    // anonymous, and an absent handle is unknown rather than a second person.
    const tokens = whyRow(result({ venue: { corroboration: { posts: 1, authors: 0, platforms: 1 } } }))
    const text = tokens.map((t) => t.text).join(' · ')
    expect(text).toContain('1 post')
    expect(text).not.toMatch(/person|people|\b0\b/)
  })

  it('says people only where two of them make it a claim worth making', () => {
    const one = whyRow(result({ venue: { corroboration: { posts: 2, authors: 1, platforms: 1 } } }))
    expect(one.map((t) => t.text).join(' ')).not.toMatch(/person|people/)

    const two = whyRow(result({ venue: { corroboration: { posts: 3, authors: 2, platforms: 2 } } }))
    expect(two.map((t) => t.text).join(' ')).toContain('2 people')
  })

  it('drops area rather than inventing one', () => {
    // Absent on 19 of 35 sampled results, so it is the last token and never
    // load-bearing. A card with no area simply has one fewer fact on it.
    const without = whyRow(result({ venue: { area: null } }))
    expect(without.some((t) => t.key === 'area')).toBe(false)
    const withArea = whyRow(result({ venue: { area: 'Cheras' } }))
    expect(withArea.at(-1)).toMatchObject({ key: 'area', text: 'Cheras' })
  })

  it('says nothing at all rather than guessing when the API reports no basis', () => {
    const tokens = whyRow(
      result({ match: undefined, venue: { corroboration: undefined, area: null }, distance_m: null })
    )
    expect(tokens).toHaveLength(0)
  })
})

describe('the disclosure only opens onto something', () => {
  it('renders no expander when the row already said everything', () => {
    const { container } = renderRow(
      result({
        match: undefined,
        venue: { dishes: [], corroboration: { posts: 1, authors: 1, platforms: 1 }, sentiment: null }
      })
    )
    expect(container.querySelector('.why-more')).toBeNull()
  })

  it('renders one when there is more to say', () => {
    const { container } = renderRow(
      result({ match: { basis: 'dish', dish: 'bak kut teh' }, venue: { dishes: ['肉骨茶', '排骨'] } })
    )
    const more = container.querySelector('.why-more')
    expect(more).toBeTruthy()
    expect(within(more as HTMLElement).getByText(/also serves/i).textContent).toContain('排骨')
  })

  it('leaves the matched dish out of "also serves", since the subtitle already named it', () => {
    const lines = whyDetail(
      result({ match: { basis: 'dish', dish: 'char siew' }, venue: { dishes: ['Char Siew', 'wantan mee'] } })
    )
    const also = lines.find((l) => l.startsWith('Also serves'))
    expect(also).toBe('Also serves: wantan mee')
  })

  it('reports the platform count, which is the one thing the row has no room for', () => {
    const lines = whyDetail(result({ venue: { corroboration: { posts: 3, authors: 2, platforms: 2 } } }))
    expect(lines.some((l) => l.includes('across 2 platforms'))).toBe(true)
  })

  it('stays quiet about corroboration on a single platform, which the row already covered', () => {
    const lines = whyDetail(result({ venue: { corroboration: { posts: 3, authors: 2, platforms: 1 } } }))
    expect(lines.some((l) => /across/.test(l))).toBe(false)
  })
})

describe('sentiment is held until the buckets can be trusted', () => {
  it('renders nothing at all, in either direction', () => {
    // Measured across four queries: of ten venues carrying a negative bucket, EIGHT
    // contain no negative language whatsoever. 王美记 buckets 0 positive / 2 negative
    // on excerpts saying "deserves 5 stars" and "definitely worth checking out", and
    // this module would render that as "2 of 2 posts critical" -- a verdict about a
    // real restaurant the posts do not support.
    //
    // Both directions, deliberately. Showing only the favourable half would bias
    // every card toward good news, which is worse than showing neither. #149.
    expect(sentimentLine({ positive: 4, mixed: 0, negative: 0 }, 4)).toBeNull()
    expect(sentimentLine({ positive: 1, mixed: 1, negative: 2 }, 4)).toBeNull()
  })
})

describe('sentiment is counts, never an average', () => {
  it('leads with the complaint wherever there is one', () => {
    // `makanlah` buckets asymmetrically -- positive >= 0.6, negative <= -0.2 -- so a
    // single negative is somebody with a real complaint rather than a mild review
    // rounded down. Burying it under a positive majority is the one thing this line
    // must not do.
    expect(sentimentPhrase({ positive: 3, mixed: 2, negative: 4 }, 9)).toBe(
      'Of the 9 posts here: 4 critical, 3 positive, 2 mixed.'
    )
    expect(sentimentPhrase({ positive: 9, mixed: 0, negative: 1 }, 10)).toMatch(/^Of the 10 posts here: 1 critical/)
  })

  it('prints unanimity, because unanimity turned out to be the rare case', () => {
    // The first draft stayed silent here, reasoning that a label reading "positive"
    // everywhere discriminates nothing. Measured, that reasoning was backwards: 163
    // of 186 multi-mention venues span more than one bucket, so agreement is the
    // 12% case and is the informative one.
    expect(sentimentPhrase({ positive: 4, mixed: 0, negative: 0 }, 4)).toBe('Of the 4 posts here: all positive.')
    expect(sentimentPhrase({ positive: 0, mixed: 3, negative: 0 }, 3)).toBe('Of the 3 posts here: all mixed.')
  })

  it('scopes itself to the posts actually cited', () => {
    // Citations are trimmed to `per_venue` before they ship, so the breakdown
    // describes the posts on screen and not the venue's whole record. A venue whose
    // only critical review missed the trim shows none, and an unscoped "All 3 posts
    // positive" would claim more than we know.
    expect(sentimentPhrase({ positive: 3, mixed: 0, negative: 0 }, 3)).toMatch(/^Of the 3 posts here:/)
    expect(sentimentPhrase({ positive: 3, mixed: 0, negative: 0 }, 3)).not.toMatch(/^All /)
  })

  it('splits a mixed reading without an average', () => {
    expect(sentimentPhrase({ positive: 3, mixed: 1, negative: 0 }, 4)).toBe('Of the 4 posts here: 3 positive, 1 mixed.')
  })

  it('REFUSES to print when the counts are not about the same posts', () => {
    // The live bug this gate exists for. `sentiment` counts mention rows, not posts:
    // of ten live `nasi lemak` results, NINE disagreed with the card's own post
    // count. Village Park reads 3 openable posts against 15 sentiment entries, so an
    // ungated line puts "1 post" in the subtitle and "All 9 posts positive" four
    // lines under it -- self-contradicting, and inflating the evidence behind a pick
    // exactly the way counting dead citations did in #111.
    expect(sentimentPhrase({ positive: 9, mixed: 0, negative: 0 }, 1)).toBeNull()
    expect(sentimentPhrase({ positive: 12, mixed: 3, negative: 0 }, 3)).toBeNull()
  })

  it('stays silent on a single post, where the excerpt below IS the sentiment', () => {
    expect(sentimentPhrase({ positive: 1, mixed: 0, negative: 0 }, 1)).toBeNull()
    expect(sentimentPhrase(null, 3)).toBeNull()
    expect(sentimentPhrase(undefined, 3)).toBeNull()
  })
})

describe('the actions row', () => {
  it('keeps All Sources a real link, so cmd-click and Open In New Tab still reach the page', () => {
    // A button dressed as a link cannot be opened in a new tab, and the citation
    // trail is the most shareable thing this product has.
    renderRow(result({ venue: { id: 'v9' } }))
    expect(screen.getByRole('link', { name: 'All Sources' }).getAttribute('href')).toBe('/r/v9')
  })

  it('leaves Directions pointing straight at Maps rather than at a dialog', () => {
    // Google Maps sets frame-ancestors and refuses to be embedded, so a Directions
    // modal could only ever hold a link to Google Maps -- one extra click to reach
    // where this already goes.
    renderRow(result())
    const link = screen.getByRole('link', { name: 'Directions' })
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('href')).toContain('google.com/maps')
  })

  it('drops the model-written line from a ranked card', () => {
    // It answered the same question the fact row now answers, and of the two only
    // one can be checked against a post. On a page whose whole claim is that every
    // result cites its source, the unverifiable sentence is the one that goes. It
    // still renders on /r/:venueId.
    const { container } = renderRow(result({ why: 'A rich peppery broth regulars queue for.' }))
    expect(container.textContent).not.toContain('regulars queue for')
  })
})

describe('a row with two platforms still pairs its evidence', () => {
  it('does not lose the second excerpt to the restructure', () => {
    const { container } = renderRow(
      result({
        citations: [
          citation(),
          citation({ post_url: 'https://maps.example/1', platform: 'google_maps', excerpt: 'Queue means something.' })
        ]
      })
    )
    expect(container.querySelectorAll('.excerpt')).toHaveLength(2)
  })
})

describe('a citation is identified by its post, not by its address', () => {
  // #153. Google Maps has no per-review URL, so `review_url()` returns the venue's
  // page and ~8 reviews share it: 1388 Maps mentions across 178 distinct URLs.
  // Keyed on the URL, Upper House shipped three plainly different reviewers,
  // rendered ONE, and was denied the corroboration stamp it had earned.
  const upperHouse = [
    citation({
      post_id: 'p1',
      post_url: 'https://maps.example/upper',
      platform: 'google_maps',
      author_handle: null,
      excerpt: 'Really love the refined Malaysian flavours here.'
    }),
    citation({
      post_id: 'p2',
      post_url: 'https://maps.example/upper',
      platform: 'google_maps',
      author_handle: null,
      excerpt: 'We came across the restaurant by chance.'
    }),
    citation({
      post_id: 'p3',
      post_url: 'https://maps.example/upper',
      platform: 'google_maps',
      author_handle: null,
      excerpt: 'Very pleasant, you could see the Merdeka 118.'
    })
  ]

  it('keeps three reviewers that happen to share one URL', () => {
    expect(citable(upperHouse)).toHaveLength(3)
  })

  it('renders all three in the trail rather than collapsing them', () => {
    const { container } = render(<VenueTrail result={result({ citations: upperHouse })} />)
    expect(container.querySelectorAll('.trail-item')).toHaveLength(3)
    const text = container.textContent ?? ''
    expect(text).toContain('refined Malaysian flavours')
    expect(text).toContain('by chance')
    expect(text).toContain('Merdeka 118')
  })

  it('still collapses the SAME post seen more than once', () => {
    // The dedupe is still necessary and still right. Showing one post twice inflates
    // the number nobody should be able to inflate by accident.
    const twice = [citation({ post_id: 'p1' }), citation({ post_id: 'p1' }), citation({ post_id: 'p1' })]
    expect(citable(twice)).toHaveLength(1)
  })

  it('falls back to the URL when the API has not sent an identity yet', () => {
    // A client build can outrun the API. The fallback is the old behaviour, which
    // errs toward showing less rather than duplicating a post.
    const noId = [
      citation({ post_url: 'https://a' }),
      citation({ post_url: 'https://a' }),
      citation({ post_url: 'https://b' })
    ]
    expect(citable(noId)).toHaveLength(2)
  })
})
