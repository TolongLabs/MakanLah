import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, venue as fetchVenue, type Result } from '../api'
import { Testimony } from '../components/Testimony'
import { citable, evidenceOf } from '../evidence'
import { dishLine, distance, platformName } from '../format'
import { cachedVenue } from '../venueCache'

type State = { status: 'loading' } | { status: 'ready'; result: Result } | { status: 'missing' } | { status: 'failed' }

/**
 * The full citation trail for one pick: every post, grouped by platform, each one
 * openable. This is the page the whole product points at, so it shows all of the
 * evidence rather than the two excerpts a result row has room for.
 *
 * The cached copy of the last search renders first when there is one, so arriving
 * from /discover is instant, and GET /venue/{id} is still the source of truth. A cold
 * load, a deep link or a new tab therefore works the same as a click.
 */
export function Venue() {
  const { venueId } = useParams()
  const [state, setState] = useState<State>(() => {
    const hit = venueId ? cachedVenue(venueId) : null
    return hit ? { status: 'ready', result: hit } : { status: 'loading' }
  })

  useEffect(() => {
    if (!venueId) return
    let live = true
    fetchVenue(venueId)
      .then((r) => live && setState({ status: 'ready', result: r }))
      .catch((err) => {
        if (!live) return
        // A cached copy beats an error page. Only fall through when there is none.
        setState((prev) =>
          prev.status === 'ready'
            ? prev
            : { status: err instanceof ApiError && err.status === 404 ? 'missing' : 'failed' }
        )
      })
    return () => {
      live = false
    }
  }, [venueId])

  if (state.status === 'loading') return <Waiting />
  if (state.status === 'missing') return <NotCited />
  if (state.status === 'failed') return <Unreachable />

  const result = state.result
  const { venue, why } = result
  const cited = citable(result.citations)
  const dist = distance(result.distance_m)
  const dishes = dishLine(venue.dishes, 8)
  const platforms = [...new Set(cited.map((c) => c.platform))]

  return (
    <div className="page">
      <p className="venue-back">
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
        {/* Null on a direct lookup, because nothing was ranked and nothing was matched.
            The page says less rather than inventing a reason this venue is here. */}
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
    </div>
  )
}

function Waiting() {
  return (
    <div className="page empty">
      <p role="status">Reading the posts.</p>
    </div>
  )
}

/** 404 from the API: the venue exists in nobody's writing. Saying so is the product
    working, not the product failing. */
function NotCited() {
  return (
    <div className="page empty empty-centred">
      <h1 className="h-sub">Nobody Has Written About This One</h1>
      <p>There is no post behind it, so there is nothing here to show you. We would rather say that than pad it out.</p>
      <p>
        <Link className="btn btn-primary" to="/taste">
          Find Food
        </Link>
      </p>
    </div>
  )
}

function Unreachable() {
  return (
    <div className="page empty empty-centred">
      <h1 className="h-sub">We Could Not Reach The Corpus</h1>
      <p>The venue is probably fine. We are not, just now. Try again in a moment.</p>
      <p>
        <Link className="btn btn-primary" to="/discover">
          Back To Results
        </Link>
      </p>
    </div>
  )
}
