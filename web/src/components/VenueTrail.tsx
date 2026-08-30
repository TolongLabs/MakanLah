import type { Result } from '../api'
import { citable, evidenceOf } from '../evidence'
import { platformName } from '../format'
import { Testimony } from './Testimony'

/**
 * Every post behind one venue, each openable.
 *
 * Extracted so the `/r/:venueId` page and the All Sources modal render the same
 * trail from the same code. They are the same evidence and they must not be able to
 * disagree — two renderings of the citation trail is two chances for one of them to
 * quietly drop a post, and the trail is the product.
 */
export function VenueTrail({ result }: { result: Result }) {
  const cited = citable(result.citations)
  return (
    <section className="trail">
      <h2 className="h-sub">Everything Written About It</h2>
      <p className="body-soft section-lede">
        {evidenceOf(result) === 'corroborated'
          ? 'Two platforms carry this place, written by different people.'
          : 'One platform carries this place so far.'}
      </p>
      <ul className="trail-list">
        {cited.map((c) => (
          <li className="trail-item" key={`${c.platform}:${c.post_url}`}>
            <div className="trail-source">
              <span>{platformName(c.platform)}</span>
              {c.posted_at && <span className="meta-line">{c.posted_at}</span>}
            </div>
            <Testimony citation={c} attributed={false} />
          </li>
        ))}
      </ul>
    </section>
  )
}
