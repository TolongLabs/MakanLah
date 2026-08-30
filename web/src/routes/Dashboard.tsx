import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { type Health, health, type Result } from '../api'
import { loadSession } from '../auth'
import { count } from '../format'
import { loadPrefs, summarise } from '../prefs'
import { lastResults } from '../venueCache'

/**
 * Where you land after signing in.
 *
 * Structured after the owner's own Kawan `Home.tsx`: a page header, then a hero
 * card, then CTA cards below it, then a tall rail down the right. What differs is
 * only what MakanLah actually has to put in those slots.
 *
 * TWO CTA CARDS, NOT THREE. `/discover` and `/taste` are the only other main
 * pages this app has. A third card would be a slot filled to balance a grid,
 * which `docs/DESIGN.md` names as a tell in as many words.
 *
 * THE HERO IS NOT A THIRD CTA. It carries the corpus figures, because the one
 * thing this product can say on arrival that nothing else can is how much real
 * writing stands behind it. Every number in it comes from `/health`; none is
 * computed here and none is a placeholder.
 */
export function Dashboard() {
  const session = loadSession()
  const [corpus, setCorpus] = useState<Health | null>(null)
  const [recent] = useState<Result[]>(() => lastResults())
  const prefs = loadPrefs()
  const answers = prefs ? summarise(prefs) : []

  useEffect(() => {
    let on = true
    health()
      .then((h) => on && setCorpus(h))
      .catch(() => {
        // The hero prints nothing rather than a zero. A corpus of "0 posts" is a
        // measurement, and an unreachable API has not made one.
      })
    return () => {
      on = false
    }
  }, [])

  return (
    <div className="page dash">
      <header className="dash-head">
        <h1 className="dash-title">{session?.user.email ? 'Good to have you back.' : 'Good to have you here.'}</h1>
        <p className="dash-sub">Everything below comes from something a person actually wrote.</p>
      </header>

      <div className="dash-bento">
        <div className="dash-col">
          <section className="dash-hero">
            <p className="dash-hero-lede">
              MakanLah does not guess. It reads what Malaysians posted, and every pick it gives you carries the post it
              came from.
            </p>
            {corpus ? (
              <dl className="dash-figures">
                <div>
                  <dt>Posts Read</dt>
                  <dd>{corpus.corpus_size.toLocaleString('en-MY')}</dd>
                </div>
                {corpus.venues != null && (
                  <div>
                    {/* KL, said plainly. The corpus is 256 Kuala Lumpur venues and
                        nothing outside it, and this figure sits directly under a
                        line about what Malaysians wrote -- unlabelled, the pair
                        reads as national coverage the corpus does not have. */}
                    <dt>Places In KL</dt>
                    <dd>{corpus.venues.toLocaleString('en-MY')}</dd>
                  </div>
                )}
                {corpus.newest_capture && (
                  <div>
                    <dt>Last Read</dt>
                    <dd>
                      <time dateTime={corpus.newest_capture}>{corpus.newest_capture.slice(0, 10)}</time>
                    </dd>
                  </div>
                )}
              </dl>
            ) : (
              /* Not a skeleton pretending to be numbers. Until /health answers there
                 is nothing true to show, and a shimmering placeholder in the shape of
                 a figure is a claim that one is coming. */
              <p className="dash-figures-pending">Counting what the corpus holds…</p>
            )}
          </section>

          <div className="dash-ctas">
            <Link className="dash-card" to="/discover">
              <span className="dash-card-label">Find Somewhere To Eat</span>
              <span className="dash-card-sub">Search the corpus. Every result cites the post behind it.</span>
            </Link>

            <Link className="dash-card" to="/taste">
              <span className="dash-card-label">Your Taste</span>
              {/* The wizard is where she lives, and it was unreachable from inside the
                  app -- this is one of the two doors back to it. */}
              <span className="dash-card-sub">
                {answers.length > 0
                  ? `Answered: ${answers.map((a) => a.value).join(', ')}.`
                  : 'Four questions. It is how the ranking learns what you want.'}
              </span>
            </Link>
          </div>
        </div>

        <aside className="dash-rail">
          <h2 className="dash-rail-heading">Where You Just Looked</h2>
          {recent.length > 0 ? (
            <ul className="dash-recent">
              {recent.slice(0, 6).map((r) => (
                <li key={r.venue.id}>
                  <Link className="dash-recent-item" to={`/r/${r.venue.id}`}>
                    <span className="dash-recent-name" lang="und">
                      {r.venue.name}
                    </span>
                    <span className="dash-recent-meta">
                      {count(r.citations.length, 'post')}
                      {r.venue.area ? ` · ${r.venue.area}` : ''}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            /* `venueCache` is sessionStorage, so this is empty on the first visit
               after signing in -- which is the commonest visit this page gets. An
               honest empty state beats inventing a history. */
            <p className="dash-recent-empty">Nothing yet. What you look at will collect here for this visit.</p>
          )}
        </aside>
      </div>
    </div>
  )
}
