import * as PIXI from 'pixi.js'
import { loadCubismCore } from './cubismCore'

// pixi-live2d-display reads window.PIXI when it is imported, to patch the display
// object prototype. The assignment has to happen before that import resolves, which
// is why the import below is dynamic and lives inside mount().
;(window as unknown as Record<string, unknown>).PIXI = PIXI

type Live2DModelLike = PIXI.DisplayObject & {
  scale: PIXI.ObservablePoint
  anchor: PIXI.ObservablePoint
  x: number
  y: number
  expression(name: string): Promise<unknown>
  destroy(): void
}

export type MountOptions = {
  url: string
  idleMotionGroup: string
  scale: number
  anchorY: number
}

/**
 * Vanilla controller for the Pixi application and the Live2D model. No React, so the
 * React host can mount and tear it down without the two lifecycles arguing.
 *
 * Pixi owns the canvas: no `view` option is passed, so every mount() appends a brand
 * new <canvas> and gets a virgin WebGL context. That is what survives StrictMode's
 * double mount, which otherwise hands back a context-poisoned canvas.
 */
export class Live2DStage {
  private app: PIXI.Application | null = null
  private model: Live2DModelLike | null = null
  private destroyed = false
  private baseScale = 0.11
  private anchorY = 0

  async mount(container: HTMLElement, opts: MountOptions): Promise<void> {
    await loadCubismCore()
    const { Live2DModel } = await import('pixi-live2d-display/cubism4')
    if (this.destroyed) return

    const { width, height } = container.getBoundingClientRect()
    const w = Math.max(width, 1)
    const h = Math.max(height, 1)

    // Pixi v6 constructor. v7/v8 would be app.init(); this project is pinned to 6.
    const app = new PIXI.Application({
      width: w,
      height: h,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1
    })
    this.app = app
    container.appendChild(app.view as unknown as HTMLCanvasElement)

    const model = (await Live2DModel.from(opts.url, {
      idleMotionGroup: opts.idleMotionGroup,
      autoUpdate: true
    })) as unknown as Live2DModelLike

    // destroy() may have run while the model was loading. Release it rather than
    // adding it to a stage that is already gone.
    if (this.destroyed || this.app == null) {
      model.destroy()
      return
    }

    this.model = model
    this.app.stage.addChild(model)
    this.baseScale = opts.scale
    this.anchorY = opts.anchorY
    this.fit(w, h)
  }

  setExpression(name: string): void {
    // Unknown expression, or a model still settling. Either is a no-op, never a throw.
    void this.model?.expression(name).catch(() => {})
  }

  resize(w: number, h: number): void {
    if (this.app == null || this.model == null) return
    this.app.renderer.resize(w, h)
    this.fit(w, h)
  }

  destroy(): void {
    this.destroyed = true
    if (this.app != null) {
      // removeView=true drops the canvas element, so the next mount appends a fresh one.
      this.app.destroy(true, { children: true })
      this.app = null
    }
    this.model = null
  }

  private fit(w: number, h: number): void {
    if (this.model == null) return
    // 600 is the reference height the scale values in modelRegistry were measured at.
    this.model.scale.set((h * this.baseScale) / 600)
    this.model.x = w / 2
    this.model.y = h * 0.05
    this.model.anchor.set(0.5, this.anchorY)
  }
}
