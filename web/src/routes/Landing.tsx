import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { type Health, health } from '../api'
import { Testimony } from '../components/Testimony'
import { leadPair } from '../evidence'
import { dishLine } from '../format'
import { SPECIMEN } from './landingSpecimen'

/** The excerpt this page is built around. Chinese, Malay and English in one sentence,
    exactly as the writer typed it, because that is the thing an English-only pipeline
    silently loses. */
const MIXED = SPECIMEN.citations[0]

export function Landing() {
  return (
    <>
      <section className="page hero">
        <div className="hero-copy">
          <h1 className="display">Somebody Already Ate There</h1>
          <p className="lede">
            Every pick comes with the post it came from, in the language it was written in.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary" to="/taste">
              Find Food
            </Link>
          </div>
        </div>
        <Specimen />
      </section>

      <MixedLanguage />
      <Corpus />
      <Commitments />

      <section className="page last-call">
        <div>
          <h2 className="h-section">Start With A Craving</h2>
          <p className="body-soft section-lede">Four questions, no account needed.</p>
        </div>
        <Link className="btn btn-primary" to="/taste">
          Find Food
        </Link>
      </section>
    </>
  )
}

function Specimen() {
  const { venue, why } = SPECIMEN
  const pair = leadPair(SPECIMEN.citations)
  const dishes = dishLine(venue.dishes)

  return (
    <figure className="specimen">
      <figcaption className="specimen-caption">A pick, as it arrives.</figcaption>
      <div className="specimen-head">
        <p className="h-sub" lang="und">
          {venue.name}
        </p>
        <p className="meta-line">
          {venue.area && <span>{venue.area}</span>}
          {dishes && <span lang="und">{dishes}</span>}
        </p>
        <p className="why">{why}</p>
      </div>
      <div className="evidence evidence-pair">
        {pair.map((c) => (
          <Testimony key={c.post_url} citation={c} />
        ))}
      </div>
    </figure>
  )
}

function MixedLanguage() {
  return (
    <section className="page section">
      <h2 className="h-section">One Sentence, Three Languages</h2>
      <p className="body-soft section-lede">
        KL writes about food in Malay, Chinese and English at once, often inside a single line. A pipeline that reads
        only one of them still returns results, which is the problem: it looks like it is working while it quietly
        drops the best posts.
      </p>
      {MIXED && (
        <div className="feature-quote">
          <Testimony citation={MIXED} large />
        </div>
      )}
    </section>
  )
}

function Corpus() {
  const [data, setData] = useState<Health | null>(null)
  const [reachable, setReachable] = useState(true)

  useEffect(() => {
    let live = true
    health()
      .then((h) => live && setData(h))
      .catch(() => live && setReachable(false))
    return () => {
      live = false
    }
  }, [])

  return (
    <section className="page section">
      <h2 className="h-section">What Is Actually In There</h2>
      <p className="body-soft section-lede">
        Counted live, from the corpus this app reads. Nothing is fetched from a platform while you wait.
      </p>
      {!reachable && (
        <p className="notice section-notice">
          We could not reach the corpus just now, so these numbers are not shown rather than guessed.
        </p>
      )}
      {data && (
        <dl className="corpus">
          <div className="stat">
            <dd className="stat-figure">{data.corpus_size.toLocaleString('en-MY')}</dd>
            <dt className="stat-label">Posts, each one linkable</dt>
          </div>
          <div className="stat">
            <dd className="stat-figure">{(data.venues ?? 0).toLocaleString('en-MY')}</dd>
            <dt className="stat-label">Places somebody wrote about</dt>
          </div>
          <div className="stat">
            <dd className="stat-figure">2</dd>
            <dt className="stat-label">Platforms, so one going dark is survivable</dt>
          </div>
        </dl>
      )}
    </section>
  )
}

const COMMITMENTS: { claim: string; why: string }[] = [
  {
    claim: 'No pick without a post behind it.',
    why: 'An entry that cannot be cited is dropped before the list is built, not shown with a caveat attached. A rating with nothing behind it is a hallucination.'
  },
  {
    claim: 'Nobody gets translated.',
    why: 'Excerpts, venue names and dish names render in the script the writer used. We may add a gloss beside what somebody wrote. We never replace it.'
  },
  {
    claim: 'Nothing is scraped while you wait.',
    why: 'The app reads a corpus that was collected in the background. That is why it keeps working on the day a platform stops answering.'
  }
]

function Commitments() {
  return (
    <section className="page section">
      <h2 className="h-section">What It Will Not Do</h2>
      <ul className="commitments">
        {COMMITMENTS.map((c) => (
          <li key={c.claim}>
            <p className="commit-claim">{c.claim}</p>
            <p className="commit-why">{c.why}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
