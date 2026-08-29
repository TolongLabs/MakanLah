import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { companionLine } from '../api'
import { type CompanionStep, scripted } from '../companion/lines'
import { rememberVoice, speaker, synth, voiceEnabled } from '../companion/voice'
import type { MascotMood } from '../evidence'
import type { Live2DStage } from '../live2d/Live2DStage'

const MascotStage = lazy(() => import('../live2d/MascotStage'))

/**
 * The companion who walks you through the wizard, and the one place in this app
 * where a generated sentence is allowed on screen.
 *
 * She is safe to generate precisely because she is useless as evidence: she sees
 * no corpus row, names no venue and makes no claim, and `makanlah/companion.py`
 * drops any line that drifts into one. Everything the product actually asserts
 * still arrives with the post behind it.
 *
 * Three things she must never do, each of which cost a version to learn:
 *
 * 1. Leave the bubble empty while a request is in flight. The scripted line for
 *    the step is on screen in the same frame the step changes; the server line
 *    replaces it only if it arrives before she starts speaking.
 * 2. Talk over herself. Stepping quickly through four questions used to queue
 *    four utterances and answer the last one long after the user moved on.
 * 3. Speak without being asked. Chrome and Safari refuse `speak()` before a user
 *    gesture, so a voice that defaulted on would be silent on step one and
 *    startling on step two. The toggle is the gesture, and the choice sticks.
 */

/**
 * How long she will wait for the server's line before speaking the scripted one.
 *
 * A shorter beat was measured and was wrong: at 400ms the fetch lost every single
 * time in the browser, so the model lane was wired up, called and never heard. She
 * now speaks the moment the line lands, and this is only the ceiling on how long
 * she will hold out for it.
 */
const SPEAK_BY_MS = 1200

/** The width at which she gains a stage. Mirrors `.companion-stage` in taste.css;
    the two have to agree, and CSS cannot tell React not to mount a component.

    This was 56rem, to match the width at which the rail becomes a sticky column. That
    conflated two different questions -- "is there room for a second column" and "is
    there room for a character" -- and the tablet band answered no to the second on the
    strength of the first. Measured at 834: 549 px of empty page below the last option,
    and no companion anywhere on it. The reason her stage is off on a phone, that 220px
    of character pushes the question below the fold, is a real constraint at 390 and
    not one at 834. */
const STAGE_AT = '(min-width: 48rem)'

/**
 * True only where the stage is actually visible.
 *
 * `display: none` on the container is not enough and the difference is measured:
 * with the CSS gate alone a phone still downloaded 500 KB of pixi, fetched the
 * moc3 and the physics JSON, and allocated a WebGL context for a canvas measured
 * at 1x1. The original mascot had this gate; rebuilding around it dropped it.
 */
function useWideEnough(): boolean {
  const [wide, setWide] = useState(() => window.matchMedia?.(STAGE_AT).matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.(STAGE_AT)
    if (!mq) return
    const on = () => setWide(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return wide
}

const MOOD: Record<CompanionStep, MascotMood> = {
  craving: 'curious',
  company: 'pleased',
  range: 'skeptical',
  mood: 'curious',
  done: 'pleased'
}

export function Companion({ step, picked, seed }: { step: CompanionStep; picked: string[]; seed: number }) {
  const [line, setLine] = useState(() => scripted(step, seed))
  // Mirrored in a ref because speak() runs a beat after the effect that scheduled
  // it, by which time the fetch may have replaced the line the closure captured.
  const lineRef = useRef(line)
  lineRef.current = line
  const [voice, setVoice] = useState(voiceEnabled)
  const [live, setLive] = useState(false)
  const [failed, setFailed] = useState(false)
  const [talking, setTalking] = useState(false)
  const wide = useWideEnough()

  const voiceRef = useRef(voice)
  voiceRef.current = voice
  const spoken = useRef(false)
  const say = useRef<ReturnType<typeof speaker> | null>(null)
  const stage = useRef<Live2DStage | null>(null)

  // The latest picks, without making them a dependency: re-fetching a line because
  // somebody toggled a fifth craving would restart the sentence mid-word.
  const picks = useRef(picked)
  picks.current = picked

  useEffect(() => {
    say.current = speaker()
    return () => say.current?.stop()
  }, [])

  // Stable, so the step effect below can depend on it honestly rather than suppress
  // the warning. Everything it touches is a ref or a setter, so there is nothing for
  // it to close over stale.
  const speak = useCallback(() => {
    if (!synth()) return
    setTalking(true)
    say.current?.say(lineRef.current)
  }, [])

  useEffect(() => {
    let current = true
    spoken.current = false
    lineRef.current = scripted(step, seed)
    setLine(lineRef.current)

    const now = () => {
      if (!current || spoken.current) return
      spoken.current = true
      if (voiceRef.current) speak()
    }

    companionLine(step, picks.current)
      .then((r) => {
        if (!current || !r.text) return
        // Swapping the text under a sentence she is already saying would leave the
        // bubble and the audio disagreeing. Silent, there is nothing to disagree
        // with, so a late line is still an improvement and is taken.
        if (!spoken.current || !voiceRef.current) {
          lineRef.current = r.text
          setLine(r.text)
        }
        now()
      })
      .catch(() => {
        // No API, no key, no quota, no network. She already has something to say.
      })

    // The ceiling, not the schedule: she speaks as soon as the line lands.
    const t = setTimeout(now, SPEAK_BY_MS)

    return () => {
      current = false
      clearTimeout(t)
      say.current?.stop()
    }
    // `line` is deliberately absent: this fires on a step change, and reading the
    // line from a ref at speak() time is what lets the fetch win the race.
  }, [step, seed, speak])

  // The mouth. Driven outside React, because a state update per frame would
  // re-render the whole wizard sixty times a second to move a jaw.
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
      // Two overlapping sines rather than one, so the jaw does not tick like a
      // metronome. No amplitude is available from the Web Speech API to drive it
      // properly, so this is a plausible mouth rather than a real lip sync.
      const t = (now - start) / 1000
      const open = 0.35 + 0.3 * Math.sin(t * 15) + 0.2 * Math.sin(t * 9.3)
      stage.current?.setMouth(open)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(raf)
      stage.current?.setMouth(0)
    }
  }, [talking])

  function toggleVoice() {
    const next = !voice
    setVoice(next)
    rememberVoice(next)
    if (next) {
      // This click is the user gesture the autoplay policy wants, so speaking
      // straight away both confirms the toggle and unlocks the synthesiser.
      spoken.current = true
      speak()
    } else {
      say.current?.stop()
      setTalking(false)
    }
  }

  return (
    <div className={live ? 'companion companion-live' : 'companion'}>
      <div className="companion-stage">
        {wide && !failed && (
          <Suspense fallback={null}>
            <MascotStage
              mood={MOOD[step]}
              onReady={() => setLive(true)}
              onFail={() => setFailed(true)}
              onStage={(s) => {
                stage.current = s
              }}
            />
          </Suspense>
        )}
      </div>
      <p className="companion-bubble fade-in" key={line} aria-live="polite">
        {line}
      </p>
      {synth() && (
        <button type="button" className="companion-voice" onClick={toggleVoice} aria-pressed={voice}>
          <span aria-hidden="true" className="companion-voice-icon">
            {voice ? '♪' : '×'}
          </span>
          {voice ? 'Voice On' : 'Voice Off'}
        </button>
      )}
    </div>
  )
}
