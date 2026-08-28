import { describe, expect, it } from 'vitest'
import type { Citation, Result } from '../api'
import { basisLine, citable, evidenceOf, leadPair, listBasisLine, moodFor, sharedBasis } from '../evidence'

function c(over: Partial<Citation> = {}): Citation {
  return {
    post_url: 'https://www.rednote.com/explore/a',
    excerpt: '汤头浓郁',
    platform: 'rednote',
    author_handle: null,
    posted_at: null,
    ...over
  }
}

const result = (citations: Citation[]): Result =>
  ({
    venue: { id: 'v', name: 'x', area: null, lat: null, lng: null, maps_url: '', dishes: [] },
    why: '',
    distance_m: null,
    citations
  }) as Result

describe('citable', () => {
  it('drops a citation with no post behind it', () => {
    expect(citable([c(), c({ post_url: '' })])).toHaveLength(1)
  })
})

describe('evidenceOf', () => {
  it('calls two platforms corroborated', () => {
    expect(evidenceOf(result([c(), c({ platform: 'google_maps', post_url: 'https://maps/1' })]))).toBe('corroborated')
  })

  it('does not call two posts on one platform corroborated', () => {
    // One person saying it twice, or one platform's algorithm surfacing the same
    // opinion twice, is not two sources agreeing.
    expect(evidenceOf(result([c(), c({ post_url: 'https://www.rednote.com/explore/b' })]))).toBe('single')
  })

  it('reports none when nothing is citable', () => {
    expect(evidenceOf(result([c({ post_url: '' })]))).toBe('none')
  })
})

describe('leadPair', () => {
  it('prefers a citation that actually carries text', () => {
    // Distinct URLs, because two posts at one URL are the same post and citable()
    // now collapses them.
    const pair = leadPair([c({ excerpt: null }), c({ post_url: 'https://rednote/b', excerpt: '有汤' })])
    expect(pair[0]?.excerpt).toBe('有汤')
  })

  it('never returns two from the same platform', () => {
    const pair = leadPair([c(), c({ post_url: 'https://www.rednote.com/explore/b', excerpt: '也好' })])
    expect(pair).toHaveLength(1)
  })

  it('returns the corroborating platform second', () => {
    const pair = leadPair([c(), c({ platform: 'google_maps', post_url: 'https://maps/1', excerpt: 'Good' })])
    expect(pair.map((p) => p.platform)).toEqual(['rednote', 'google_maps'])
  })
})

describe('moodFor', () => {
  it('is curious while nothing has been asked yet', () => {
    expect(moodFor(null)).toBe('curious')
  })

  it('is pleased only when two platforms agree', () => {
    expect(moodFor('corroborated')).toBe('pleased')
    expect(moodFor('single')).toBe('skeptical')
    expect(moodFor('none')).toBe('concerned')
  })

  it('lets degraded outrank everything, so a stale corpus never reads as pleased', () => {
    // A face that smiles at evidence it cannot vouch for is decoration. Issue #11.
    expect(moodFor('corroborated', true)).toBe('concerned')
  })
})

describe('basisLine', () => {
  it('admits when nothing the user typed appears in the post', () => {
    expect(basisLine('semantic')).toMatch(/no exact match/i)
  })

  it('says nothing when the API reports no basis', () => {
    expect(basisLine(undefined)).toBeNull()
  })
})

describe('sharedBasis', () => {
  it('finds the basis when every entry agrees', () => {
    expect(sharedBasis([{ match: { basis: 'semantic' } }, { match: { basis: 'semantic' } }])).toBe('semantic')
  })

  it('is undefined when they differ, so each row says its own', () => {
    expect(sharedBasis([{ match: { basis: 'dish' } }, { match: { basis: 'semantic' } }])).toBeUndefined()
  })

  it('is undefined when the API reports no basis at all', () => {
    expect(sharedBasis([{}, {}])).toBeUndefined()
  })

  it('still admits the whole list is a semantic match', () => {
    // The honest caveat has to survive being hoisted, or hoisting it lost the point.
    expect(listBasisLine('semantic')).toMatch(/none of these match your words exactly/i)
  })
})

describe('duplicate citations', () => {
  it('counts the same post once, however many times the corpus carries it', () => {
    // Two rows for one post is not two pieces of evidence. Inflating the count is the
    // one arithmetic error this product cannot afford.
    expect(citable([c(), c()])).toHaveLength(1)
  })

  it('does not let a duplicate masquerade as corroboration', () => {
    expect(evidenceOf(result([c(), c()]))).toBe('single')
  })

  it('still pairs two genuinely different posts', () => {
    const two = [c(), c({ post_url: 'https://maps/1', platform: 'google_maps', excerpt: 'Good' })]
    expect(citable(two)).toHaveLength(2)
    expect(leadPair(two)).toHaveLength(2)
  })
})
