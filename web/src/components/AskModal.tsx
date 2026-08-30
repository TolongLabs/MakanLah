import { type FormEvent, useEffect, useRef, useState } from 'react'
import { type AskResponse, ask, type Citation } from '../api'
import { speaker, voiceEnabled } from '../companion/voice'
import { platformName } from '../format'
import { Modal } from './Modal'

export type AskTarget = { id: string; name: string } | null

/**
 * Interrogating one pick, in front of the results rather than beside them.
 *
 * This used to live in the right-hand aside, and on a phone that aside sits below
 * every result on the page. Tapping "Ask About This" scrolled nothing, opened
 * nothing and gave no feedback: the form it targeted was several screens down. The
 * control looked broken because, from where the user was standing, it was.
 *
 * SHE STILL NEVER ANSWERS FROM HER OWN KNOWLEDGE. Every word comes back from `/ask`,
 * which answers out of that venue's citations or declines. `covered: false` renders
 * as a refusal with no sources attached rather than as a hedge — a chatbot cannot
 * say "nobody wrote about that" because it has no evidence trail to be honest about,
 * and saying it is the feature.
 *
 * The mascot stays in the aside and is not duplicated here. Two Live2D stages means
 * two WebGL contexts for one character, and she is visible through the blurred
 * backdrop on any screen wide enough to have had her in the first place.
 */
export function AskModal({ target, onClose }: { target: NonNullable<AskTarget>; onClose: () => void }) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [errored, setErrored] = useState(false)

  const field = useRef<HTMLInputElement>(null)
  const say = useRef<ReturnType<typeof speaker> | null>(null)

  useEffect(() => {
    say.current = speaker()
    // Native `showModal()` focuses the first tabbable node, which is the close
    // button. The question field is what this dialog is for.
    field.current?.focus()
    return () => say.current?.stop()
  }, [])

  // `speaker().say()` cancels whatever is mid-sentence, so this pre-empts the
  // aside's ambient reading rather than talking over it.
  useEffect(() => {
    if (!answer || !voiceEnabled()) return
    say.current?.say(answer.answer)
  }, [answer])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q) return
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
      <form className="ask-form ask-form-modal" onSubmit={onSubmit}>
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

      <div className="ask-bubble ask-bubble-modal" aria-live="polite">
        {/* WAITING AND FINISHED-WITH-NOTHING ARE DIFFERENT CLAIMS. With no in-flight
            signal beyond the button label, a hung renderer and an ignored click look
            identical from outside — that cost a UAT round once, reported as "the UI
            drops the answer on the floor". */}
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
          <p className="ask-note">
            I will read what people wrote about this one and answer from that, or say I cannot.
          </p>
        )}
        {errored && <p className="ask-uncovered">I could not reach the posts just now. Try that again in a moment.</p>}
      </div>
    </Modal>
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
            {platformName(c.platform)}
            {c.posted_at ? `, ${c.posted_at}` : ''}
          </a>
        </li>
      ))}
    </ul>
  )
}
