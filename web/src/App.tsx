import { type FormEvent, useState } from 'react'
import { type RecommendResponse, type Result, recommend } from './api'
import { dishLine, distance, sourceLabel } from './format'

type Geo = { lat: number; lng: number } | null

const RADII = [
  { label: 'Anywhere In KL', value: 0 },
  { label: 'Within 2 km', value: 2000 },
  { label: 'Within 5 km', value: 5000 },
  { label: 'Within 10 km', value: 10000 }
]

export default function App() {
  const [query, setQuery] = useState('')
  const [radius, setRadius] = useState(0)
  const [geo, setGeo] = useState<Geo>(null)
  const [geoRefused, setGeoRefused] = useState(false)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<RecommendResponse | null>(null)
  const [failed, setFailed] = useState(false)
  const [asked, setAsked] = useState('')

  function locate() {
    if (!navigator.geolocation) {
      setGeoRefused(true)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setGeo({ lat: p.coords.latitude, lng: p.coords.longitude })
        setGeoRefused(false)
      },
      // Refusing location must never dead-end the app: it falls back to KL-wide.
      () => setGeoRefused(true),
      { timeout: 8000 }
    )
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    setLoading(true)
    setFailed(false)
    setAsked(q)
    try {
      const useRadius = radius > 0 && geo
      setData(
        await recommend({
          query: q,
          limit: 10,
          ...(useRadius ? { lat: geo.lat, lng: geo.lng, radius_m: radius } : {})
        })
      )
    } catch {
      setData(null)
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="wrap">
      <header className="masthead">
        <h1 className="wordmark">MakanLah</h1>
        <p className="tagline">Where to eat in KL, with the post behind every pick.</p>
      </header>

      <form className="search" onSubmit={onSubmit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="what do you feel like eating?"
          aria-label="What you feel like eating"
          enterKeyHint="search"
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Finding…' : 'Find Food'}
        </button>
      </form>

      <div className="controls">
        <label>
          Distance
          <select value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
            {RADII.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        {radius > 0 && !geo && (
          <button type="button" onClick={locate}>
            Use My Location
          </button>
        )}
        {geo && <span>Located</span>}
      </div>

      {geoRefused && (
        <p className="notice-plain">
          We could not get your location, so this searches all of KL. Distances are hidden.
        </p>
      )}
      {data?.degraded && (
        <p className="notice">A source was unreachable at the last refresh, so this may be incomplete.</p>
      )}
      {failed && <p className="notice">We could not reach the corpus. Nothing is lost — try again in a moment.</p>}

      {data && data.results.length > 0 && (
        <ol className="results">
          {data.results.map((r, i) => (
            <ResultRow key={r.venue.id} result={r} rank={i + 1} />
          ))}
        </ol>
      )}

      {data && data.results.length === 0 && !failed && (
        <div className="empty">
          <p>Nothing in the corpus matches “{asked}” yet.</p>
          <p>Try a wider distance, or describe the dish rather than the place.</p>
        </div>
      )}

      {!data && !failed && (
        <div className="empty">
          <p>Say what you feel like eating.</p>
          <p>Every pick here comes with the post it came from, in the language it was written in.</p>
        </div>
      )}

      <footer className="foot">
        Recommendations are drawn from posts written by other people. We show them as written and link back to the
        original.
      </footer>
    </div>
  )
}

function ResultRow({ result, rank }: { result: Result; rank: number }) {
  const { venue, citations, why } = result
  const dist = distance(result.distance_m)
  const dishes = dishLine(venue.dishes)
  // The invariant, at the last possible moment: a result without evidence is not
  // a result. It should never arrive, and if it does it does not render.
  const cited = citations.filter((c) => c.post_url)
  if (!cited.length) return null
  const lead = cited.find((c) => c.excerpt) ?? cited[0]

  return (
    <li className="result">
      <div className="rank">{rank}</div>
      <div>
        <h2 className="venue" lang="und">
          {venue.name}
        </h2>
        <p className="meta">
          {venue.area && <span>{venue.area}</span>}
          {dist && <span>{dist}</span>}
          {dishes && <span>{dishes}</span>}
        </p>
        {why && <p className="why">{why}</p>}
        {lead?.excerpt && <blockquote className="excerpt">{lead.excerpt}</blockquote>}
        <div className="cite">
          {cited.slice(0, 3).map((c) => (
            <a key={c.post_url} className="chip" href={c.post_url} target="_blank" rel="noreferrer noopener">
              {sourceLabel(c.platform, c.author_handle)}
            </a>
          ))}
        </div>
        <p className="actions">
          <a href={venue.maps_url} target="_blank" rel="noreferrer noopener">
            Directions →
          </a>
        </p>
      </div>
    </li>
  )
}
