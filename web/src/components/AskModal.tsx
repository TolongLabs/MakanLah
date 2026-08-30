import { type FormEvent, lazy, Suspense, useEffect, useRef, useState } from 'react'
import { type AskEvent, type AskTurn, ask, askStream, type Citation, NoStream, type ToolStep } from '../api'
import { speaker, voiceEnabled } from '../companion/voice'
import { platformName } from '../format'
import type { Live2DStage } from '../live2d/Live2DStage'
import { Modal } from './Modal'
import { StageBoundary } from './StageBoundary'

const MascotStage = lazy(() => import('../live2d/MascotStage'))

/** Mirrors every other stage gate in the app. Below it she is not mounted at all
    rather than hidden: a phone was downloading 500 KB of pixi and allocating a WebGL
    context for a canvas measured at 1x1. */
const STAGE_AT = '(min-width: 48rem)'

export type AskTarget = { id: string; name: string } | null

/** `id` rather than an array index. Turns only ever append today, but a key that
    encodes position is a bug waiting for the first edit-or-retry feature, and React
    reuses the wrong DOM node when one lands. */
type Turn = { id: number } & (
  | { role: 'user'; content: string }
  | { role: 'assistant'; content: string; tools: ToolStep[]; citations: Citation[]; covered: boolean }
)

/**
 * The copilot, in front of the page.
 *
 * **This is a conversation, not a lookup, and the difference is the point.** It used
 * to be one question in and one answer out, in the right-hand aside — which on a
 * phone sits below every result, so tapping Ask targeted a form several screens down
 * and appeared to do nothing at all.
 *
 * **The tool trace is the evidence claim, made watchable.** `makanlah/copilot.py`
 * has always enforced that she answers from a venue's stored excerpts or declines,
 * and that guarantee has always been invisible: the user was told she looked.
 * Watching `read_citations → 4 posts` happen is the same claim, checkable. It is
 * also what makes `covered: false` land — she is seen looking, and finding nothing.
 *
 * Steps expand while she works and collapse to one line once she answers, because
 * during the wait the trace is the only thing happening and afterwards the answer is
 * what matters. The collapsed row stays openable rather than disappearing; a trail
 * you can no longer inspect is not a trail.
 *
 * **She is one stage, moved, never two.** The aside stops mounting her while this is
 * open. Two Live2D stages means two WebGL contexts for one character.
 *
 * **`POST /ask` is the fallback and must keep working.** Until `/ask/stream` is
 * deployed, `NoStream` sends every turn down the one-shot path, which produces the
 * same conversation without the trace.
 */
export function AskModal({ target, onClose }: { target: NonNullable<AskTarget>; onClose: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [live, setLive] = useState<ToolStep[]>([])
  const [streamed, setStreamed] = useState('')
  const [errored, setErrored] = useState(false)
  const [wide] = useState(() => window.matchMedia?.(STAGE_AT).matches ?? false)
  const [failed, setFailed] = useState(false)
  const [talking, setTalking] = useState(false)

  const field = useRef<HTMLInputElement>(null)
  const say = useRef<ReturnType<typeof speaker> | null>(null)
  const stage = useRef<Live2DStage | null>(null)
  const log = useRef<HTMLDivElement>(null)
  const abort = useRef<AbortController | null>(null)
  const nextId = useRef(0)

  useEffect(() => {
    say.current = speaker()
    // Native showModal() focuses the first tabbable node, which is the close button.
    field.current?.focus()
    return () => {
      abort.current?.abort()
      say.current?.stop()
    }
  }, [])

  // Follow the conversation as it grows, the way a chat log should.
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: 'smooth' })
  }, [])

  // The mouth, driven outside React: a state update per frame would re-render the
  // whole conversation sixty times a second to move a jaw.
  useEffect(() => {
    if (!talking) return
    const s = window.speechSynthesis
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

  function finish(turn: Omit<Extract<Turn, { role: 'assistant' }>, 'id'>) {
    setTurns((t) => [...t, { ...turn, id: nextId.current++ }])
    setLive([])
    setStreamed('')
    if (voiceEnabled() && turn.content) {
      say.current?.say(turn.content)
      setTalking(true)
    }
    requestAnimationFrame(() => log.current?.scrollTo({ top: log.current.scrollHeight, behavior: 'smooth' }))
  }

  async function send(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || busy) return

    const history: AskTurn[] = [
      ...turns.map((t) => ({ role: t.role, content: t.content })),
      { role: 'user', content: q }
    ]
    setTurns((t) => [...t, { id: nextId.current++, role: 'user', content: q }])
    setQuestion('')
    setBusy(true)
    setErrored(false)
    setLive([])
    setStreamed('')

    const ctl = new AbortController()
    abort.current = ctl

    try {
      const steps: ToolStep[] = []
      let text = ''
      let ended: Extract<AskEvent, { type: 'done' }> | null = null

      for await (const ev of askStream(target.id, history, ctl.signal)) {
        if (ev.type === 'tool_call') {
          steps.push({ id: ev.id, name: ev.name, args: ev.args })
          setLive([...steps])
        } else if (ev.type === 'tool_result') {
          const step = steps.find((s) => s.id === ev.id)
          if (step) {
            step.summary = ev.summary
            step.count = ev.count
          }
          setLive([...steps])
        } else if (ev.type === 'delta') {
          text += ev.text
          setStreamed(text)
        } else if (ev.type === 'done') {
          ended = ev
        }
      }

      finish({
        role: 'assistant',
        content: ended?.answer ?? text,
        tools: steps,
        citations: ended?.citations ?? [],
        covered: ended?.covered ?? false
      })
    } catch (err) {
      if (ctl.signal.aborted) return
      if (err instanceof NoStream) {
        // The route is not deployed. Same conversation, no visible trace.
        try {
          const r = await ask(target.id, q)
          finish({ role: 'assistant', content: r.answer, tools: [], citations: r.citations, covered: r.covered })
        } catch {
          setErrored(true)
        }
      } else {
        setErrored(true)
      }
    } finally {
      setBusy(false)
      abort.current = null
    }
  }

  return (
    <Modal
      onClose={onClose}
      title={
        <>
          Asking About{' '}
          <span lang="und" className="modal-title-subject">
            {target.name}
          </span>
        </>
      }
    >
      <div className="chat">
        {wide && !failed && (
          <div className="chat-stage">
            <StageBoundary onFail={() => setFailed(true)}>
              <Suspense fallback={null}>
                <MascotStage
                  mood={turns.some((t) => t.role === 'assistant' && !t.covered) ? 'concerned' : 'curious'}
                  onReady={() => {}}
                  onFail={() => setFailed(true)}
                  onStage={(s) => {
                    stage.current = s
                  }}
                />
              </Suspense>
            </StageBoundary>
          </div>
        )}

        <div className="chat-log" ref={log} aria-live="polite">
          {turns.length === 0 && !busy && (
            <p className="chat-opener">
              I will read what people wrote about this one and answer from that, or tell you they did not say.
            </p>
          )}

          {turns.map((t) =>
            t.role === 'user' ? (
              <p className="chat-said" key={t.id}>
                {t.content}
              </p>
            ) : (
              <div className="chat-reply" key={t.id}>
                {t.tools.length > 0 && <Steps steps={t.tools} done />}
                <p className="chat-answer">{t.content}</p>
                {/* A CAPTION FOR THE ABSENT SOURCES, not a second refusal. The
                    answer above already says the posts do not cover it -- the API
                    writes that sentence -- and the old panel printed "Nobody wrote
                    about that one" underneath it, which said the same thing twice.
                    What the reader needs here is why there is nothing to click,
                    because an empty space where citations usually sit reads as a
                    load that failed. */}
                {t.covered ? (
                  <Sources citations={t.citations} />
                ) : (
                  <p className="chat-uncited">Nothing to cite. She will not guess it for you.</p>
                )}
              </div>
            )
          )}

          {busy && (
            <div className="chat-reply">
              {live.length > 0 && <Steps steps={live} />}
              {streamed ? (
                <p className="chat-answer">{streamed}</p>
              ) : (
                <p className="chat-waiting">{live.length > 0 ? 'Reading what she found…' : 'Reading her posts…'}</p>
              )}
            </div>
          )}

          {errored && (
            <p className="chat-uncovered">I could not reach the posts just now. Try that again in a moment.</p>
          )}
        </div>

        <form className="chat-form" onSubmit={send}>
          <input
            ref={field}
            className="ask-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={turns.length > 0 ? 'Ask something else' : 'Is it halal? Good for a group?'}
            aria-label={`Ask about ${target.name}`}
            maxLength={300}
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !question.trim()}>
            {busy ? 'Reading…' : 'Ask'}
          </button>
        </form>
      </div>
    </Modal>
  )
}

/**
 * What she did before answering.
 *
 * Open while she works, collapsed to one line once she has answered — the trace is
 * the only thing happening during the wait, and afterwards the answer is what
 * matters. Collapsed rather than removed: a trail you cannot reopen is not a trail.
 */
function Steps({ steps, done = false }: { steps: ToolStep[]; done?: boolean }) {
  if (!done) {
    return (
      <ol className="steps">
        {steps.map((s) => (
          <li className={s.summary ? 'step' : 'step step-running'} key={s.id}>
            <span className="step-name">{s.name.replace(/_/g, ' ')}</span>
            <span className="step-out">{s.summary ?? '…'}</span>
          </li>
        ))}
      </ol>
    )
  }
  return (
    <details className="steps-done">
      <summary className="steps-toggle">
        {steps.length === 1 ? '1 step' : `${steps.length} steps`} before answering
      </summary>
      <ol className="steps">
        {steps.map((s) => (
          <li className="step" key={s.id}>
            <span className="step-name">{s.name.replace(/_/g, ' ')}</span>
            <span className="step-out">{s.summary ?? '—'}</span>
          </li>
        ))}
      </ol>
    </details>
  )
}

/** The citations behind an answer, attached by the API from database rows and never
    parsed out of what the model said. Without these the answer is just a claim. */
function Sources({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null
  return (
    <ul className="ask-sources">
      {citations.map((c) => (
        <li key={c.post_id ?? c.post_url}>
          <a className="link" href={c.post_url} target="_blank" rel="noreferrer noopener">
            {platformName(c.platform)}
            {c.posted_at ? `, ${c.posted_at}` : ''}
          </a>
        </li>
      ))}
    </ul>
  )
}
