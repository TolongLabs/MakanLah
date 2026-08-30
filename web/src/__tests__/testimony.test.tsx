import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Citation } from '../api'
import { AskCompanion } from '../components/AskCompanion'
import { Testimony } from '../components/Testimony'

/**
 * The audit page is a RECORD, and that is why dead rows are labelled here rather
 * than dropped.
 *
 * The card is a pointer and a dead pointer is worth nothing, so #101 drops the
 * chip there. `/r/:id` is the other half of the promise: it is where somebody
 * checks the arithmetic behind a corroboration stamp, and hiding rows breaks that
 * — a venue whose stamp reads `posts: 4` over a page showing one row invites
 * exactly the doubt the stamp exists to answer.
 *
 * Two conditions, and they are asserted separately below because satisfying one
 * is the easy way to miss the other: no live-looking link that wastes a click,
 * and the excerpt stays, because the testimony is the substance and the URL is
 * only its provenance.
 *
 * Measured on prod before this: `/r/` for 兴记肉骨茶 showed [live, DEAD] and for
 * 興记肉骨茶 [live, live, DEAD], with no label on either.
 */
function citation(over: Partial<Citation> = {}): Citation {
  return {
    post_url: 'https://www.rednote.com/explore/abc',
    excerpt: '汤底浓郁药材香，肉质软烂入味。',
    platform: 'rednote',
    author_handle: 'momo',
    posted_at: '2026-08-01',
    ...over
  }
}

describe('Testimony for a post that no longer opens', () => {
  for (const attributed of [true, false]) {
    describe(attributed ? 'as a chip' : 'as a caption', () => {
      const dead = () => render(<Testimony citation={citation({ dead: true })} attributed={attributed} />)

      it('offers no link to click', () => {
        const { container } = dead()
        expect(container.querySelectorAll('a')).toHaveLength(0)
      })

      it('says so, rather than going quiet', () => {
        dead()
        // A row that simply lost its link reads as a rendering fault. The page has
        // to say what it found, because "we checked" is itself the evidence here.
        expect(screen.getByText(/no longer opens/i)).toBeTruthy()
      })

      it('keeps the excerpt, which is the part that is still true', () => {
        dead()
        expect(screen.getByText(/汤底浓郁药材香/)).toBeTruthy()
      })

      it('still names who wrote it', () => {
        dead()
        expect(screen.getByText(/momo/)).toBeTruthy()
      })
    })
  }

  it('leaves a live post alone', () => {
    const { container } = render(<Testimony citation={citation()} attributed={false} />)
    expect(container.querySelector('a')?.getAttribute('href')).toBe('https://www.rednote.com/explore/abc')
    expect(screen.queryByText(/no longer opens/i)).toBeNull()
  })

  it('treats an unchecked post as live', () => {
    // `dead: null` is "nobody has probed this yet", which is not the same claim as
    // dead and must not be rendered as one. A cooled-down re-probe resolved one of
    // these live on the venue with the strongest evidence in the corpus.
    const { container } = render(<Testimony citation={citation({ dead: null })} attributed={false} />)
    expect(container.querySelectorAll('a')).toHaveLength(1)
    expect(screen.queryByText(/no longer opens/i)).toBeNull()
  })
})

/**
 * The companion's own copy, which the Discover tests cannot see because they stub
 * her out. Measured on prod: the evidence-gap screen invited a tap on a pick while
 * rendering zero pickable cards, directly under a reading telling a user who had
 * just completed onboarding to complete onboarding.
 */
describe('the companion says only what is true of the screen she is on', () => {
  it('invites a tap only where there is something to tap', () => {
    const { rerender } = render(
      <AskCompanion evidence={null} degraded={false} phase="empty" target={null} onClear={() => {}} />
    )
    expect(screen.queryByText(/Tap Ask on any pick/i)).toBeNull()
    rerender(<AskCompanion evidence="single" degraded={false} phase="picks" target={null} onClear={() => {}} />)
    expect(screen.getByText(/Tap Ask on any pick/i)).toBeTruthy()
  })

  it('does not tell somebody who has searched to go and answer the questions', () => {
    render(<AskCompanion evidence={null} degraded={false} phase="empty" target={null} onClear={() => {}} />)
    expect(screen.queryByText(/Answer the four questions/i)).toBeNull()
  })

  it('still says it before anything has been searched', () => {
    render(<AskCompanion evidence={null} degraded={false} phase="idle" target={null} onClear={() => {}} />)
    expect(screen.getByText(/Answer the four questions/i)).toBeTruthy()
  })
})
