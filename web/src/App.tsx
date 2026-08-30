import { type Location, Route, Routes, useLocation } from 'react-router-dom'
import { Shell } from './components/Shell'
import { SourcesModal } from './components/SourcesModal'
import { Dashboard } from './routes/Dashboard'
import { Discover } from './routes/Discover'
import { Landing } from './routes/Landing'
import { Privacy } from './routes/Privacy'
import { SignIn } from './routes/SignIn'
import { SignUp } from './routes/SignUp'
import { Taste } from './routes/Taste'
import { Venue } from './routes/Venue'

/**
 * Two route groups, because the auth screens are not the same kind of page.
 *
 * They render with no top bar and no footer: the dual pane IS the screen. A nav
 * offering Discover and Get Started beside a sign-in form is three ways out of the
 * one screen whose entire job is to be finished, and a footer under it invites a
 * scroll on a page that should not have one.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/sign-up" element={<SignUp />} />
      <Route path="*" element={<Chromed />} />
    </Routes>
  )
}

/**
 * `/r/:venueId` renders two ways from one route, and which one depends on where the
 * reader came from.
 *
 * Clicking All Sources on a result sets `backgroundLocation`, so the results stay
 * mounted underneath and the trail opens over them — nothing is lost, the scroll
 * position survives, and browser back closes the dialog. A cold load, a refresh, a
 * shared link or a cmd-click has no such state and gets the full page.
 *
 * The alternative, a piece of component state on /discover, would have kept the
 * address bar on /discover while the reader looked at one venue's evidence. The
 * citation trail is the most shareable thing this product has; a URL that does not
 * follow the reader to it is a link they cannot send anybody.
 */
function Chromed() {
  const location = useLocation()
  const background = (location.state as { backgroundLocation?: Location } | null)?.backgroundLocation

  return (
    <Shell>
      <Routes location={background ?? location}>
        <Route path="/" element={<Landing />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/taste" element={<Taste />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/r/:venueId" element={<Venue />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      {background && (
        <Routes>
          <Route path="/r/:venueId" element={<SourcesModal />} />
        </Routes>
      )}
    </Shell>
  )
}

function NotFound() {
  return (
    <div className="page empty empty-centred">
      <h1 className="h-sub">That Page Is Not Here</h1>
      <p>Nothing at this address. The four questions are the way in.</p>
      <p>
        <a className="btn btn-primary" href="/taste">
          Find Food
        </a>
      </p>
    </div>
  )
}
