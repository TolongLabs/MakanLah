import { Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
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

function Chromed() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/taste" element={<Taste />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/r/:venueId" element={<Venue />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
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
