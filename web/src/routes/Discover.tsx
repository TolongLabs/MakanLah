import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { apiBase, type Chip, type Prefs, type RecommendResponse, recommend, suggestions } from '../api'
import { AskCompanion } from '../components/AskCompanion'
import { AskModal, type AskTarget } from '../components/AskModal'
import { ResultRow } from '../components/ResultRow'
import { coverageLine, evidenceOf, listBasisLine, sharedBasis } from '../evidence'
import { count, distance } from '../format'
import { loadPrefs, rangeLabel, summarise } from '../prefs'
import { RANGE } from '../taste/options'
import { cacheResults } from '../venueCache'

/** `applied_prefs` keys to the rows `summarise()` produces. #170: the page named
    all five answers while the API discarded three of them, so the three that can
    only be confirmed by the response are named only when it confirms them. */
const APPLIED_TERM: Record<string, string> = { company: 'With', mood: 'Mood', budget: 'Budget' }

/** The two the client owns. The API excludes them from `applied_prefs` on purpose:
    they ARE the query string and `radius_m`, so naming them there would count one
    filter twice. */
const CLIENT_TERMS = new Set(['Craving', 'Within'])

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
  // The radius the last search ACTUALLY used, which is not the same as the one
  // selected: run() drops it when geolocation never resolved. Telling somebody
  // "nothing within 3 km of you" when the search was KL-wide is the same class of
  // lie as blaming the corpus for a radius.
  const [askedRadius, setAskedRadius] = useState(0)
  const [chips, setChips] = useState<Chip[]>([])
  const [target, setTarget] = useState<AskTarget>(null)
  // The onboarding craving used to ride along on every later search forever, so the
  // page claimed two different things at once: "Filtered by your answers: nasi lemak
  // bumbung supper" above "5 picks for something not too heavy". Droppable now.
  //
  // #170. This comment used to end "the rest of the answers still filter", and that
  // was false. `prefs` is not a field on `RecommendRequest`, so Pydantic's default
  // extra='ignore' discards the whole object -- prefs as a bare string, a bare int
  // or null all return 200, where an out-of-range radius_m returns 422. Only Craving
  // (folded into the query string) and Within (sent as top-level radius_m) reach
  // ranking; With, Mood and Budget reach nothing. Which makes Drop The Craving a
  // no-op on results as well: it re-runs the same term at the same radius, and the
  // only input that differs is one the server never reads.
  const [useCraving, setUseCraving] = useState(true)

  const useCravingRef = useRef(useCraving)
  useCravingRef.current = useCraving

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
        setAskedRadius(useRadius ? radiusM : 0)
        const applied = prefs && !useCravingRef.current ? { ...prefs, craving: [] } : prefs
        const res = await recommend({
          query: term,
          limit: 10,
          ...(applied ? { prefs: applied } : {}),
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
  const gap = data?.evidence_gap ?? null
  const gaps = data?.coverage_gaps ?? []
  const outOfRange = data?.distance_gap ?? null
  // ONE caveat about the list, and only the caveat the cards cannot carry.
  //
  // Every card's subtitle now leads with its own basis, so "Every one of these is a
  // post naming that dish" restates ten cards in a banner. The semantic case is
  // different in kind: a whole page of near-misses is a fact about the QUERY rather
  // than about any row, and #140 makes it the common outcome -- every ingredient
  // word (`chicken`, `crab`, `noodle`) resolves to no canonical dish and routes
  // straight into the semantic lane. Ten cards each murmuring "Close in meaning" is
  // a much weaker warning than one line saying the corpus has no exact match.
  const common = sharedBasis(results)
  const commonLine = common === 'semantic' ? listBasisLine(common) : null
  const best = results[0]
  const summary = summarise(prefs)
  const hasCraving = (prefs.craving?.length ?? 0) > 0
  // Once the craving is dropped it stops being advertised as well as stops being
  // sent. Claiming a filter that is no longer applied is the same bug in reverse.
  // Named only where the response confirms it filtered. An older API sends no
  // `applied_prefs` and on that build the three did nothing, so absent and empty
  // land in the same place -- which is the honest one either way.
  const applied = new Set((data?.applied_prefs ?? []).map((k) => APPLIED_TERM[k]).filter(Boolean))
  const shown = summary
    .filter((r) => useCraving || r.term !== 'Craving')
    .filter((r) => CLIENT_TERMS.has(r.term) || applied.has(r.term))
    // #172. Geo rides router state and is never persisted, so a returning user has
    // prefs and no geo -- run() then drops the radius and searches KL-wide while
    // this line went on claiming "1 km" from `prefs`. The empty state was already
    // reading `askedRadius` and correctly saying "near you", so one screen carried
    // both sentences. `askedRadius` is the radius the search ACTUALLY used, and it
    // is the only one of the two either sentence is entitled to.
    //
    // Only once a search has been MADE. `asked` and `askedRadius` are both set
    // before the await, so they survive the catch and keep describing the request
    // that actually went out; `data` does not, and gating on it put "1 km" back
    // beside a failure state -- the same bug one branch over. Before any search
    // `askedRadius` is 0 and the wizard's answer is still the honest claim.
    .map((r) => (r.term === 'Within' && asked ? { ...r, value: rangeLabel(askedRadius) } : r))

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
          {/* ALWAYS present, not only once there are answers to change. The wizard
              is where the companion lives and its only route from here used to be
              an inline "Change" inside a conditional sentence -- the owner could
              not find it at all. Named for what it does rather than for editing a
              setting. */}
          <Link className="btn btn-quiet find-taste" to="/taste">
            {summary.length > 0 ? 'Redo My Taste' : 'Answer Four Questions'}
          </Link>
          {shown.length > 0 && (
            <p className="find-prefs">
              Filtered by your answers: {shown.map((r) => r.value).join(', ')}.{' '}
              {hasCraving && useCraving && (
                <button
                  type="button"
                  className="link link-button"
                  onClick={() => {
                    // The ref is written HERE and not left to the next render:
                    // run() reads it synchronously and React has not re-rendered
                    // yet, so setUseCraving alone updated the label while the
                    // request still carried the craving. The claim and the
                    // request have to agree.
                    useCravingRef.current = false
                    setUseCraving(false)
                    if (asked) void run(asked, radius)
                  }}
                >
                  Drop The Craving
                </button>
              )}{' '}
            </p>
          )}
        </div>
      </header>

      <div className="discover-body">
        <main className="discover-results">
          {/* At most one caveat, and only about what actually happened. Three stacked
              explanations -- two of them false -- read as an app apologising for
              itself, and the reader cannot tell which one is the real reason. */}
          {geoRefused && (
            <p className="notice-plain">
              We could not get your location, so this searches all of KL. Distances are hidden.
            </p>
          )}
          {data?.degraded && data.degraded_reasons?.length ? (
            <p className="notice">{`Showing what we have: ${data.degraded_reasons.join(', ')}.`}</p>
          ) : null}
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
              {/* COVERAGE, not relevance, and the distinction is the whole point.
                  A Malay halal query used to come back under "None of these match
                  your words exactly", which answers a question she did not ask
                  while staying silent on the one she did. This sits above the
                  basis line because it outranks it: not holding the information
                  at all is a larger fact than how the matching was done. */}
              {gaps.map((g) => (
                <p className="notice-coverage" key={g}>
                  {coverageLine(g)}
                </p>
              ))}
              {commonLine && <p className="basis list-basis">{commonLine}</p>}
              <ol className="results">
                {results.map((r, i) => (
                  <ResultRow key={r.venue.id} result={r} rank={r.rank ?? i + 1} gaps={gaps} onAsk={setTarget} />
                ))}
              </ol>
            </>
          )}

          {/* ONE explanation, and the true one.
              This said "nothing in the corpus matches X yet" for a query the corpus
              is full of -- the real cause was a 3km radius, and tapping Search All
              Of KL right after returned ten picks. It also told people to try the
              suggestions above when there were none on screen. Both were the page
              guessing at a reason instead of naming the one it knows. */}
          {/* The corpus knows the dish and cannot show you the writing (#98). This
              sits ABOVE the generic empty state and takes precedence over it,
              because it is the one case where the page knows the real reason and
              the generic copy would guess a different one -- which is the mistake
              #82 was filed for. Measured: `roti canai` returned Potato Corner. */}
          {!loading && gap && !failed && (
            <div className="empty empty-centred gap">
              <p className="gap-lede">
                {count(gap.total, 'place')} near you {gap.total === 1 ? 'serves' : 'serve'}{' '}
                <strong lang="und">{gap.term}</strong>, and we cannot show you what people wrote.
              </p>
              <p>
                The posts we had about {gap.total === 1 ? 'it' : 'them'} no longer open, so these are not picks. The
                restaurants are real and you can check them yourself.
              </p>
              <ul className="gap-venues">
                {gap.venues.map((v) => (
                  <li key={v.maps_url}>
                    <a className="link" href={v.maps_url} target="_blank" rel="noreferrer noopener">
                      <span lang="und">{v.name}</span>
                    </a>
                    {v.area && <span className="posted">{v.area}</span>}
                  </li>
                ))}
              </ul>
              {gap.total > gap.venues.length && (
                <p className="gap-more">{`Showing ${gap.venues.length} of ${gap.total}.`}</p>
              )}
            </div>
          )}

          {/* THE CORPUS HAS THE DISH AND NOTHING IN RANGE SERVES IT.
              Before this signal existed the API returned semantically-close venues
              with `coverage_gaps: []`, so a `nasi lemak` search at walking distance
              came back as pasta and tacos presented as Rank 1, 2, 3 -- some of them
              stamped "Corroborated by two independent sources", which was true about
              the posts and deeply misleading about the answer. The client had no way
              to know and correctly did not guess (#82).

              WHAT THIS MAY NOW SAY. `nearest` still mixes venues with readable
              posts and #101 venues whose every citation is dead, but `verifiable`
              tells them apart since `85b9220`, so each entry names its own class
              instead of the surface staying silent about all of them. The counts
              name a property rather than gesturing at the page, because nothing
              here RENDERS a post: there is no venue id to deep-link, so "9 posts
              still open" is the whole claim, and a venue nobody's surviving post
              describes says so outright.

              An older API sends neither field, and the note then disappears rather
              than defaulting -- see the type. Silence is the honest fallback here;
              `false` would be a claim. */}
          {!loading && outOfRange && !failed && (
            <div className="empty empty-centred gap">
              {/* The radius is named only when we actually hold one. `distance_gap`
                  can only arrive from a request that carried lat, lng and a radius,
                  so in practice `askedRadius` is set -- but a copy line that divides
                  by a number it has not checked prints "Nothing within 0.0 km of
                  you", which reads as a bug and is one. */}
              <p className="gap-lede">
                {askedRadius > 0 ? (
                  <>Nothing within {(askedRadius / 1000).toFixed(askedRadius < 1000 ? 1 : 0)} km of you serves </>
                ) : (
                  <>Nothing near you serves </>
                )}
                <strong lang="und">{outOfRange.term}</strong>.
              </p>
              <p>
                {outOfRange.nearest.length === 1
                  ? 'The nearest one that does:'
                  : `The nearest ${outOfRange.nearest.length} that do:`}
              </p>
              <ul className="gap-venues">
                {outOfRange.nearest.map((v) => (
                  <li key={v.maps_url}>
                    <a className="link" href={v.maps_url} target="_blank" rel="noreferrer noopener">
                      <span lang="und">{v.name}</span>
                    </a>
                    <span className="posted">
                      {distance(v.distance_m)}
                      {v.area ? ` · ${v.area}` : ''}
                    </span>
                    {typeof v.verifiable === 'boolean' && (
                      <span className="gap-evidence">
                        {v.verifiable && (v.live_citations ?? 0) > 0
                          ? `${count(v.live_citations ?? 0, 'post')} still open`
                          : 'No post still opens'}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setRadius(0)
                    void run(asked, 0)
                  }}
                >
                  Search All Of KL
                </button>
              </p>
            </div>
          )}

          {!loading && data && results.length === 0 && !failed && !gap && !outOfRange && (
            <div className="empty empty-centred">
              {askedRadius > 0 ? (
                <>
                  <p>
                    Nothing for “{asked}” within {(askedRadius / 1000).toFixed(askedRadius < 1000 ? 1 : 0)} km of you.
                  </p>
                  <p>There may be more further out.</p>
                  <p>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => {
                        setRadius(0)
                        void run(asked, 0)
                      }}
                    >
                      Search All Of KL
                    </button>
                  </p>
                </>
              ) : (
                <>
                  <p>Nobody has written about “{asked}” yet, anywhere in the corpus.</p>
                  <p>
                    {chips.length > 0
                      ? 'One of the suggestions above will have posts behind it.'
                      : 'Try describing the dish rather than the place.'}
                  </p>
                </>
              )}
            </div>
          )}
        </main>

        <aside className="discover-aside">
          <AskCompanion
            evidence={best ? evidenceOf(best) : null}
            degraded={data?.degraded ?? false}
            phase={best ? 'picks' : data || gap ? 'empty' : 'idle'}
            paused={target != null}
          />
        </aside>
      </div>

      {/* The ask moved out of the aside and in front of the page. On a phone that
          aside sits below every result, so tapping Ask scrolled nothing and opened
          nothing -- the form it targeted was several screens down and the control
          read as broken. */}
      {target && <AskModal target={target} onClose={() => setTarget(null)} />}
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
