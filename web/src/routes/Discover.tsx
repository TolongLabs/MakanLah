import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { apiBase, type Prefs, type RecommendResponse, recommend } from '../api'
import { Mascot } from '../components/Mascot'
import { ResultRow } from '../components/ResultRow'
import { evidenceOf, moodFor } from '../evidence'
import { count } from '../format'
import { loadPrefs, queryFrom, summarise } from '../prefs'
import { RANGE } from '../taste/options'
import { cacheResults } from '../venueCache'

type Geo = { lat: number; lng: number } | null
type Handoff = { prefs?: Prefs; geo?: Geo; geoRefused?: boolean }

export function Discover() {
  const navigate = useNavigate()
  const location = useLocation()
  const handoff = (location.state ?? {}) as Handoff

  const [prefs] = useState<Prefs | null>(() => handoff.prefs ?? loadPrefs())
  const [query, setQuery] = useState(() => (prefs ? queryFrom(prefs) : ''))
  const [radius, setRadius] = useState(() => prefs?.range_m ?? 0)
  const [geo] = useState<Geo>(handoff.geo ?? null)
  const [geoRefused] = useState(Boolean(handoff.geoRefused))

  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<RecommendResponse | null>(null)
  const [failed, setFailed] = useState(false)
  const [asked, setAsked] = useState('')

  const run = useCallback(
    async (q: string, radiusM: number) => {
      const term = q.trim()
      if (!term) return
      setLoading(true)
      setFailed(false)
      setAsked(term)
      try {
        const useRadius = radiusM > 0 && geo
        const res = await recommend({
          query: term,
          limit: 10,
          ...(prefs ? { prefs } : {}),
          ...(useRadius ? { lat: geo.lat, lng: geo.lng, radius_m: radiusM } : {})
        })
        setData(res)
        cacheResults(res.results)
      } catch {
        setData(null)
        setFailed(true)
      } finally {
        setLoading(false)
      }
    },
    [geo, prefs]
  )

  // The wizard is the front door: arriving here having never answered it means the
  // user deep-linked or cleared storage, so send them through it rather than showing
  // an empty page with a search box and no explanation.
  const first = useRef(true)
  useEffect(() => {
    if (!first.current) return
    first.current = false
    if (!prefs) {
      navigate('/taste', { replace: true })
      return
    }
    void run(queryFrom(prefs), prefs.range_m ?? 0)
  }, [navigate, prefs, run])

  if (!prefs) return null

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void run(query, radius)
  }

  const results = data?.results ?? []
  const best = results[0]
  const mood = moodFor(best ? evidenceOf(best) : null, data?.degraded ?? false)

  return (
    <div className="page discover-grid">
      <aside className="discover-rail">
        <div className="rail-block">
          <h2 className="rail-heading">Search</h2>
          <form className="search" onSubmit={onSubmit}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="What you feel like eating"
              placeholder="what do you feel like eating?"
              enterKeyHint="search"
            />
            <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
              {loading ? 'Finding…' : 'Go'}
            </button>
          </form>
        </div>

        <div className="rail-block">
          <h2 className="rail-heading">Distance</h2>
          <div className="options options-tight">
            {RANGE.map((r) => (
              <button
                key={r.value}
                type="button"
                className="option"
                aria-pressed={radius === r.value}
                onClick={() => {
                  setRadius(r.value)
                  void run(query, r.value)
                }}
              >
                <span className="option-label">{r.label}</span>
              </button>
            ))}
          </div>
          {radius > 0 && !geo && (
            <p className="notice-plain section-lede">
              Without a location this searches all of KL. Distances stay hidden.
            </p>
          )}
        </div>

        <div className="rail-block">
          <h2 className="rail-heading">Your Taste</h2>
          <dl className="taste-summary">
            {summarise(prefs).map((row) => (
              <div key={row.term}>
                <dt>{row.term}</dt>
                <dd lang="und">{row.value}</dd>
              </div>
            ))}
          </dl>
          <p className="section-lede">
            <Link className="link" to="/taste">
              Adjust
            </Link>
          </p>
        </div>

        <div className="rail-block">
          <Mascot mood={mood} />
        </div>
      </aside>

      <div>
        <div className="stack-gap">
          {geoRefused && (
            <p className="notice-plain">
              We could not get your location, so this searches all of KL. Distances are hidden.
            </p>
          )}
          {data?.degraded && (
            <p className="notice">
              {data.degraded_reasons?.length
                ? `Showing what we have: ${data.degraded_reasons.join(', ')}.`
                : 'A source was unreachable at the last refresh, so this may be incomplete.'}
            </p>
          )}
          {failed && (
            <p className="notice">
              We could not reach the corpus at <code>{apiBase()}</code>. It is not hosted yet, so it needs to be running
              somewhere this page can reach. Point it at one by adding <code>?api=https://your-api</code> to the URL.
            </p>
          )}
        </div>

        {loading && <Skeletons />}

        {!loading && results.length > 0 && (
          <>
            <p className="result-count">{count(results.length, 'pick')}</p>
            <ol className="results">
              {results.map((r, i) => (
                <ResultRow key={r.venue.id} result={r} rank={i + 1} />
              ))}
            </ol>
          </>
        )}

        {!loading && data && results.length === 0 && !failed && (
          <div className="empty empty-centred">
            <p>Nothing in the corpus matches “{asked}” yet.</p>
            <p>Try a wider distance, or describe the dish rather than the place.</p>
            {radius > 0 && (
              <p>
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => {
                    setRadius(0)
                    void run(query, 0)
                  }}
                >
                  Search All Of KL
                </button>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/** Shaped like the rows it stands in for, so the page does not jump when they land. */
function Skeletons() {
  return (
    <div className="results" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div className="skeleton" key={i}>
          <div />
          <div>
            <div className="skeleton-bar" />
            <div className="skeleton-bar" />
            <div className="skeleton-bar" />
            <div className="skeleton-bar" />
          </div>
        </div>
      ))}
    </div>
  )
}
