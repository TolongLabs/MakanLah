import { Link, useLocation } from 'react-router-dom'
import type { Result } from '../api'
import {
  citationHref,
  independentlyBacked,
  leadPair,
  mentionLine,
  sharedPostCount,
  whyDetail,
  whyRow
} from '../evidence'
import { Chop } from './Chop'
import { Testimony } from './Testimony'

/**
 * One pick.
 *
 * **The card answers "why is this here" in its subtitle now, and that is the whole
 * point of this version.** The answer was always on the card — `basisLine` has said
 * "Here because a post names this dish" from the first build — but it sat eighth in
 * a stack of five grey sentences, below a model-written blurb, in the same treatment
 * as two lines answering different questions. The owner read his own results page
 * and reported that nothing told him why anything was there. The data was never
 * missing; the hierarchy buried it.
 *
 * So the answer moved up, absorbed the metadata line that used to occupy that slot,
 * and took the corroboration counts with it. Three lines became one that says more:
 * `Names char siew · 2 posts · 9.4 km`.
 *
 * **The model-written `why` no longer renders here.** It answered the same question
 * the fact row now answers, and of the two only one can be checked against a post.
 * On a page whose entire claim is "every result cites its source", the unverifiable
 * sentence is the one that goes. It still renders on `/r/:venueId`, where there is
 * room to be discursive and no ranked list making a comparison out of it.
 *
 * Everything the row has no space for goes behind a per-card disclosure, which is
 * the only honest way to serve "more informative AND briefer at once". `whyDetail`
 * returns nothing where the row already said it all, and then no disclosure renders
 * — a control that opens onto an empty box is worse than no control.
 */
export function ResultRow({
  result,
  rank,
  gaps = [],
  onAsk
}: {
  result: Result
  rank: number
  /** What the corpus cannot answer about this query. A row says which of them a
      real post about IT mentions -- and says nothing at all for the rest, because
      silence in the corpus is not a "no" about the restaurant. */
  gaps?: string[]
  /** Hands this venue to the ask dialog. Absent on surfaces that have none, which
      is why the control is conditional rather than always rendered. */
  onAsk?: (venue: { id: string; name: string }) => void
}) {
  const location = useLocation()
  const { venue } = result
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
  const facts = whyRow(result)
  const detail = whyDetail(result, shared)
  // Only where somebody actually wrote about it. A row with nothing to say here
  // renders nothing: adding "no halal information" to every other card would turn
  // a fact about the corpus into an implied verdict on the restaurant, which is
  // the one error a Malaysian user will not forgive.
  const mentioned = gaps.filter((g) => (venue.gap_mentions ?? []).includes(g))

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

        {facts.length > 0 && (
          <p className="why-row">
            {facts.map((f) => (
              <span
                key={f.key}
                className={f.lead ? 'why-lead' : 'why-fact'}
                // The matched dish is a corpus string and may be in any of three
                // scripts; the counts and the distance are ours and are English.
                lang={f.lead ? 'und' : undefined}
              >
                {f.text}
              </span>
            ))}
          </p>
        )}

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
        {mentioned.map((g) => (
          <p className="basis mentions-gap" key={g}>
            {mentionLine(g)}
          </p>
        ))}

        <div className={pair.length > 1 ? 'evidence evidence-pair' : 'evidence'}>
          {pair.map((c) => (
            <Testimony key={c.post_id ?? `${c.platform}:${c.post_url}`} citation={c} href={citationHref(c, venue)} />
          ))}
        </div>

        {detail.length > 0 && (
          <details className="why-more">
            <summary className="why-more-toggle">Why This Showed</summary>
            <div className="why-more-body">
              {detail.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          </details>
        )}

        <p className="result-actions">
          {onAsk && (
            <button type="button" className="ask-trigger" onClick={() => onAsk({ id: venue.id, name: venue.name })}>
              Ask About This
            </button>
          )}
          {/* A real link that a modal intercepts, never a button dressed as one.
              Cmd-click, middle-click and Open In New Tab all have to reach the full
              page, and `backgroundLocation` is what lets the same href render as an
              overlay on a normal click and as a page on a cold load. */}
          <Link className="link" to={`/r/${venue.id}`} state={{ backgroundLocation: location }}>
            All Sources
          </Link>
          {/* NOT a modal, deliberately. Google Maps sets frame-ancestors and refuses
              to be embedded, so a Directions dialog could only ever contain a link to
              Google Maps -- one extra click to reach where this already goes. And the
              stated requirement, not leaving the results behind, is already met: this
              opens a tab. */}
          <a className="link" href={venue.maps_url} target="_blank" rel="noreferrer noopener">
            Directions
          </a>
        </p>
      </div>
    </li>
  )
}
