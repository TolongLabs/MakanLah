import * as PIXI from 'pixi.js'
import { loadCubismCore } from './cubismCore'

// pixi-live2d-display reads window.PIXI when it is imported, to patch the display
// object prototype. The assignment has to happen before that import resolves, which
// is why the import below is dynamic and lives inside mount().
;(window as unknown as Record<string, unknown>).PIXI = PIXI

type CoreModel = {
  setParameterValueById(id: string, value: number): void
}

type Live2DModelLike = PIXI.DisplayObject & {
  scale: PIXI.ObservablePoint
  anchor: PIXI.ObservablePoint
  x: number
  y: number
  expression(name: string): Promise<unknown>
  destroy(): void
  autoUpdate: boolean
  internalModel?: { coreModel?: CoreModel }
}

/** Cubism 4's standard mouth-open parameter. Every model built on the standard
    template carries it; a model that does not simply keeps its mouth shut. */
const MOUTH = 'ParamMouthOpenY'

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
    this.frame(w, h)
  }

  /**
   * Drive the mouth from outside, 0 shut to 1 open.
   *
   * Called from a rAF loop while the speech synthesiser is talking, which is why
   * it takes a number rather than a phoneme: the Web Speech API exposes no
   * amplitude and no visemes, only word-boundary events, so a real lip sync is
   * not available to ask for. An oscillation timed to actual speech reads as
   * talking; a still face beside a voice reads as broken.
   *
   * The parameter is written every frame because Cubism resets it on update.
   */
  setMouth(open: number): void {
    const core = this.model?.internalModel?.coreModel
    if (!core) return
    try {
      core.setParameterValueById(MOUTH, Math.min(1, Math.max(0, open)))
    } catch {
      // A model without the standard parameter. Silence is the correct outcome.
    }
  }

  setExpression(name: string): void {
    // Unknown expression, or a model still settling. Either is a no-op, never a throw.
    void this.model?.expression(name).catch(() => {})
  }

  resize(w: number, h: number): void {
    if (this.app == null || this.model == null) return
    this.app.renderer.resize(w, h)
    this.frame(w, h)
  }

  destroy(): void {
    this.destroyed = true
    if (this.model != null) {
      // ORDER MATTERS, AND THIS ONE CRASHED THE TAB.
      //
      // `autoUpdate: true` registers the model on PIXI.Ticker.shared, which is a
      // global and is NOT torn down with the Application. Destroying the app first
      // left the shared ticker still updating a model whose renderer was gone, and
      // the next frame threw
      //
      //   getAttribLocation: parameter 1 is not of type 'WebGLProgram'
      //
      // on every route change between the two screens that host her. Measured:
      // without this, six client-side round trips between /taste and /discover
      // CRASH THE TAB; with it, six round trips survive with the canvas still
      // rendering. Unregister from the ticker and release the model before the
      // renderer it draws through.
      //
      // A non-fatal `getAttribLocation` error still logs on each mount, from
      // Cubism's own shader singleton being keyed to a WebGL context that every
      // mount replaces. She renders correctly through it. Tracked separately --
      // it is in the vendored runtime, not here, and fixing it means either
      // reusing one context across mounts or reaching into Cubism internals.
      this.model.autoUpdate = false
      this.model.destroy()
      this.model = null
    }
    if (this.app != null) {
      // removeView=true drops the canvas element, so the next mount appends a fresh one.
      this.app.destroy(true, { children: true })
      this.app = null
    }
  }

  private frame(w: number, h: number): void {
    if (this.model == null) return
    // 600 is the reference height the scale values in modelRegistry were measured at.
    this.model.scale.set((h * this.baseScale) / 600)
    this.model.x = w / 2
    this.model.y = h * 0.05
    this.model.anchor.set(0.5, this.anchorY)
  }
}
