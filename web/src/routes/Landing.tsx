import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { type Citation, type Health, health } from '../api'
import { Chop } from '../components/Chop'
import { Testimony } from '../components/Testimony'
import { leadPair } from '../evidence'
import { dishLine } from '../format'
import { MIXED_SCRIPT, SPECIMEN } from './landingSpecimen'

/**
 * The landing page, restructured on the pattern in the owner's SolarSim app: a
 * full-height hero over a photograph that blurs as you leave it, then sectioned
 * content beneath.
 *
 * TWO CALLS TO ACTION ON THE WHOLE PAGE, both reading "Get Started" and both going to
 * sign-up: one in the top bar, one at the foot. The page previously had three, in two
 * different wordings, pointing at a different destination. A landing page that asks
 * three times is a landing page that is not confident the first ask worked.
 *
 * The hero deliberately carries no button. The bar is pinned above it and the closing
 * band is one scroll away, so a third ask between them would only be noise.
 */
export function Landing() {
  return (
    <>
      <Hero />
      <FromRealPosts />
      <Corpus />
      <Commitments />
      <LastCall />
    </>
  )
}

/** Scroll distance, published on animation frames rather than on every scroll event. */
function useScrollY(): number {
  const [y, setY] = useState(0)
  useEffect(() => {
    let ticking = false
    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        setY(window.scrollY)
        ticking = false
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return y
}

/**
 * Full-height, over a photograph, with the copy on a glass panel.
 *
 * The image blurs progressively as it scrolls away, which is SolarSim's move and the
 * reason the text stays readable over a busy photo without a heavy scrim. It is a
 * filter on a decorative image rather than movement, but it is still driven by scroll,
 * so prefers-reduced-motion pins it at a constant blur instead.
 */
function Hero() {
  const y = useScrollY()
  const imageRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    const image = imageRef.current
    if (!image) return
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    image.style.filter = still ? 'blur(6px)' : `blur(${Math.min(14, y / 40).toFixed(1)}px)`
  }, [y])

  return (
    <section className="hero-full">
      <picture>
        <source media="(max-width: 40rem)" srcSet="/kopitiam-800.webp" />
        <img
          ref={imageRef}
          className="hero-full-image"
          src="/kopitiam-1600.webp"
          alt=""
          width={1600}
          height={667}
          fetchPriority="high"
          decoding="async"
        />
      </picture>
      <div className="hero-full-inner">
        <div className="hero-glass rise-in">
          <span className="hero-mark">
            <Chop size={40} />
          </span>
          <h1 className="display">Somebody Already Ate There</h1>
          <p className="lede">
            Every pick comes with the post it came from, in the language it was written in. No blurbs, no invented
            ratings.
          </p>
        </div>
      </div>
    </section>
  )
}

/**
 * The exhibit, and then the rest of the evidence.
 *
 * The plate carries the corroboration: one venue with two posts from two platforms
 * side by side, which is the claim the product is actually making and the only way
 * to make it visibly. The cards carry the posts that are not part of that pair, so
 * nothing appears twice.
 *
 * THE PLATE IS ALSO WHAT `scripts/layout_check.py` MEASURES, and it is the only
 * surface in the app that renders an `.evidence-pair` without an API behind it.
 * Rebuilding this page around cards alone removed it, and the guard reported five
 * "nothing was measured" failures rather than passing quietly -- which is the only
 * reason this is written down here. If the plate leaves this page again, the guard
 * needs a new host or it is guarding nothing.
 */
const PAIR = leadPair(SPECIMEN.citations)
const PAIRED = new Set(PAIR.map((c) => c.post_url))
const POST_CARDS: Citation[] = [...SPECIMEN.citations, MIXED_SCRIPT].filter(
  (c): c is Citation => Boolean(c) && !PAIRED.has(c.post_url)
)

const PLATFORM_LABEL: Record<string, string> = { rednote: 'RedNote', google_maps: 'Google Maps' }

function PostCard({ citation }: { citation: Citation }) {
  const label = PLATFORM_LABEL[citation.platform] ?? citation.platform
  return (
    <li className="post-card">
      <div className="post-card-head">
        <span className="chip">{label}</span>
        {citation.posted_at && <span className="post-card-date">{citation.posted_at}</span>}
      </div>
      <blockquote className="post-card-quote" lang="und">
        {citation.excerpt}
      </blockquote>
      <a className="post-card-link" href={citation.post_url} target="_blank" rel="noreferrer noopener">
        Read The Post
      </a>
    </li>
  )
}

function Specimen() {
  const { venue, why } = SPECIMEN
  const dishes = dishLine(venue.dishes)
  return (
    <figure className="specimen rise-in specimen-enter">
      <span className="stamp" title="Two independent sources">
        <Chop size={58} />
        <span className="sr-only">Corroborated by two independent sources.</span>
      </span>
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
        {PAIR.map((c) => (
          <Testimony key={c.post_url} citation={c} />
        ))}
      </div>
    </figure>
  )
}

function FromRealPosts() {
  const { venue } = SPECIMEN
  return (
    <section className="page section">
      <h2 className="h-section">Straight From The Posts</h2>
      <p className="body-soft section-lede">
        Real captures, shown as written. Two independent posts put <strong lang="und">{venue.name}</strong> in front of
        you; the rest are other places entirely. Two platforms, three languages, nobody translated.
      </p>
      <div className="posts-split">
        <Specimen />
        <ul className="post-cards">
          {POST_CARDS.map((c) => (
            <PostCard key={c.post_url} citation={c} />
          ))}
        </ul>
      </div>
    </section>
  )
}

/** Freshness in the coarsest honest unit. "3 days" is useful; "3.04 days" is noise,
    and a precise figure implies a precision the capture schedule does not have. */
function sinceCapture(iso: string | null): string {
  if (!iso) return 'Unknown'
  const days = Math.floor((Date.now() - Date.parse(iso)) / 86_400_000)
  if (Number.isNaN(days)) return 'Unknown'
  if (days < 1) return 'Today'
  return days === 1 ? '1 day' : `${days} days`
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
            <dd className="stat-figure">{sinceCapture(data.newest_capture)}</dd>
            <dt className="stat-label">Since the newest post was captured</dt>
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

/** The second and last call to action on the page. */
function LastCall() {
  return (
    <section className="last-call">
      <div className="last-call-copy">
        <div className="last-call-inner">
          <h2 className="h-section">Start With A Craving</h2>
          <p className="section-lede">Four questions, and somebody has already eaten there.</p>
          <Link className="btn btn-invert" to="/sign-up">
            Get Started
          </Link>
        </div>
      </div>
    </section>
  )
}
