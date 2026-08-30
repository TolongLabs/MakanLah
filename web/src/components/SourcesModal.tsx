import { useNavigate, useParams } from 'react-router-dom'
import { citable } from '../evidence'
import { count, dishLine, distance, platformName } from '../format'
import { useVenue } from '../routes/Venue'
import { MapPreview } from './MapPreview'
import { Modal } from './Modal'
import { VenueTrail } from './VenueTrail'

/**
 * The full citation trail, over the results rather than instead of them.
 *
 * **The URL still changes to `/r/:venueId`.** That is the point of doing this with a
 * route rather than a piece of component state: the evidence page is the most
 * shareable thing this product has, and an overlay that leaves the address bar on
 * `/discover` quietly takes that away. With the route driving it, the browser back
 * button closes the dialog, a refresh gives the full page, and the link a reader
 * copies still points at the evidence.
 *
 * **The head is a briefing, not a repeat of the card.** It carries what the reader
 * needs to act — where it is, how far, what it serves, how much writing stands
 * behind it — and then gets out of the way. Everything below it is the writing
 * itself, which is what the dialog is for and what gets the room.
 *
 * Rendered only when `location.state.backgroundLocation` is set, which a normal
 * click on All Sources supplies and a cold load does not — so the same href is an
 * overlay from the results and a page from anywhere else, with no duplicated
 * rendering to keep in step.
 */
export function SourcesModal() {
  const { venueId } = useParams()
  const navigate = useNavigate()
  const state = useVenue(venueId)
  // Back rather than a push to /discover: the results, their scroll position and the
  // query that produced them are all still behind this, and navigating forward to
  // them would throw all three away to arrive at the same address.
  const close = () => navigate(-1)

  if (state.status === 'loading') {
    return (
      <Modal title="Reading The Posts" onClose={close}>
        <p role="status">Fetching everything written about this one.</p>
      </Modal>
    )
  }

  if (state.status !== 'ready') {
    return (
      <Modal
        title={state.status === 'missing' ? 'Nobody Has Written About This One' : 'We Could Not Reach The Corpus'}
        onClose={close}
      >
        <p>
          {state.status === 'missing'
            ? 'There is no post behind it, so there is nothing here to show you. We would rather say that than pad it out.'
            : 'The venue is probably fine. We are not, just now. Try again in a moment.'}
        </p>
      </Modal>
    )
  }

  const { venue } = state.result
  const dist = distance(state.result.distance_m)
  const dishes = dishLine(venue.dishes, 6)
  // COUNTED FROM THE CITATIONS ON SCREEN, not from `venue.corroboration`.
  //
  // `add_corroboration` runs in `recommend()` and not in the direct venue lookup, so
  // the field is absent here -- and because this loads cache-first then overwrites
  // with the API's answer, reading it would show a number briefly and then lose it.
  // Counting what the trail below actually renders cannot drift from the trail, and
  // it is the same derivation `/r/:venueId` already uses.
  const cited = citable(state.result.citations)
  const platforms = [...new Set(cited.map((x) => x.platform))]
  const facts = [
    venue.area ? { k: 'Where', v: venue.area, lang: true } : null,
    dist ? { k: 'Distance', v: dist } : null,
    cited.length > 0
      ? { k: 'Evidence', v: `${count(cited.length, 'post')} · ${platforms.map(platformName).join(', ')}` }
      : null
  ].filter((f) => f != null)

  return (
    <Modal
      onClose={close}
      title={
        <span lang="und" className="modal-title-subject">
          {venue.name}
        </span>
      }
    >
      <div className="brief">
        <MapPreview src={venue.map_image_url} name={venue.name} href={venue.maps_url} />

        <div className="brief-facts">
          {/* Half the corpus has no area and a query without geolocation has no
              distance, so an empty list is a real outcome and renders as nothing
              rather than as an empty rule. */}
          {facts.length > 0 && (
            <dl className="brief-list">
              {facts.map((f) => (
                <div key={f.k}>
                  <dt>{f.k}</dt>
                  <dd lang={f.lang ? 'und' : undefined}>{f.v}</dd>
                </div>
              ))}
            </dl>
          )}

          {dishes && (
            <p className="brief-dishes">
              <span className="brief-label">Serves</span> <span lang="und">{dishes}</span>
            </p>
          )}

          {/* The only Directions on this flow now that the card carries two actions
              rather than three, and deliberately NOT a dialog of its own: Google Maps
              sets frame-ancestors and refuses to be embedded, so a Directions dialog
              could hold nothing but a link to Google Maps. Opening a tab already
              satisfies the requirement it would have served, which is not losing the
              results behind it. */}
          <a className="btn btn-quiet brief-go" href={venue.maps_url} target="_blank" rel="noreferrer noopener">
            Directions
          </a>
        </div>
      </div>

      <VenueTrail result={state.result} />
    </Modal>
  )
}
