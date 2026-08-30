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
  openable,
  sharedBasis,
  sharedPostCount
} from '../evidence'
import bkt from './fixtures/bkt-citations.json'

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

  // Measured on prod: 阿喜 and 三美肉骨茶 both lead with a live Google Maps citation
  // and carry nothing but DEAD RedNote ones. The server's prefer_live puts the live
  // citation first, so the LEAD was right on 5 of 5 -- and the second chip, chosen
  // only for being a different platform, linked to a post that no longer exists on
  // 3 of 5 cards.
  it('does not corroborate with a post that no longer exists', () => {
    const pair = leadPair([
      c({ platform: 'google_maps', post_url: 'https://maps/1', excerpt: 'Good' }),
      c({ post_url: 'https://rednote/dead', excerpt: '好吃', dead: true })
    ])
    expect(pair).toHaveLength(1)
    expect(pair[0]?.platform).toBe('google_maps')
  })

  it('reaches past a dead post to a live one on the same platform', () => {
    const pair = leadPair([
      c({ platform: 'google_maps', post_url: 'https://maps/1', excerpt: 'Good' }),
      c({ post_url: 'https://rednote/dead', excerpt: '好吃', dead: true }),
      c({ post_url: 'https://rednote/live', excerpt: '也好吃' })
    ])
    expect(pair.map((x) => x.post_url)).toEqual(['https://maps/1', 'https://rednote/live'])
  })

  it('treats an unchecked post as live rather than as dead', () => {
    // `dead: null` is "nobody has probed this yet". Collapsing unknown into dead
    // would delete real evidence from the product -- the 兴记肉骨茶 citation was
    // exactly that case and re-probing resolved it live.
    const pair = leadPair([
      c({ platform: 'google_maps', post_url: 'https://maps/1', excerpt: 'Good' }),
      c({ post_url: 'https://rednote/unknown', excerpt: '好吃', dead: null })
    ])
    expect(pair).toHaveLength(2)
  })

  it('still shows a dead lead when it is the only thing there is', () => {
    // with_live_citations drops an entry whose every citation is dead, so this
    // should not arrive. If it does, one dead citation beats rendering nothing at
    // all: the invariant is that a card always shows where it came from.
    const pair = leadPair([c({ post_url: 'https://rednote/dead', excerpt: '好吃', dead: true })])
    expect(pair).toHaveLength(1)
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
    expect(basisLine('semantic')).toMatch(/no post here uses your words/i)
  })

  it('calls the semantic lane weaker than a named dish, because it measurably is', () => {
    // Not decoration. #140: `canonical_for_query` resolves only curated dish names,
    // so all 14 common ingredient words fall through to this lane -- the one with
    // near-zero citation support against 12/12 on dish matches. A reader shown a
    // chicken rice shop for `crab` is entitled to know which lane produced it.
    expect(basisLine('semantic')).toMatch(/weaker/i)
    expect(basisLine('dish')).toMatch(/strongest/i)
  })

  it('never repeats the subtitle it sits under', () => {
    // The disclosure exists to ADD to the fact row. `whyRow` leads a semantic card
    // with "Close in meaning", and an expander restating that phrase rebuilds the
    // buried-footnote problem inside the fix for it -- which it did, and the row
    // rendered the phrase twice until this caught it.
    expect(basisLine('semantic')).not.toMatch(/close in meaning/i)
    expect(basisLine('dish')).not.toMatch(/^names /i)
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

  it('counts an anonymous Maps reviewer as a second voice', () => {
    // THE INVERSION. Google Maps citations carry author_handle: null, so
    // `authors >= 2` alone withheld the stamp from every venue backed by a RedNote
    // post AND a Maps review -- while stamping RedNote-only venues, and while the
    // companion beside it said "two platforms, written by different people".
    const crossPlatform = venue({ corroboration: { posts: 2, authors: 1, platforms: 2 } })
    expect(
      independentlyBacked(result([cite('https://a', 'rednote'), cite('https://b', 'google_maps')], crossPlatform))
    ).toBe(true)
  })

  it('still refuses a single post however many platforms carry it', () => {
    // #87's actual shape: one listicle backing several venues gives each of them
    // one post, and one post is never corroboration.
    const onePost = venue({ corroboration: { posts: 1, authors: 1, platforms: 2 } })
    expect(independentlyBacked(result([cite('https://a', 'rednote'), cite('https://a', 'google_maps')], onePost))).toBe(
      false
    )
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

/**
 * The real shape, from `POST /recommend {"query": "肉骨茶"}` against prod: five
 * venues, sixteen citations, seven of them measured dead. Post URLs are replaced
 * with synthetic ones and excerpts with a placeholder, because scraped content does
 * not go in the repository -- what is preserved is the structure under test, which
 * is the platform of each citation, its order, and its `dead` value.
 *
 * This is here because the unit tests above are cases I chose. Three of these five
 * cards rendered a dead chip on production while every one of those unit tests
 * would have passed, since the shape that breaks it -- a live lead on one platform
 * and nothing but dead citations on the other -- is one I did not think to write
 * until it was measured in the wild.
 */
describe('leadPair against the shape prod actually returns', () => {
  const rows = bkt as { rank: number; citations: Citation[] }[]

  it('has dead citations in the fixture at all', () => {
    // Without this the suite below passes trivially on a fixture somebody cleaned.
    expect(rows.flatMap((r) => r.citations).filter((c) => c.dead === true).length).toBe(7)
  })

  it('never hands the reader a post that no longer exists', () => {
    for (const row of rows) {
      for (const cite of leadPair(row.citations)) {
        expect(cite.dead, `rank ${row.rank} -> ${cite.post_url}`).not.toBe(true)
      }
    }
  })

  /**
   * The check Peer 1 asked for by name, and the reason it is shaped this way: a
   * check that re-runs `evidenceOf` to confirm `evidenceOf` agrees with itself and
   * proves nothing. This asserts two INDEPENDENT functions reach the same verdict
   * over real data -- the claim the companion makes, against the testimony the card
   * can actually render.
   */
  it('never claims corroboration the card cannot show', () => {
    for (const row of rows) {
      const claimed = evidenceOf({ citations: row.citations } as Result) === 'corroborated'
      const shown = leadPair(row.citations).length > 1
      expect(claimed, `rank ${row.rank}: evidenceOf said corroborated, leadPair rendered one`).toBe(shown)
    }
  })

  it('has a row where the two used to disagree', () => {
    // Without this the agreement test above passes on a fixture where nothing was
    // ever at stake. Ranks 4 and 5 are the real 阿喜 and 三美 shape: a live Google
    // Maps citation plus RedNote citations that are all dead, which is two
    // platforms by the old count and one openable post in fact.
    const twoPlatformsIfDeadCounts = rows.filter((r) => new Set(citable(r.citations).map((c) => c.platform)).size > 1)
    const oneOpenablePlatform = twoPlatformsIfDeadCounts.filter(
      (r) => new Set(openable(r.citations).map((c) => c.platform)).size === 1
    )
    expect(oneOpenablePlatform.length).toBeGreaterThan(0)
  })

  it('still cites every card', () => {
    // Dropping a dead chip must never drop the last chip. A card with no citation
    // is not a result, and this is the invariant the fix could have broken.
    for (const row of rows) {
      expect(leadPair(row.citations).length, `rank ${row.rank}`).toBeGreaterThan(0)
    }
  })
})
