import { useEffect, useRef } from 'react'
import type { MascotMood } from '../evidence'
import { Live2DStage } from './Live2DStage'
import { EXPRESSION, MODEL } from './modelRegistry'

/**
 * The React host. Split from Mascot.tsx so that pixi and pixi-live2d-display land in
 * their own lazily-imported chunk and never reach a visitor who does not see a mascot.
 */
export default function MascotStage({
  mood,
  onReady,
  onFail,
  onStage
}: {
  mood: MascotMood
  onReady: () => void
  onFail: () => void
  /** The controller, handed out so a host can drive the mouth from a rAF loop.
      Going through props would re-render React at frame rate. */
  onStage?: (stage: Live2DStage | null) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<Live2DStage | null>(null)
  const settled = useRef({ ready: onReady, fail: onFail, stage: onStage })
  settled.current = { ready: onReady, fail: onFail, stage: onStage }

  useEffect(() => {
    const container = containerRef.current
    if (container == null) return

    let cancelled = false
    const stage = new Live2DStage()
    stageRef.current = stage

    stage
      .mount(container, MODEL)
      .then(() => {
        if (cancelled) return
        settled.current.stage?.(stage)
        settled.current.ready()
      })
      .catch(() => {
        // The model binaries are not in this repository, so this is the expected path
        // until somebody drops them in. The host keeps the fallback, which carries the
        // same reading, and nothing on the results path waits for any of it.
        if (!cancelled) settled.current.fail()
      })

    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect
      if (box) stage.resize(Math.max(box.width, 1), Math.max(box.height, 1))
    })
    observer.observe(container)

    return () => {
      cancelled = true
      observer.disconnect()
      settled.current.stage?.(null)
      stage.destroy()
      stageRef.current = null
    }
  }, [])

  useEffect(() => {
    stageRef.current?.setExpression(EXPRESSION[mood])
  }, [mood])

  return <div ref={containerRef} className="mascot-canvas" aria-hidden="true" />
}
