import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { rememberVoice, speaker, synth, voiceEnabled } from '../companion/voice'
import { type CompanionPhase, type Evidence, type MascotMood, moodFor, readingFor } from '../evidence'
import type { Live2DStage } from '../live2d/Live2DStage'
import { StageBoundary } from './StageBoundary'

const MascotStage = lazy(() => import('../live2d/MascotStage'))

/* Must match the tablet rule in results.css. Changing one and not the other is how
   the stage got CSS room on a tablet while React still refused to mount it. */
const STAGE_AT = '(min-width: 48rem)'

/**
 * The companion on the results page, where she has two jobs rather than a presence.
 *
 * **She reports how strong the evidence is**, unprompted, whenever a search lands.
 * That is real information the list itself cannot carry: "two independent sources
 * agree on the top one" is the difference between a recommendation and a mention,
 * and it is the product's whole claim said out loud.
 *
 * **And she is how you interrogate a pick**, though the interrogation itself now
 * happens in `AskModal`, in front of the page. It lived here and could not: on a
 * phone this aside sits below every result, so Ask targeted a form several screens
 * down and appeared to do nothing at all.
 *
 * What stays is what benefits from being ambient rather than modal — the character,
 * and an unprompted reading of the evidence. The line she says is written locally by
 * `readingFor` and is not generated.
 */
export function AskCompanion({
  evidence,
  degraded,
  phase = 'idle'
}: {
  evidence: Evidence | null
  degraded: boolean
  /** Nothing searched yet, searched and empty, or holding picks. The mood cannot
      carry this: `curious` means both "ask me something" and "I found nothing",
      and only one of those should tell you to answer the onboarding questions. */
  phase?: CompanionPhase
}) {
  const mood: MascotMood = moodFor(evidence, degraded)
  const reading = readingFor(mood, phase)

  const [wide, setWide] = useState(() => window.matchMedia?.(STAGE_AT).matches ?? false)
  const [live, setLive] = useState(false)
  const [failed, setFailed] = useState(false)
  const [voice, setVoice] = useState(voiceEnabled)
  const [talking, setTalking] = useState(false)

  const stage = useRef<Live2DStage | null>(null)
  const say = useRef<ReturnType<typeof speaker> | null>(null)

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

  const spoken = `${reading.read}. ${reading.note}`

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

  return (
    <div className={live ? 'ask-companion is-live' : 'ask-companion'}>
      {wide && !failed && (
        <div className="ask-stage">
          {/* Suspense handles the PENDING import; only the boundary handles the
              rejected one. Without it a failed chunk fetch throws through render
              and takes the panel with it. */}
          <StageBoundary onFail={() => setFailed(true)}>
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
          </StageBoundary>
        </div>
      )}

      <div className="ask-bubble" aria-live="polite">
        <p className="ask-read">{reading.read}</p>
        <p className="ask-note">{reading.note}</p>
      </div>

      {/* Only where there is something to tap. On the evidence-gap screen there are
          deliberately zero pickable cards, and inviting a tap on a pick that is not
          there is the same false claim as the reading above it. */}
      {phase === 'picks' && <p className="ask-hint">Tap Ask on any pick and I will read its posts for you.</p>}

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
