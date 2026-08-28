import { Link, useParams } from 'react-router-dom'
import { Testimony } from '../components/Testimony'
import { citable, evidenceOf } from '../evidence'
import { dishLine, distance, platformName } from '../format'
import { cachedVenue } from '../venueCache'

/**
 * The full citation trail for one pick: every post, grouped by platform, each one
 * openable. This is the page the whole product points at, so it shows all of the
 * evidence rather than the two excerpts a result row has room for.
 */
export function Venue() {
  const { venueId } = useParams()
  const result = venueId ? cachedVenue(venueId) : null

  if (!result) return <ColdLoad />

  const { venue, why } = result
  const cited = citable(result.citations)
  const dist = distance(result.distance_m)
  const dishes = dishLine(venue.dishes, 8)
  const platforms = [...new Set(cited.map((c) => c.platform))]

  return (
    <div className="page">
      <p className="section-lede">
        <Link className="link" to="/discover">
          Back To Results
        </Link>
      </p>
      <header className="venue-head">
        <h1 className="venue-title" lang="und">
          {venue.name}
        </h1>
        <p className="meta-line">
          {venue.area && <span>{venue.area}</span>}
          {dist && <span>{dist}</span>}
          <span>
            {cited.length === 1 ? '1 post' : `${cited.length} posts`}
            {platforms.length > 1 ? `, ${platforms.map(platformName).join(' and ')}` : ''}
          </span>
        </p>
        {dishes && (
          <p className="why" lang="und">
            {dishes}
          </p>
        )}
        {why && <p className="why">{why}</p>}
        <p className="result-actions">
          <a className="link" href={venue.maps_url} target="_blank" rel="noreferrer noopener">
            Directions
          </a>
        </p>
      </header>

      <section className="trail">
        <h2 className="h-sub">Everything Written About It</h2>
        <p className="body-soft section-lede">
          {evidenceOf(result) === 'corroborated'
            ? 'Two platforms carry this place, written by different people.'
            : 'One platform carries this place so far.'}
        </p>
        <ul className="section-lede">
          {cited.map((c) => (
            <li className="trail-item" key={`${c.platform}:${c.post_url}`}>
              <div className="trail-source">
                <span>{platformName(c.platform)}</span>
                {c.posted_at && <span className="meta-line">{c.posted_at}</span>}
              </div>
              <Testimony citation={c} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

/** Deep-linked, or opened in a new tab, so the search that produced this pick is not
    in this tab's memory. Said plainly rather than rendered as an empty trail. */
function ColdLoad() {
  return (
    <div className="page empty empty-centred">
      <h1 className="h-sub">We Do Not Have This One Loaded</h1>
      <p>A venue page is built from the search that found it, and this tab has no search in it yet.</p>
      <p>
        <Link className="btn btn-primary" to="/taste">
          Find Food
        </Link>
      </p>
    </div>
  )
}
