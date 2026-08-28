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
  scale: 0.11,
  anchorY: 0.24
} as const

/** Bound to evidence strength, not sentiment. A mascot that only ever smiles is
    decoration; this one reports what the corpus actually holds. */
export const EXPRESSION: Record<MascotMood, string> = {
  curious: 'browLink',
  pleased: 'blush',
  skeptical: 'cool',
  concerned: 'worried'
}
