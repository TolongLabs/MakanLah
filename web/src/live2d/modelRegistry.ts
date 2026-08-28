import type { MascotMood } from '../evidence'

/**
 * LiveroiD_A-Y01, from the owner's Kawan app. `scale` and `anchorY` are the values
 * that already frame this model correctly there; the model3.json carries no motions,
 * so the idle group is empty and pixi-live2d-display falls back to auto-idle.
 *
 * Y01's expressions reference ../LiveroiD_A-Y02/, so both folders must be present.
 * Neither is in this repository. See web/public/models/README.md.
 */
export const MODEL = {
  url: '/models/liveroid/LiveroiD_A-Y01/LiveroiD_A-Y01.model3.json',
  idleMotionGroup: '',
  // Kawan's values frame this model on a much taller stage. In a 200px rail box they
  // render a small full body with the legs cropped, which reads as a mistake rather
  // than a portrait. Scaled up and anchored higher to crop to head and shoulders.
  scale: 0.3,
  anchorY: 0.08
} as const

/** Bound to evidence strength, not sentiment. A mascot that only ever smiles is
    decoration; this one reports what the corpus actually holds. */
export const EXPRESSION: Record<MascotMood, string> = {
  curious: 'browLink',
  pleased: 'blush',
  skeptical: 'cool',
  concerned: 'worried'
}
