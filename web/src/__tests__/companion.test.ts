import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { SCRIPT, STEP_KEYS, scripted } from '../companion/lines'
import { PITCH, pickVoice, RATE } from '../companion/voice'

/** The Python source of truth, read rather than imported: there is no runtime that
    can import both, so parity is asserted against the file itself. */
function pythonScript(): Record<string, string[]> {
  const src = readFileSync(join(__dirname, '../../../makanlah/companion.py'), 'utf8')
  const block = src.slice(src.indexOf('SCRIPT: dict'), src.indexOf('SYSTEM = """'))
  const out: Record<string, string[]> = {}
  let key: string | null = null
  for (const raw of block.split('\n')) {
    const head = raw.match(/^\s{4}'([a-z]+)':\s*\($/)
    if (head?.[1]) {
      key = head[1]
      out[key] = []
      continue
    }
    const line = raw.match(/^\s{8}'(.*)',$/)
    if (line?.[1] != null && key) out[key]?.push(line[1].replace(/\\'/g, "'"))
  }
  return out
}

describe('the companion script', () => {
  it('says exactly what the server says', () => {
    // Two copies of the same lines, in two languages, because the client speaks
    // before the server answers. The copy is only safe while it is a copy, so a
    // change to one side is a failing test rather than a silent divergence.
    expect(pythonScript()).toEqual(SCRIPT)
  })

  it('covers every step the wizard walks, plus the send-off', () => {
    for (const step of [...STEP_KEYS, 'done'] as const) {
      expect(SCRIPT[step].length).toBeGreaterThan(0)
    }
  })

  it('speaks only what an English voice can read', () => {
    // A Chinese glyph in an English synthesiser is skipped or spelled out letter by
    // letter. The corpus is trilingual and the excerpts stay in their own script;
    // the spoken lines are the one place that cannot be.
    for (const pool of Object.values(SCRIPT)) {
      for (const line of pool) {
        expect(line).not.toMatch(/[぀-ヿ一-鿿]/)
      }
    }
  })

  it('keeps a spoken line short enough to listen to', () => {
    for (const pool of Object.values(SCRIPT)) {
      for (const line of pool) {
        expect(line.split(' ').length).toBeLessThanOrEqual(18)
      }
    }
  })

  it('gives the same line for the same seed, and a different one for another', () => {
    // Stepping Back to a question already answered must not reword it: three
    // wordings in one wizard reads as three different companions.
    expect(scripted('craving', 2)).toBe(scripted('craving', 2))
    expect(scripted('craving', 0)).not.toBe(scripted('craving', 1))
  })

  it('wraps a seed past the end of the pool', () => {
    expect(scripted('mood', 99)).toBeTruthy()
  })
})

function voice(name: string, lang: string): SpeechSynthesisVoice {
  return { name, lang, default: false, localService: true, voiceURI: name } as SpeechSynthesisVoice
}

describe('choosing a voice', () => {
  it('prefers a named light voice over an unnamed one', () => {
    const got = pickVoice([voice('Daniel', 'en-GB'), voice('Google UK English Female', 'en-GB')])
    expect(got?.name).toBe('Google UK English Female')
  })

  it('prefers Malaysian English over British when both are light', () => {
    const got = pickVoice([voice('Female', 'en-GB'), voice('Female', 'en-MY')])
    expect(got?.lang).toBe('en-MY')
  })

  it('never picks a non-English voice while an English one exists', () => {
    // "makan" and "lah" in a Japanese voice are nonsense sounds.
    const got = pickVoice([voice('Kyoko', 'ja-JP'), voice('Daniel', 'en-GB')])
    expect(got?.name).toBe('Daniel')
  })

  it('still speaks when nothing matches, rather than falling silent', () => {
    expect(pickVoice([voice('Kyoko', 'ja-JP')])?.name).toBe('Kyoko')
  })

  it('has nothing to pick from an empty list', () => {
    expect(pickVoice([])).toBeNull()
  })

  it('is pitched above the platform default', () => {
    // The cute register is these two numbers and nothing else. If a later change
    // flattens them the companion becomes a satnav.
    expect(PITCH).toBeGreaterThan(1)
    expect(RATE).toBeGreaterThan(1)
  })
})
