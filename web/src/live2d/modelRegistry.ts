import type { MascotMood } from '../evidence'

/**
 * LiveroiD_A-Y01, from the owner's Kawan app. `scale` and `anchorY` are the values
 * that already frame this model correctly there; the model3.json carries no motions,
 * so the idle group is empty and pixi-live2d-display falls back to auto-idle.
 *
 * Y01's expressions reference ../LiveroiD_A-Y02/, so both folders must be present.
 * Neither is in this repository. See web/public/models/README.md.
 */
/**
 * Framing, measured off the model rather than eyeballed.
 *
 * THE PREVIOUS VALUES PAINTED NOTHING. `scale: 0.3, anchorY: 0.08` shipped to
 * production and rendered a completely empty canvas: every asset loaded, the
 * WebGL context was live, `onReady` fired, and 0% of the canvas had ink in it.
 *
 * The reason is that the model canvas is 4648x8000 units and **the character's
 * ink starts 34.3% of the way down it** -- the top third is empty space. The old
 * anchor framed units 536 to 2536, which is entirely air above her head. Nothing
 * was broken; the camera was pointed at the wrong part of the sheet.
 *
 * Measured by fitting the whole model into a probe canvas and reading back the
 * alpha channel to find the ink bounding box:
 *
 *   ink x 537..4098 of 4648   (centred: fraction 0.4986, so anchor.x 0.5 is right)
 *   ink y 2741..7990 of 8000  (starts at fraction 0.3427)
 *
 * `anchorY` is therefore the ink's own top fraction, which puts the top of her
 * head just under the top of the box. `scale` crops to head and shoulders: at
 * 0.381 the painted coverage of a 288x220 rail box is 57.8%.
 *
 * `scripts/mascot_check.mjs` asserts the canvas is not blank, in CI, because the
 * check that existed only asserted a live WebGL context -- which a blank canvas
 * has too. That is what let this ship.
 */
export const MODEL = {
  url: '/models/liveroid/LiveroiD_A-Y01/LiveroiD_A-Y01.model3.json',
  idleMotionGroup: '',
  scale: 0.381,
  anchorY: 0.343
} as const

/** Bound to evidence strength, not sentiment. A mascot that only ever smiles is
    decoration; this one reports what the corpus actually holds. */
export const EXPRESSION: Record<MascotMood, string> = {
  curious: 'browLink',
  pleased: 'blush',
  skeptical: 'cool',
  concerned: 'worried'
}
