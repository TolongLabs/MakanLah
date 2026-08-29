export type CompanionStep = 'craving' | 'company' | 'range' | 'mood' | 'done'

/**
 * The lines the companion always has.
 *
 * A deliberate copy of `SCRIPT` in `makanlah/companion.py`, not an import: the
 * wizard speaks the instant a step changes, and a spoken question that arrives
 * three hundred milliseconds after the question it is asking about has already
 * been read is worse than one that never varies. The server's line, when it
 * arrives, replaces this one; when the API is down, unset or out of free quota,
 * nobody can tell the difference.
 *
 * `web/src/__tests__/companion.test.ts` asserts the two lists stay in step, so a
 * change to one is a failing test rather than a silent drift.
 */
export const SCRIPT: Record<CompanionStep, string[]> = {
  craving: [
    'Okay, tell me. What are you craving right now?',
    'Hungry already? Pick whatever sounds good, as many as you like.',
    'So, what are we eating today? Go on, pick a few.'
  ],
  company: [
    'Nice choice! Now, who is eating with you?',
    'Ooh, good pick. Is anyone coming along?',
    'Lovely. Are you going alone, or bringing people?'
  ],
  range: [
    'How far would you go for this? Be honest.',
    'Walking distance, or are we driving?',
    'Okay, how far are you willing to travel?'
  ],
  mood: [
    'Last one, I promise. What kind of meal are you after?',
    'Almost done! Comfort food, or something new?',
    'One more. What sort of meal are we in the mood for?'
  ],
  done: [
    'Got it. Let me go and read what people actually wrote.',
    'Perfect. Finding you somebody who has already eaten there.',
    'On it. Every pick comes with the post behind it, promise.'
  ]
}

/** The step order the wizard walks, so a step index maps to a key. */
export const STEP_KEYS: CompanionStep[] = ['craving', 'company', 'range', 'mood']

/**
 * Picked by seed rather than at random, so a step revisited with Back says what
 * it said the first time. A companion that reworded itself every time you
 * stepped backwards would read as three different companions.
 */
export function scripted(step: CompanionStep, seed: number): string {
  const pool = SCRIPT[step]
  return pool[Math.abs(seed) % pool.length] ?? pool[0] ?? ''
}
