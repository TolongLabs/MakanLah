import { useEffect, useRef } from 'react'
import type { MascotMood } from '../evidence'
import { Live2DStage } from './Live2DStage'
import { EXPRESSION, MODEL } from './modelRegistry'

/**
 * The React host. Split from Mascot.tsx so that pixi and pixi-live2d-display land in
 * their own lazily-imported chunk and never reach a visitor who does not see a mascot.
 */
export default function MascotStage({ mood, onFail }: { mood: MascotMood; onFail: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<Live2DStage | null>(null)
  const failRef = useRef(onFail)
  failRef.current = onFail

  useEffect(() => {
    const container = containerRef.current
    if (container == null) return

    let cancelled = false
    const stage = new Live2DStage()
    stageRef.current = stage

    stage.mount(container, MODEL).catch(() => {
      // The model binaries are not in this repository, so this is the expected path
      // until someone drops them in. The host swaps to a fallback that carries the
      // same reading, and nothing on the results path waits for any of it.
      if (!cancelled) failRef.current()
    })

    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect
      if (box) stage.resize(Math.max(box.width, 1), Math.max(box.height, 1))
    })
    observer.observe(container)

    return () => {
      cancelled = true
      observer.disconnect()
      stage.destroy()
      stageRef.current = null
    }
  }, [])

  useEffect(() => {
    stageRef.current?.setExpression(EXPRESSION[mood])
  }, [mood])

  return <div ref={containerRef} aria-hidden="true" style={{ width: '100%', height: '100%' }} />
}
