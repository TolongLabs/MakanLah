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
  const [stageFailed, setStageFailed] = useState(false)
  const [wanted, setWanted] = useState(false)
  const { read, note } = readingFor(mood)

  // Deferred past first paint on purpose. pixi plus pixi-live2d-display is heavy for a
  // PWA that promises a decision in two minutes.
  useEffect(() => {
    if (off) return
    const idle = window.requestIdleCallback
    if (typeof idle === 'function') {
      const id = idle(() => setWanted(true), { timeout: 2500 })
      return () => window.cancelIdleCallback?.(id)
    }
    const t = setTimeout(() => setWanted(true), 1200)
    return () => clearTimeout(t)
  }, [off])

  if (off) return null

  const showStage = wanted && !stageFailed

  return (
    <div className="mascot">
      {showStage ? (
        <Suspense fallback={null}>
          <MascotStage mood={mood} onFail={() => setStageFailed(true)} />
        </Suspense>
      ) : (
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
