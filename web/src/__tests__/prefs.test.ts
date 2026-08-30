import { beforeEach, describe, expect, it } from 'vitest'
import { loadPrefs, queryFrom, savePrefs, summarise } from '../prefs'
import { BUDGET, cravingOptions } from '../taste/options'

beforeEach(() => localStorage.clear())

describe('loadPrefs', () => {
  it('is null before the wizard has ever been finished', () => {
    // /discover routes to /taste on this, so a false positive here would drop a first
    // time visitor into an empty results page.
    expect(loadPrefs()).toBeNull()
  })

  it('rejects a stored value of the wrong shape rather than spreading it', () => {
    // Anything that has been through localStorage is untrusted input.
    localStorage.setItem('makanlah.prefs', JSON.stringify({ craving: 'nasi lemak' }))
    expect(loadPrefs()).toBeNull()
  })

  it('rejects json that is not an object', () => {
    localStorage.setItem('makanlah.prefs', '"nope"')
    expect(loadPrefs()).toBeNull()
  })

  it('survives a round trip', () => {
    savePrefs({ craving: ['肉骨茶 bak kut teh'], company: 'family', range_m: 3000, mood: 'comfort' })
    expect(loadPrefs()?.craving).toEqual(['肉骨茶 bak kut teh'])
  })
})

describe('queryFrom', () => {
  it('keeps what the user typed verbatim', () => {
    expect(queryFrom({ craving: ['something soupy, not too far'] })).toBe('something soupy, not too far')
  })
})

describe('summarise', () => {
  it('distinguishes all of KL from an unanswered range', () => {
    expect(summarise({ craving: [], range_m: 0 })).toContainEqual({ term: 'Within', value: 'All of KL' })
    expect(summarise({ craving: [] }).some((r) => r.term === 'Within')).toBe(false)
  })
})

describe('cravingOptions', () => {
  it('is deterministic for a given hour', () => {
    const at = (h: number) => cravingOptions(new Date(2026, 7, 28, h, 0, 0))
    expect(at(8)).toEqual(at(8))
  })

  it('offers breakfast in the morning and supper late', () => {
    // The clock is real information: nobody wants bak kut teh at 08:00, and offering
    // it wastes the one screen where the app gets to be useful.
    const morning = cravingOptions(new Date(2026, 7, 28, 8, 0, 0)).map((o) => o.label)
    const late = cravingOptions(new Date(2026, 7, 28, 23, 0, 0)).map((o) => o.label)
    expect(morning.join(' ')).toMatch(/Roti Canai/)
    expect(late.join(' ')).not.toEqual(morning.join(' '))
  })

  it('always offers three concrete options', () => {
    for (const h of [0, 6, 12, 18, 21, 23]) {
      expect(cravingOptions(new Date(2026, 7, 28, h, 0, 0))).toHaveLength(3)
    }
  })

  it('carries more than one script, at every hour', () => {
    // Handle all three of EN, MS and ZH or handle none. A craving list that is only
    // English biases the whole session toward English posts.
    for (const h of [8, 13, 19, 23]) {
      const labels = cravingOptions(new Date(2026, 7, 28, h, 0, 0))
        .map((o) => o.label)
        .join(' ')
      expect(labels).toMatch(/[一-鿿]/)
    }
  })
})

describe('budget options', () => {
  it('offers an explicit no preference rather than click to deselect', () => {
    // A radio you clear by clicking it twice is neither discoverable nor keyboard
    // reachable.
    expect(BUDGET.map((b) => b.value)).toContain('any')
  })
})

describe('summarise refuses to recite an answer it cannot name', () => {
  it('drops a value the label table does not know', () => {
    // `isPrefs` checks these are strings, not that they are KNOWN strings, so an
    // older build's vocabulary or a hand-edited localStorage key reaches here. It
    // rendered as "Answered: 肉骨茶, Family, 3 km, ." -- a separator with nothing
    // behind it. Found by looking at the dashboard card, not by a test.
    const rows = summarise({ craving: ['肉骨茶'], mood: 'familiar' as never, range_m: 3000 })
    expect(rows.map((r) => r.term)).toEqual(['Craving', 'Within'])
    expect(rows.every((r) => Boolean(r.value))).toBe(true)
  })

  it('keeps the ones it does know', () => {
    const rows = summarise({ craving: [], mood: 'comfort', company: 'family', budget: 'cheap' })
    expect(rows.map((r) => r.value)).toEqual(['Family', 'Something familiar', 'Cheap'])
  })
})
