import { useNavigate, useParams } from 'react-router-dom'
import { distance } from '../format'
import { useVenue } from '../routes/Venue'
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

  return (
    <Modal
      onClose={close}
      title={
        <span lang="und" className="modal-title-subject">
          {venue.name}
        </span>
      }
    >
      {(venue.area || dist) && (
        <p className="meta-line">
          {venue.area && <span>{venue.area}</span>}
          {dist && <span>{dist}</span>}
        </p>
      )}
      <VenueTrail result={state.result} />
      <p className="result-actions modal-actions">
        <a className="link" href={venue.maps_url} target="_blank" rel="noreferrer noopener">
          Directions
        </a>
      </p>
    </Modal>
  )
}
