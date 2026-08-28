import { lazy, Suspense, useEffect, useState } from 'react'
import { type MascotMood, readingFor } from '../evidence'

const MascotStage = lazy(() => import('../live2d/MascotStage'))

const DISMISS_KEY = 'makanlah.mascot.off'

function dismissed(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === '1'
  } catch {
    return false
  }
}

/**
 * The mascot reports evidence strength. Three rules from issue #11 shape it:
 *
 * 1. It is never on the critical path. The reading renders immediately as text; the
 *    Live2D chunk is only imported after first paint, and results never wait for it.
 * 2. It is dismissible, and the choice sticks.
 * 3. If the model cannot load, the reading stays. The information is the point, the
 *    face is the presentation, and the two are allowed to come apart.
 */
export function Mascot({ mood }: { mood: MascotMood }) {
  const [off, setOff] = useState(dismissed)
  // 'idle' until first paint is past, 'loading' while the chunk and the model are in
  // flight, then one of two terminal states. The reading stays on screen for the first
  // three, so there is never a frame where the panel is blank.
  const [phase, setPhase] = useState<'idle' | 'loading' | 'live' | 'failed'>('idle')
  const { read, note } = readingFor(mood)

  // Deferred past first paint on purpose. pixi plus pixi-live2d-display is heavy for a
  // PWA that promises a decision in two minutes.
  useEffect(() => {
    if (off) return
    const start = () => setPhase((p) => (p === 'idle' ? 'loading' : p))
    const idle = window.requestIdleCallback
    if (typeof idle === 'function') {
      const id = idle(start, { timeout: 2500 })
      return () => window.cancelIdleCallback?.(id)
    }
    const t = setTimeout(start, 1200)
    return () => clearTimeout(t)
  }, [off])

  if (off) return null

  return (
    <div className={phase === 'live' ? 'mascot mascot-live' : 'mascot'}>
      {phase !== 'idle' && phase !== 'failed' && (
        <Suspense fallback={null}>
          <MascotStage mood={mood} onReady={() => setPhase('live')} onFail={() => setPhase('failed')} />
        </Suspense>
      )}
      {phase !== 'live' && (
        <div className="mascot-fallback">
          <p className="mascot-read">{read}</p>
          <p className="mascot-note">{note}</p>
        </div>
      )}
      <button
        type="button"
        className="mascot-dismiss"
        onClick={() => {
          try {
            localStorage.setItem(DISMISS_KEY, '1')
          } catch {
            // Nothing to remember it with. Hiding it for this session is enough.
          }
          setOff(true)
        }}
      >
        Hide
      </button>
      <p className="sr-only" aria-live="polite">
        {`${read}. ${note}`}
      </p>
    </div>
  )
}
