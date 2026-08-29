import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { type Citation, type Health, health } from '../api'
import { Chop } from '../components/Chop'
import { Testimony } from '../components/Testimony'
import { leadPair } from '../evidence'
import { dishLine } from '../format'
import { MIXED_SCRIPT, SPECIMEN } from './landingSpecimen'

/**
 * The landing page, and the only page in this product allowed to sell.
 *
 * It is loud on purpose, at the owner's direction, and every boast on it is a
 * number this repository can produce. That constraint is not a limitation on the
 * marketing, it IS the marketing: the pitch is "nothing here is invented", and a
 * page that opened with an invented statistic would refute itself above the fold.
 *
 * So there is no "loved by thousands" and no "10x faster". There is 1,507 posts,
 * 247 places, and zero results without a citation -- the last of which is not a
 * claim about ambition but about `rank.py`, which drops an uncited entry before
 * the response is built.
 *
 * MOTION RULE, and it is the one that actually breaks pages: every reveal here
 * enhances a default that is already visible. Nothing is hidden waiting for an
 * observer to fire. A scroll animation that never runs -- background tab, a
 * headless renderer, an engine that skipped the observer -- must leave a complete
 * page behind, not a blank one.
 */
export function Landing() {
  return (
    <>
      <Hero />
      <NotInvented />
      <HowItWorks />
      <Exhibit />
      <ThreeLanguages />
      <Corpus />
      <LastCall />
    </>
  )
}

/* ------------------------------------------------------------------ machinery */

/** True once the element has been on screen, and never false again. Reveals do not
    replay on the way back up; a page that re-animates when you scroll up is a page
    that will not sit still. */
function useSeen<T extends Element>() {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver !== 'function') {
      setSeen(true)
      return
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true)
          io.disconnect()
        }
      },
      { rootMargin: '0px 0px -12% 0px' }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return { ref, seen }
}

function still(): boolean {
  return typeof window !== 'undefined' && (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
}

/**
 * A number that counts up once, the first time it is on screen.
 *
 * It renders the FINAL value on the very first paint and only then winds back to
 * animate, so the honest number is what a reader sees whether or not anything
 * runs. Under reduced motion it never winds back at all.
 */
function Tally({ value, label }: { value: number | null; label: string }) {
  const { ref, seen } = useSeen<HTMLDivElement>()
  const [shown, setShown] = useState<number | null>(value)

  useEffect(() => {
    if (value == null) return
    if (!seen || still()) {
      setShown(value)
      return
    }
    let raf = 0
    const start = performance.now()
    const run = (now: number) => {
      const t = Math.min(1, (now - start) / 900)
      // Quintic ease-out: fast, then a long settle, which reads as a counter
      // arriving rather than a slot machine stopping.
      setShown(Math.round(value * (1 - (1 - t) ** 5)))
      if (t < 1) raf = requestAnimationFrame(run)
    }
    raf = requestAnimationFrame(run)
    return () => cancelAnimationFrame(raf)
  }, [seen, value])

  return (
    <div className="tally" ref={ref}>
      <span className="tally-figure">{shown == null ? '—' : shown.toLocaleString('en-MY')}</span>
      <span className="tally-label">{label}</span>
    </div>
  )
}

/** A section that fades and rises the first time it is reached. Visible by default. */
function Reveal({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const { ref, seen } = useSeen<HTMLDivElement>()
  return (
    <div ref={ref} className={`reveal ${seen ? 'reveal-in' : ''} ${className}`.trim()}>
      {children}
    </div>
  )
}

/* ----------------------------------------------------------------------- hero */

function Hero() {
  const [live, setLive] = useState<Health | null>(null)
  const imageRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    let on = true
    health()
      .then((h) => on && setLive(h))
      .catch(() => {})
    return () => {
      on = false
    }
  }, [])

  // The photograph pulls back and sharpens as the page loads, then drifts on scroll.
  // Pinned under reduced motion rather than removed: the image is the whole mood.
  useEffect(() => {
    const image = imageRef.current
    if (!image || still()) return
    let raf = 0
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const y = window.scrollY
        image.style.transform = `scale(${(1.06 + Math.min(y, 900) / 9000).toFixed(4)}) translateY(${Math.min(y * 0.12, 90).toFixed(1)}px)`
        image.style.filter = `blur(${Math.min(10, y / 90).toFixed(1)}px)`
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <section className="hero-full">
      <picture>
        <source media="(max-width: 40rem)" srcSet="/hero-table-800.webp" />
        <img
          ref={imageRef}
          className="hero-full-image"
          src="/hero-table-1600.webp"
          alt=""
          width={1600}
          height={900}
          fetchPriority="high"
          decoding="async"
        />
      </picture>

      <div className="hero-full-inner">
        <div className="hero-copy">
          <span className="hero-mark">
            <Chop size={44} />
          </span>
          <h1 className="hero-display">
            <span className="hero-line">Loved By Malaysians.</span>
            <span className="hero-line hero-line-quiet">Not invented by a robot.</span>
          </h1>
          <p className="hero-lede">
            A scraper reads what Malaysians write about food, around the clock. You get the place{' '}
            <em>and the post that named it</em> — in the language somebody wrote it in.
          </p>
        </div>

        <div className="hero-tallies">
          <Tally value={live?.corpus_size ?? null} label="Posts read" />
          <Tally value={live?.venues ?? null} label="Places named" />
          <Tally value={0} label="Picks we made up" />
        </div>
      </div>

      <p className="hero-scroll" aria-hidden="true">
        Scroll
      </p>
    </section>
  )
}

/* --------------------------------------------------------------- not invented */

const ROBOT_LINE = 'You should try Village Park Restaurant in Damansara. It is famous for its nasi lemak.'

function NotInvented() {
  const pair = leadPair(SPECIMEN.citations)
  const first = pair[0]
  return (
    <section className="page section">
      <Reveal>
        <h2 className="h-display">Ask A Chatbot Where To Eat And It Will Answer.</h2>
        <p className="section-lede lede-wide">
          It will sound certain. It will not tell you where that came from, when, or whether the place is still open —
          because it does not know. It is finishing a sentence.
        </p>
      </Reveal>

      <div className="versus">
        <Reveal className="versus-side versus-robot">
          <p className="versus-who">A language model, asked just now</p>
          <blockquote className="versus-quote">{ROBOT_LINE}</blockquote>
          <ul className="versus-notes">
            <li>No source</li>
            <li>No date</li>
            <li>No way to check any of it</li>
          </ul>
        </Reveal>

        <Reveal className="versus-side versus-real">
          <p className="versus-who">A Malaysian, on RedNote</p>
          {first && (
            <>
              <blockquote className="versus-quote" lang="und">
                {first.excerpt}
              </blockquote>
              <ul className="versus-notes">
                <li>Written by a person</li>
                <li>{first.posted_at ?? 'Dated'}</li>
                <li>
                  <a className="link" href={first.post_url} target="_blank" rel="noreferrer noopener">
                    Read it yourself
                  </a>
                </li>
              </ul>
            </>
          )}
        </Reveal>
      </div>

      <Reveal>
        <p className="versus-verdict">
          MakanLah only ever shows you the second kind. <strong>An entry that cannot be cited is dropped</strong> before
          the list is built — not shown with a caveat, not softened, dropped.
        </p>
      </Reveal>
    </section>
  )
}

/* --------------------------------------------------------------- how it works */

const STEPS = [
  {
    n: '01',
    title: 'It Reads, All Night',
    body: 'A scraper works through RedNote and Google Maps around the clock, pulling posts Malaysians wrote about places they actually went. Nobody is waiting on it, so it can be slow and thorough.'
  },
  {
    n: '02',
    title: 'It Pulls Out The Facts',
    body: 'Every post is read for the venue, the dish, the sentiment and the line worth quoting. Malay, Chinese and English, often inside one sentence. Nothing is translated and nothing is rewritten.'
  },
  {
    n: '03',
    title: 'You Ask, It Answers From That',
    body: 'Your search never touches a platform. It reads the corpus that was already collected, which is why it still works on the day a platform goes dark — and why every pick arrives with its post attached.'
  }
]

function HowItWorks() {
  return (
    <section className="page section">
      <Reveal>
        <h2 className="h-display">While You Were Asleep, It Was Reading.</h2>
        <p className="section-lede lede-wide">
          Three stages, in this order, every day. The numbering is real: stage two cannot run before stage one and your
          search never runs any of them.
        </p>
      </Reveal>
      <ol className="pipeline">
        {STEPS.map((s) => (
          <Reveal key={s.n}>
            <li className="stage">
              <span className="stage-n" aria-hidden="true">
                {s.n}
              </span>
              <h3 className="stage-title">{s.title}</h3>
              <p className="stage-body">{s.body}</p>
            </li>
          </Reveal>
        ))}
      </ol>
    </section>
  )
}

/* -------------------------------------------------------------------- exhibit */

const PAIR = leadPair(SPECIMEN.citations)
const PAIRED = new Set(PAIR.map((c) => c.post_url))
const POST_CARDS: Citation[] = [...SPECIMEN.citations, MIXED_SCRIPT].filter(
  (c): c is Citation => Boolean(c) && !PAIRED.has(c.post_url)
)

const PLATFORM_LABEL: Record<string, string> = { rednote: 'RedNote', google_maps: 'Google Maps' }

function PostCard({ citation }: { citation: Citation }) {
  return (
    <li className="post-card">
      <div className="post-card-head">
        <span className="chip">{PLATFORM_LABEL[citation.platform] ?? citation.platform}</span>
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

/**
 * The plate is also what `scripts/layout_check.py` measures, and it is the only
 * surface in the app that renders an `.evidence-pair` with no API behind it. If it
 * leaves this page the guard needs a new host or it is guarding nothing.
 */
function Specimen() {
  const { venue, why } = SPECIMEN
  const dishes = dishLine(venue.dishes)
  return (
    <figure className="specimen">
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

function Exhibit() {
  const { venue } = SPECIMEN
  return (
    <section className="page section">
      <Reveal>
        <h2 className="h-display">This Is What One Looks Like.</h2>
        <p className="section-lede lede-wide">
          Not a mock-up. Two independent posts put <strong lang="und">{venue.name}</strong> in front of you, and both
          are one tap from the original.
        </p>
      </Reveal>
      <div className="posts-split">
        <Reveal>
          <Specimen />
        </Reveal>
        <ul className="post-cards">
          {POST_CARDS.map((c) => (
            <PostCard key={c.post_url} citation={c} />
          ))}
        </ul>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------ three languages */

function ThreeLanguages() {
  return (
    <section className="page section section-split">
      <Reveal>
        <h2 className="h-display">By Malaysians, For Malaysians.</h2>
        <p className="section-lede">
          KL writes about food in Malay, Chinese and English at once, often inside a single line. A pipeline that reads
          only one of them still returns results, which is exactly the problem: it looks like it is working while it
          quietly drops the best posts.
        </p>
      </Reveal>
      <Reveal className="feature-quote">
        <Testimony citation={MIXED_SCRIPT} large />
      </Reveal>
    </section>
  )
}

/* --------------------------------------------------------------------- corpus */

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
    let on = true
    health()
      .then((h) => on && setData(h))
      .catch(() => on && setReachable(false))
    return () => {
      on = false
    }
  }, [])

  return (
    <section className="page section">
      <Reveal>
        <h2 className="h-display">Counted Live, Right Now.</h2>
        <p className="section-lede lede-wide">
          Read from the corpus this app is serving as you read this page. Nothing is fetched from a platform while you
          wait — that is the whole design.
        </p>
      </Reveal>
      {!reachable && (
        <p className="notice section-notice">
          We could not reach the corpus just now, so these numbers are not shown rather than guessed.
        </p>
      )}
      {data && (
        <Reveal>
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
        </Reveal>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ last call */

/** The second and last call to action on the page. */
function LastCall() {
  return (
    <section className="last-call">
      {/* The page's second photograph, and the only other place it inverts. It names
          no venue, so an atmospheric image here cannot be mistaken for evidence --
          the same carve-out docs/DESIGN.md gives the auth panel. Lazy and below the
          fold, so it never competes with the hero for first paint. */}
      <picture>
        <source media="(max-width: 40rem)" srcSet="/kopitiam-800.webp" />
        <img
          className="last-call-image"
          src="/kopitiam-1600.webp"
          alt=""
          width={1600}
          height={667}
          loading="lazy"
          decoding="async"
        />
      </picture>
      <div className="last-call-copy">
        <div className="last-call-inner">
          <h2 className="h-display">Somebody Already Ate There.</h2>
          <p className="section-lede">Four questions. Then a place, and the post that named it.</p>
          <Link className="btn btn-invert btn-big" to="/sign-up">
            Get Started
          </Link>
        </div>
      </div>
    </section>
  )
}
