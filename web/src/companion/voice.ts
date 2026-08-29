/**
 * The companion's speaking voice, on the browser's own synthesiser.
 *
 * No key, no network, no bundle weight, and nothing to bill. The alternative was
 * a hosted TTS returning audio through our API, which would put an audio file on
 * the request path of a wizard that promises a decision in two minutes, and cost
 * money per sentence for a feature nobody needs to hear twice.
 *
 * The register is set by pitch and rate rather than by a model: a high pitch and
 * a slightly quick delivery on a light female voice is what reads as the cute
 * anime companion the owner asked for, and it is the same two dials on every
 * platform. It is an approximation of that voice and worth saying so; a real
 * character voice needs a real voice actor or a paid TTS.
 *
 * OFF BY DEFAULT, AND THAT IS NOT TIMIDITY. Chrome and Safari refuse
 * `speechSynthesis.speak()` until the page has had a user gesture, so a voice
 * that switched itself on would be silent on the first step and startling on the
 * second. The toggle is the gesture. The choice is remembered.
 */

const KEY = 'makanlah.companion.voice'

export function synth(): SpeechSynthesis | null {
  // jsdom has no speechSynthesis, and neither does every mobile browser.
  return typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null
}

export function voiceEnabled(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function rememberVoice(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? '1' : '0')
  } catch {
    // A browser with storage blocked still gets the voice for this session.
  }
}

/**
 * Names that mark a light, higher-pitched voice on at least one major platform.
 * Ordered best-first. Matched case-insensitively against `voice.name`.
 *
 * A list of names is a blunt instrument and will miss voices it should catch:
 * the Web Speech API exposes no gender, no age and no timbre, only a name and a
 * language tag, so there is nothing better to sort on. Everything unmatched
 * still speaks -- in whatever the platform default is -- rather than falling
 * silent, which is why this ranks rather than filters.
 */
const PREFERRED = [
  'google uk english female',
  'samantha',
  'karen',
  'tessa',
  'microsoft aria',
  'microsoft zira',
  'microsoft sonia',
  'female'
]

function score(v: SpeechSynthesisVoice): number {
  const name = v.name.toLowerCase()
  const named = PREFERRED.findIndex((p) => name.includes(p))
  // Malaysian English first where it exists, then any English at all. A voice in
  // the wrong language reads "makan" and "lah" as nonsense.
  const lang = v.lang.toLowerCase()
  const langBonus = lang.startsWith('en-my') ? 30 : lang.startsWith('en-gb') ? 20 : lang.startsWith('en') ? 10 : -50
  return (named === -1 ? 0 : PREFERRED.length - named) * 4 + langBonus
}

export function pickVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const usable = voices.filter((v) => v.lang.toLowerCase().startsWith('en'))
  const pool = usable.length > 0 ? usable : voices
  if (pool.length === 0) return null
  return pool.reduce((best, v) => (score(v) > score(best) ? v : best))
}

/**
 * Chrome populates `getVoices()` asynchronously and returns an empty array on
 * the first call. Resolving on `voiceschanged` is the documented way round it;
 * the timeout is there because a browser that already had them never fires the
 * event.
 */
export function voicesReady(s: SpeechSynthesis, timeoutMs = 1200): Promise<SpeechSynthesisVoice[]> {
  const now = s.getVoices()
  if (now.length > 0) return Promise.resolve(now)
  return new Promise((resolve) => {
    let settled = false
    const done = () => {
      if (settled) return
      settled = true
      s.removeEventListener?.('voiceschanged', done)
      resolve(s.getVoices())
    }
    s.addEventListener?.('voiceschanged', done)
    setTimeout(done, timeoutMs)
  })
}

export type Speaker = {
  say(text: string): void
  stop(): void
}

/** The cute register, as two numbers rather than as a personality. */
export const PITCH = 1.6
export const RATE = 1.05

export function speaker(): Speaker {
  const s = synth()
  if (!s) return { say: () => {}, stop: () => {} }

  let chosen: SpeechSynthesisVoice | null = null
  let generation = 0

  return {
    say(text: string) {
      const mine = ++generation
      // One line at a time. Without the cancel, stepping quickly through the
      // wizard queues four questions and the companion answers the last one
      // several sentences after the user has moved on.
      s.cancel()
      const start = (voices: SpeechSynthesisVoice[]) => {
        if (mine !== generation) return
        chosen = chosen ?? pickVoice(voices)
        const u = new SpeechSynthesisUtterance(text)
        if (chosen) {
          u.voice = chosen
          u.lang = chosen.lang
        }
        u.pitch = PITCH
        u.rate = RATE
        s.speak(u)
      }
      if (chosen) start([])
      else void voicesReady(s).then(start)
    },
    stop() {
      generation++
      s.cancel()
    }
  }
}
