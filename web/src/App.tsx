import { Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { Discover } from './routes/Discover'
import { Landing } from './routes/Landing'
import { SignIn } from './routes/SignIn'
import { SignUp } from './routes/SignUp'
import { Taste } from './routes/Taste'
import { Venue } from './routes/Venue'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sign-in" element={<SignIn />} />
        <Route path="/sign-up" element={<SignUp />} />
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
