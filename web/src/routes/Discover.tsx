import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { apiBase, type Chip, type Prefs, type RecommendResponse, recommend, suggestions } from '../api'
import { AskCompanion, type AskTarget } from '../components/AskCompanion'
import { ResultRow } from '../components/ResultRow'
import { evidenceOf, listBasisLine, sharedBasis } from '../evidence'
import { count } from '../format'
import { loadPrefs, summarise } from '../prefs'
import { RANGE } from '../taste/options'
import { cacheResults } from '../venueCache'

type Geo = { lat: number; lng: number } | null
type Handoff = { prefs?: Prefs; geo?: Geo; geoRefused?: boolean }

/**
 * The results page, rebuilt around the one thing somebody is here to do.
 *
 * The old version buried a 200px search box in a left rail beside three other rail
 * blocks, and prefilled it with a sentence assembled from the wizard answers. Both
 * were wrong in the same way: they treated searching as one of several equal
 * controls, when it is the entire page.
 *
 * WHAT CHANGED, AND WHY EACH ONE:
 *
 * 1. Search is a header, full width, first thing, and **empty**. A prefilled field
 *    has to be cleared before it can be used, and it made the wizard's answers look
 *    like a query the user typed rather than a filter already applied.
 * 2. The wizard's answers are still applied -- they go to the API as `prefs` -- and
 *    are shown as a plain line saying so, which is what they always were.
 * 3. Chips replace the prefill. Every one is a dish the corpus has posts about, so
 *    a chip cannot lead to an empty page. See `makanlah/suggest.py`.
 * 4. Distance is a segmented control on one row, not a rail block of radio cards.
 * 5. The companion has a job: she reports how strong the evidence is, and Ask on any
 *    pick hands her that venue so you can interrogate its posts.
 *
 * The first search still runs automatically from the wizard's answers, because
 * arriving from four questions to an empty page would waste them.
 */
export function Discover() {
  const navigate = useNavigate()
  const location = useLocation()
  const handoff = (location.state ?? {}) as Handoff

  const [prefs] = useState<Prefs | null>(() => handoff.prefs ?? loadPrefs())
  // Deliberately empty. See note 1 above.
  const [query, setQuery] = useState('')
  const [radius, setRadius] = useState(() => prefs?.range_m ?? 0)
  const [geo] = useState<Geo>(handoff.geo ?? null)
  const [geoRefused] = useState(Boolean(handoff.geoRefused))

  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<RecommendResponse | null>(null)
  const [failed, setFailed] = useState(false)
  const [asked, setAsked] = useState('')
  const [chips, setChips] = useState<Chip[]>([])
  const [target, setTarget] = useState<AskTarget>(null)

  const run = useCallback(
    async (q: string, radiusM: number) => {
      const term = q.trim()
      if (!term) return
      setLoading(true)
      setFailed(false)
      setAsked(term)
      setTarget(null)
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
    void run(cravingOf(prefs), prefs.range_m ?? 0)
  }, [navigate, prefs, run])

  useEffect(() => {
    let on = true
    suggestions()
      .then((s) => on && setChips(s.chips))
      .catch(() => {
        // No chips rather than invented ones. Six dead ends is worse than none.
      })
    return () => {
      on = false
    }
  }, [])

  if (!prefs) return null

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void run(query, radius)
  }

  function pick(chip: Chip) {
    setQuery(chip.query)
    void run(chip.query, radius)
  }

  const results = data?.results ?? []
  // One caveat about the list beats the same sentence on every row.
  const common = sharedBasis(results)
  const commonLine = listBasisLine(common)
  const best = results[0]
  const summary = summarise(prefs)

  return (
    <div className="page discover">
      <header className="find">
        <form className="find-form" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="find">
            What are you hungry for?
          </label>
          <input
            id="find"
            className="find-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What are you hungry for?"
            autoComplete="off"
            enterKeyHint="search"
          />
          <button type="submit" className="btn btn-primary find-go" disabled={loading || !query.trim()}>
            {loading ? 'Reading…' : 'Find'}
          </button>
        </form>

        {chips.length > 0 && (
          <fieldset className="chips">
            <legend className="sr-only">Suggestions</legend>
            {chips.map((c) => (
              <button type="button" key={c.label} className="chip-button" onClick={() => pick(c)} disabled={loading}>
                <span lang="und">{c.label}</span>
                {/* The count is the honesty: this is offered because people wrote
                    about it, and the number says how many. */}
                <span className="chip-count">{c.posts}</span>
              </button>
            ))}
          </fieldset>
        )}

        <div className="find-filters">
          <fieldset className="segmented">
            <legend className="sr-only">How far</legend>
            {RANGE.map((r) => (
              <button
                type="button"
                key={r.value}
                className="segment"
                aria-pressed={radius === r.value}
                onClick={() => {
                  setRadius(r.value)
                  if (asked) void run(asked, r.value)
                }}
              >
                {r.label}
              </button>
            ))}
          </fieldset>
          {summary.length > 0 && (
            <p className="find-prefs">
              Filtered by your answers: {summary.map((s) => s.value).join(', ')}.{' '}
              <Link className="link" to="/taste">
                Change
              </Link>
            </p>
          )}
        </div>
      </header>

      <div className="discover-body">
        <main className="discover-results">
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
              We could not reach the corpus at <code>{apiBase()}</code>. Point this page at a running one by adding{' '}
              <code>?api=https://your-api</code> to the URL.
            </p>
          )}

          {loading && (
            <>
              {/* The re-rank is a model call and p95 is about five seconds, so the
                  wait is named rather than left to look like a hang. */}
              <p className="result-count" role="status">
                Reading the posts. This takes a few seconds.
              </p>
              <Skeletons />
            </>
          )}

          {!loading && results.length > 0 && (
            <>
              <p className="result-count">
                {count(results.length, 'pick')} for <strong lang="und">{asked}</strong>
              </p>
              {commonLine && <p className="basis list-basis">{commonLine}</p>}
              <ol className="results">
                {results.map((r, i) => (
                  <ResultRow key={r.venue.id} result={r} rank={r.rank ?? i + 1} showBasis={!common} onAsk={setTarget} />
                ))}
              </ol>
            </>
          )}

          {!loading && data && results.length === 0 && !failed && (
            <div className="empty empty-centred">
              <p>Nothing in the corpus matches “{asked}” yet.</p>
              <p>Try one of the suggestions above, or describe the dish rather than the place.</p>
              {radius > 0 && (
                <p>
                  <button
                    type="button"
                    className="btn btn-quiet"
                    onClick={() => {
                      setRadius(0)
                      void run(asked, 0)
                    }}
                  >
                    Search All Of KL
                  </button>
                </p>
              )}
            </div>
          )}
        </main>

        <aside className="discover-aside">
          <AskCompanion
            evidence={best ? evidenceOf(best) : null}
            degraded={data?.degraded ?? false}
            target={target}
            onClear={() => setTarget(null)}
          />
        </aside>
      </div>
    </div>
  )
}

/** The wizard's craving words, used only for the first automatic search. The rest of
    the answers travel as `prefs` and filter server-side rather than being flattened
    into a sentence the user then has to delete. */
function cravingOf(prefs: Prefs): string {
  const craving = prefs.craving ?? []
  return craving.length > 0 ? craving.join(' ') : 'makan'
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
