import { describe, expect, it } from 'vitest'
import { evidenceOf } from '../evidence'
import { MIXED_SCRIPT, SPECIMEN } from '../routes/landingSpecimen'

const CJK = /[一-鿿]/
const LATIN = /[A-Za-z]{3,}/

describe('the landing page exhibits', () => {
  it('does not print the same post twice', () => {
    // #27 reordered citations by what the excerpt says rather than extractor
    // confidence, which promoted MIXED_SCRIPT's post to SPECIMEN's lead. The page
    // then showed one excerpt in both places whose job is to show varied evidence.
    const specimenPosts = SPECIMEN.citations.map((c) => c.post_url)
    expect(specimenPosts).not.toContain(MIXED_SCRIPT.post_url)
  })

  it('corroborates, because the hero claims a two-platform pair', () => {
    expect(evidenceOf(SPECIMEN)).toBe('corroborated')
  })

  it('cites a real post behind every excerpt', () => {
    // Non-negotiable 4. A frozen exhibit is still a result.
    for (const c of [...SPECIMEN.citations, MIXED_SCRIPT]) {
      expect(c.post_url).toMatch(/^https:\/\//)
      // Not a formality: Citation.excerpt is nullable, and a citation with nothing
      // quoted is a link, not evidence.
      expect(c.excerpt).not.toBeNull()
      expect((c.excerpt ?? '').trim().length).toBeGreaterThan(0)
    }
  })

  it('republishes nobody: handles are dropped, platform and date are kept', () => {
    for (const c of [...SPECIMEN.citations, MIXED_SCRIPT]) {
      expect(c.author_handle).toBeNull()
      expect(c.platform).toBeTruthy()
    }
  })

  it('carries all three languages, which is the claim the page makes', () => {
    expect(SPECIMEN.why).toMatch(/\b(nasi|sambal|sedap|beraroma)\b/i)
    expect(SPECIMEN.citations.some((c) => CJK.test(c.excerpt ?? ''))).toBe(true)
    expect(SPECIMEN.citations.some((c) => LATIN.test(c.excerpt ?? '') && !CJK.test(c.excerpt ?? ''))).toBe(true)
    // The language section's own exhibit has to mix scripts inside one excerpt --
    // two monolingual excerpts side by side would not show the phenomenon.
    const mixed = MIXED_SCRIPT.excerpt ?? ''
    expect(CJK.test(mixed) && LATIN.test(mixed)).toBe(true)
  })
})
