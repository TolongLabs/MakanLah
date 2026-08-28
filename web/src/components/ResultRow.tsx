import { Link } from 'react-router-dom'
import type { Result } from '../api'
import { basisLine, leadPair } from '../evidence'
import { dishLine, distance } from '../format'
import { Testimony } from './Testimony'

/**
 * One pick. Ordered by visual weight per docs/DESIGN.md: rank in the margin, the venue
 * name as the label on the testimony, metadata, our claim, then the writing itself.
 *
 * `rank` is the position the re-rank assigned, passed in rather than derived from the
 * array index: a row whose citations are all unreachable does not render, and counting
 * positions in the list would then quietly renumber everything below it.
 *
 * When two platforms carry the venue, both excerpts render side by side, each under
 * its own source chip. The layout is the evidence claim, so nothing has to assert it.
 */
export function ResultRow({ result, rank, showBasis = true }: { result: Result; rank: number; showBasis?: boolean }) {
  const { venue, why } = result
  const pair = leadPair(result.citations)

  // The invariant at the last possible moment: a result without a reachable post is
  // not a result. It should never arrive, and if it does it does not render.
  if (!pair.length) return null

  const dist = distance(result.distance_m)
  const dishes = dishLine(venue.dishes)
  const basis = showBasis ? basisLine(result.match?.basis) : null

  return (
    <li className="result">
      <div className="rank" aria-hidden="true">
        {rank}
      </div>
      <div>
        <h3 className="venue-name" lang="und">
          <Link to={`/r/${venue.id}`}>
            <span className="sr-only">{`Rank ${rank}. `}</span>
            {venue.name}
          </Link>
        </h3>
        <p className="meta-line">
          {venue.area && <span>{venue.area}</span>}
          {dist && <span>{dist}</span>}
          {dishes && <span lang="und">{dishes}</span>}
        </p>
        {why && <p className="why">{why}</p>}
        {basis && <p className="basis">{basis}</p>}
        <div className={pair.length > 1 ? 'evidence evidence-pair' : 'evidence'}>
          {pair.map((c) => (
            <Testimony key={`${c.platform}:${c.post_url}`} citation={c} />
          ))}
        </div>
        <p className="result-actions">
          <Link className="link" to={`/r/${venue.id}`}>
            All Sources
          </Link>
          <a className="link" href={venue.maps_url} target="_blank" rel="noreferrer noopener">
            Directions
          </a>
        </p>
      </div>
    </li>
  )
}
