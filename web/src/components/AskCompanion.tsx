import { type FormEvent, lazy, Suspense, useEffect, useRef, useState } from 'react'
import { type AskResponse, ask, type Citation } from '../api'
import { rememberVoice, speaker, synth, voiceEnabled } from '../companion/voice'
import { type Evidence, type MascotMood, moodFor, readingFor } from '../evidence'
import type { Live2DStage } from '../live2d/Live2DStage'

const MascotStage = lazy(() => import('../live2d/MascotStage'))

/* Must match the tablet rule in results.css. Changing one and not the other is how
   the stage got CSS room on a tablet while React still refused to mount it. */
const STAGE_AT = '(min-width: 48rem)'

export type AskTarget = { id: string; name: string } | null

/**
 * The companion on the results page, where she has two jobs rather than a presence.
 *
 * **She reports how strong the evidence is**, unprompted, whenever a search lands.
 * That is real information the list itself cannot carry: "two independent sources
 * agree on the top one" is the difference between a recommendation and a mention,
 * and it is the product's whole claim said out loud.
 *
 * **And she is how you interrogate a pick.** Tapping Ask on a result puts that
 * venue in her hands; the question goes to `/ask`, which answers from that venue's
 * citations or says the posts do not cover it. That second outcome is the feature.
 * A chatbot cannot say "nobody wrote about that" because it has no evidence trail
 * to be honest about, and she says it constantly.
 *
 * SHE NEVER ANSWERS FROM HER OWN KNOWLEDGE. Every word in an answer comes back from
 * the API with citations attached, and a `covered: false` reply renders as a refusal
 * with no citations rather than as a hedge. The line she says while idle is written
 * locally from `readingFor`, not generated.
 */
export function AskCompanion({
  evidence,
  degraded,
  target,
  onClear
}: {
  evidence: Evidence | null
  degraded: boolean
  target: AskTarget
  onClear: () => void
}) {
  const mood: MascotMood = moodFor(evidence, degraded)
  const reading = readingFor(mood)

  const [wide, setWide] = useState(() => window.matchMedia?.(STAGE_AT).matches ?? false)
  const [live, setLive] = useState(false)
  const [failed, setFailed] = useState(false)
  const [voice, setVoice] = useState(voiceEnabled)
  const [talking, setTalking] = useState(false)

  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [errored, setErrored] = useState(false)

  const stage = useRef<Live2DStage | null>(null)
  const say = useRef<ReturnType<typeof speaker> | null>(null)
  const field = useRef<HTMLInputElement>(null)

  useEffect(() => {
    say.current = speaker()
    return () => say.current?.stop()
  }, [])

  // The stage is not mounted below the breakpoint, rather than hidden. A phone was
  // downloading 500 KB of pixi and allocating a WebGL context for a 1x1 canvas.
  useEffect(() => {
    const mq = window.matchMedia?.(STAGE_AT)
    if (!mq) return
    const on = () => setWide(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])

  // A new target clears the last answer and takes focus, so Ask on a second venue
  // never shows the first venue's answer under the second venue's name.
  useEffect(() => {
    setAnswer(null)
    setErrored(false)
    setQuestion('')
    if (target) field.current?.focus()
  }, [target])

  const spoken = answer ? answer.answer : `${reading.read}. ${reading.note}`

  // Speak whatever is currently on her lips, when it changes and the voice is on.
  useEffect(() => {
    if (!voice || !spoken) return
    setTalking(true)
    say.current?.say(spoken)
  }, [voice, spoken])

  useEffect(() => {
    if (!talking) return
    const s = synth()
    if (!s) return
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      if (!s.speaking) {
        stage.current?.setMouth(0)
        setTalking(false)
        return
      }
      const t = (now - start) / 1000
      stage.current?.setMouth(0.35 + 0.3 * Math.sin(t * 15) + 0.2 * Math.sin(t * 9.3))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(raf)
      stage.current?.setMouth(0)
    }
  }, [talking])

  async function onAsk(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || !target) return
    setBusy(true)
    setErrored(false)
    try {
      setAnswer(await ask(target.id, q))
    } catch {
      setAnswer(null)
      setErrored(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={live ? 'ask-companion is-live' : 'ask-companion'}>
      {wide && !failed && (
        <div className="ask-stage">
          <Suspense fallback={null}>
            <MascotStage
              mood={mood}
              onReady={() => setLive(true)}
              onFail={() => setFailed(true)}
              onStage={(s) => {
                stage.current = s
              }}
            />
          </Suspense>
        </div>
      )}

      <div className="ask-bubble" aria-live="polite">
        {/* WAITING AND FINISHED-WITH-NOTHING ARE DIFFERENT CLAIMS and used to look
            identical: the only in-flight signal was the submit button's label, so a
            hung renderer and an ignored click were indistinguishable from outside.
            That cost a UAT round -- a crashed tab was reported as "the UI drops the
            answer on the floor", and it took two clean reproductions to rule out.
            She now says she is reading, and says it in the bubble where the answer
            will appear. */}
        {busy ? (
          <p className="ask-read ask-waiting">Reading her posts…</p>
        ) : answer ? (
          <>
            <p className="ask-answer">{answer.answer}</p>
            {answer.covered ? (
              <Sources citations={answer.citations} />
            ) : (
              <p className="ask-uncovered">Nobody wrote about that one. I am not going to guess it for you.</p>
            )}
          </>
        ) : (
          <>
            <p className="ask-read">{reading.read}</p>
            <p className="ask-note">{reading.note}</p>
          </>
        )}
        {errored && <p className="ask-uncovered">I could not reach the posts just now. Try that again in a moment.</p>}
      </div>

      {target ? (
        <form className="ask-form" onSubmit={onAsk}>
          <p className="ask-target">
            Asking about <strong lang="und">{target.name}</strong>
            <button type="button" className="ask-clear" onClick={onClear}>
              Done
            </button>
          </p>
          <div className="ask-row">
            <input
              ref={field}
              className="ask-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Is it halal? Good for a group?"
              aria-label={`Ask about ${target.name}`}
              maxLength={300}
            />
            <button type="submit" className="btn btn-primary" disabled={busy || !question.trim()}>
              {busy ? 'Reading…' : 'Ask'}
            </button>
          </div>
        </form>
      ) : (
        <p className="ask-hint">Tap Ask on any pick and I will read its posts for you.</p>
      )}

      {synth() && (
        <button
          type="button"
          className="companion-voice"
          aria-pressed={voice}
          onClick={() => {
            const next = !voice
            setVoice(next)
            rememberVoice(next)
            if (!next) {
              say.current?.stop()
              setTalking(false)
            }
          }}
        >
          <span aria-hidden="true" className="companion-voice-icon">
            {voice ? '♪' : '×'}
          </span>
          {voice ? 'Voice On' : 'Voice Off'}
        </button>
      )}
    </div>
  )
}

/** The citations behind an answer, attached by the API from database rows and never
    parsed out of what the model said. Without these the answer is just a claim. */
function Sources({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null
  return (
    <ul className="ask-sources">
      {citations.map((c) => (
        <li key={c.post_url}>
          <a className="link" href={c.post_url} target="_blank" rel="noreferrer noopener">
            {c.platform === 'google_maps' ? 'Google Maps' : 'RedNote'}
            {c.posted_at ? `, ${c.posted_at}` : ''}
          </a>
        </li>
      ))}
    </ul>
  )
}
