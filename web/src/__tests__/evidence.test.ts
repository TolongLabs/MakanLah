import { describe, expect, it } from 'vitest'
import type { Citation, Result } from '../api'
import {
  basisLine,
  citable,
  citationHref,
  evidenceOf,
  independentlyBacked,
  leadPair,
  listBasisLine,
  moodFor,
  sharedBasis,
  sharedPostCount
} from '../evidence'

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

describe('what may be called independent', () => {
  const cite = (post: string, platform: string, extra: Partial<Citation> = {}): Citation => ({
    post_url: post,
    excerpt: 'x',
    platform,
    author_handle: null,
    posted_at: null,
    ...extra
  })
  const venue = (extra = {}) => ({
    id: 'v',
    name: 'n',
    area: null,
    lat: null,
    lng: null,
    maps_url: 'https://maps',
    dishes: [],
    ...extra
  })
  const result = (citations: Citation[], v = venue()): Result =>
    ({ venue: v, why: '', distance_m: null, citations }) as unknown as Result

  it('refuses to call one post on two platforms corroborated', () => {
    // The #87 bug. One listicle backed three of the top five picks and every card
    // said "Corroborated by two independent sources". True by the old rule, false
    // as English: one voice is one voice however many platforms carry it.
    const one = 'https://rednote/abc'
    expect(independentlyBacked(result([cite(one, 'rednote'), cite(one, 'google_maps')]))).toBe(false)
  })

  it('accepts two distinct posts on two platforms', () => {
    expect(independentlyBacked(result([cite('https://a', 'rednote'), cite('https://b', 'google_maps')]))).toBe(true)
  })

  it('refuses two distinct posts on one platform, without a server signal', () => {
    // Conservative on purpose: without `corroboration` we cannot tell two authors
    // from one author posting twice, and the stamp is the strongest claim we make.
    expect(independentlyBacked(result([cite('https://a', 'rednote'), cite('https://b', 'rednote')]))).toBe(false)
  })

  it('believes the server signal over the layout when it arrives', () => {
    const two = venue({ corroboration: { posts: 2, authors: 2, platforms: 1 } })
    expect(independentlyBacked(result([cite('https://a', 'rednote'), cite('https://b', 'rednote')], two))).toBe(true)
  })

  it('lets the server signal veto a pair that only looks independent', () => {
    const one = venue({ corroboration: { posts: 1, authors: 1, platforms: 2 } })
    expect(independentlyBacked(result([cite('https://a', 'rednote'), cite('https://b', 'google_maps')], one))).toBe(
      false
    )
  })

  it('counts how many other picks lean on the same post', () => {
    expect(sharedPostCount(cite('https://a', 'rednote', { shared_with: ['v2', 'v3'] }))).toBe(2)
    expect(sharedPostCount(cite('https://a', 'rednote'))).toBe(0)
  })
})

describe('where a citation links', () => {
  const only = (platform: string, url = 'https://post'): Citation => ({
    post_url: url,
    excerpt: null,
    platform,
    author_handle: null,
    posted_at: null
  })

  it('prefers the exact place_id link over a Maps name search', () => {
    // The corpus can only store a name search for a Maps review, and for a name
    // like ALVA that lands on the wrong place. 23 of 23 venues in UAT.
    const exact = 'https://www.google.com/maps/search/?api=1&query=X&query_place_id=0x31cc'
    expect(citationHref(only('google_maps'), { maps_url: exact })).toBe(exact)
  })

  it('keeps the name search when the venue has no place_id either', () => {
    expect(citationHref(only('google_maps'), { maps_url: 'https://www.google.com/maps/search/?api=1&query=X' })).toBe(
      'https://post'
    )
  })

  it('never rewrites a RedNote post URL', () => {
    const exact = 'https://www.google.com/maps/search/?api=1&query=X&query_place_id=0x31cc'
    expect(citationHref(only('rednote'), { maps_url: exact })).toBe('https://post')
  })
})
