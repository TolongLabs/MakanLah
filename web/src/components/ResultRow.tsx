import { Link } from 'react-router-dom'
import type { Result } from '../api'
import { basisLine, citationHref, independentlyBacked, leadPair, sharedPostCount } from '../evidence'
import { dishLine, distance } from '../format'
import { Chop } from './Chop'
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
export function ResultRow({
  result,
  rank,
  showBasis = true,
  onAsk
}: {
  result: Result
  rank: number
  showBasis?: boolean
  /** Hands this venue to the companion. Absent on surfaces that have no companion,
      which is why the control is conditional rather than always rendered. */
  onAsk?: (venue: { id: string; name: string }) => void
}) {
  const { venue, why } = result
  const pair = leadPair(result.citations)

  // The invariant at the last possible moment: a result without a reachable post is
  // not a result. It should never arrive, and if it does it does not render.
  if (!pair.length) return null

  // Two independent voices saying the same thing is the strongest claim this
  // product can make, so the stamp is gated on it actually being true -- two
  // distinct posts by two distinct authors, not two platforms carrying one post.
  // #87: one listicle backed three of the top five and all three were stamped.
  const attested = independentlyBacked(result)
  // How many other picks on this same page lean on the same post. Non-zero means
  // the list is narrower than its length suggests, and the reader should see that.
  const shared = Math.max(0, ...pair.map(sharedPostCount))
  const dist = distance(result.distance_m)
  const dishes = dishLine(venue.dishes)
  const basis = showBasis ? basisLine(result.match?.basis) : null

  return (
    <li className="result">
      <div className="rank" aria-hidden="true">
        {rank}
      </div>
      <div className="result-body">
        {attested && (
          <span className="stamp" title="Two independent sources">
            <Chop size={54} />
            <span className="sr-only">Corroborated by two independent sources.</span>
          </span>
        )}
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
        {/* Two venues in the corpus read as the same name and are genuinely
            different restaurants, so two rows is right and silence is not. #58
            leaves `disambiguator` null when the corpus cannot tell them apart, and
            null is the honest answer: name the ambiguity rather than invent a label
            to fill the slot. */}
        {venue.ambiguous_with_sibling && (
          <p className="ambiguous">
            {venue.disambiguator
              ? `Another place shares this name. This is the one ${venue.disambiguator}.`
              : 'Another place in the corpus has the same name. The posts cannot tell them apart, so both are listed.'}
          </p>
        )}
        {why && <p className="why">{why}</p>}
        {basis && <p className="basis">{basis}</p>}
        {shared > 0 && (
          <p className="basis shared-source">
            {`One of these posts also backs ${shared === 1 ? 'another pick' : `${shared} other picks`} in this list.`}
          </p>
        )}
        <div className={pair.length > 1 ? 'evidence evidence-pair' : 'evidence'}>
          {pair.map((c) => (
            <Testimony key={`${c.platform}:${c.post_url}`} citation={c} href={citationHref(c, venue)} />
          ))}
        </div>
        <p className="result-actions">
          {onAsk && (
            <button type="button" className="ask-trigger" onClick={() => onAsk({ id: venue.id, name: venue.name })}>
              Ask About This
            </button>
          )}
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
