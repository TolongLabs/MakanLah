import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const recommend = vi.fn()
const suggestions = vi.fn()

vi.mock('../api', async () => {
  const real = await vi.importActual<typeof import('../api')>('../api')
  return { ...real, recommend: (...a: unknown[]) => recommend(...a), suggestions: () => suggestions() }
})

// The Live2D chunk is 500 KB of pixi behind a lazy import and never resolves in
// jsdom. The panel is not what these assertions are about -- but the PROPS it is
// handed are, so the stub records them.
const companionProps: Record<string, unknown>[] = []
vi.mock('../components/AskCompanion', () => ({
  AskCompanion: (p: Record<string, unknown>) => {
    companionProps.push(p)
    return null
  }
}))

import { Discover } from '../routes/Discover'

const empty = { results: [], degraded: false, sources_used: [] }

function show(state: Record<string, unknown>) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/discover', state }]}>
      <Discover />
    </MemoryRouter>
  )
}

beforeEach(() => {
  localStorage.clear()
  companionProps.length = 0
  recommend.mockReset().mockResolvedValue(empty)
  suggestions.mockReset().mockResolvedValue({ chips: [], band: 'lunch', source: 'corpus' })
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('the empty state tells the truth about why', () => {
  it('blames the distance when a distance was actually applied', async () => {
    // Peer 3 at her Klang office on 3 km was told "nothing in the corpus matches
    // nasi lemak yet" -- and Search All Of KL right after returned ten picks. The
    // corpus was never the reason.
    show({ prefs: { craving: ['nasi lemak'], range_m: 3000 }, geo: { lat: 3.04, lng: 101.44 } })
    const box = await screen.findByText(/Nothing for/i)
    expect(box.textContent).toMatch(/within 3 km of you/i)
    expect(screen.getByRole('button', { name: /Search All Of KL/i })).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/Nothing in the corpus/i)
  })

  it('never claims a radius when geolocation never resolved', async () => {
    // radius is selected but run() drops it without a fix, so the search was
    // KL-wide. Saying "within 3 km of you" would be the same lie in reverse.
    show({ prefs: { craving: ['nasi lemak'], range_m: 3000 }, geoRefused: true })
    await screen.findByText(/Nobody has written about/i)
    expect(document.body.textContent).not.toMatch(/km of you/i)
  })

  it('does not point at suggestions that are not on screen', async () => {
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await screen.findByText(/Nobody has written about/i)
    expect(document.body.textContent).not.toMatch(/suggestions above/i)
  })

  it('points at the suggestions when there are some', async () => {
    suggestions.mockResolvedValue({
      chips: [{ label: '肉骨茶', query: '肉骨茶', posts: 14, venues: 9 }],
      band: 'lunch',
      source: 'model'
    })
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await waitFor(() => expect(document.body.textContent).toMatch(/suggestions above/i))
  })
})

describe('the craving can be dropped', () => {
  it('stops sending it and stops advertising it', async () => {
    show({ prefs: { craving: ['nasi lemak bumbung supper'], company: 'solo', range_m: 0 } })
    const drop = await screen.findByRole('button', { name: /Drop The Craving/i })
    expect(document.body.textContent).toMatch(/nasi lemak bumbung supper/i)

    drop.click()
    await waitFor(() => expect(document.body.textContent).not.toMatch(/nasi lemak bumbung supper/i))

    // The claim and the request have to agree: it must be gone from BOTH.
    const last = recommend.mock.calls.at(-1)?.[0] as { prefs?: { craving?: string[] } }
    expect(last?.prefs?.craving).toEqual([])
  })
})

describe('the search field', () => {
  it('is empty on arrival', async () => {
    // It used to be prefilled from the wizard, so it had to be cleared before it
    // could be used, and it made the answers look like a query the user typed.
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await waitFor(() => expect(recommend).toHaveBeenCalled())
    expect((screen.getByLabelText(/hungry for/i) as HTMLInputElement).value).toBe('')
  })

  it('still runs the wizard answers as the first search', async () => {
    show({ prefs: { craving: ['肉骨茶'], range_m: 0 } })
    await waitFor(() => expect(recommend).toHaveBeenCalled())
    const first = recommend.mock.calls[0]?.[0] as { query: string } | undefined
    expect(first?.query).toBe('肉骨茶')
  })
})

/**
 * #98, the half that is decidable without a model.
 *
 * Measured on prod: `roti canai` returned Mon Beef Roti, RAYs @ B.LAND, Potato
 * Corner, kaiia kanteen and Menya Aburi. The lane had resolved the dish and found
 * exactly the two venues carrying it, Devi's Corner and Kapitan; both were dropped
 * because each has a single RedNote citation and both are dead.
 *
 * The design question this settles is whether to name the venues or count them.
 * Naming: the two claims are not equally checkable — that a post said something is
 * unverifiable once the post is gone, while the restaurant's existence is checkable
 * in ten seconds from its place_id. A bare number is no more provable and gives a
 * hungry person nothing.
 */
const GAP = {
  results: [],
  degraded: false,
  sources_used: [],
  evidence_gap: {
    term: 'roti canai',
    total: 2,
    venues: [
      { name: 'Devi’s Corner', area: 'PJ', maps_url: 'https://maps/?query_place_id=p1' },
      { name: 'Kapitan', area: 'Bangsar', maps_url: 'https://maps/?query_place_id=p2' }
    ]
  }
}

describe('when the corpus knows the dish and cannot show the writing', () => {
  beforeEach(() => {
    recommend.mockReset().mockResolvedValue(GAP)
  })

  it('names the venues rather than counting them', async () => {
    show({ prefs: { craving: ['roti canai'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText('Devi’s Corner')).toBeTruthy())
    expect(screen.getByText('Kapitan')).toBeTruthy()
  })

  it('hands over a link the reader can check the restaurant with', async () => {
    // The justification for naming at all. If the link were a name search rather
    // than the exact place, the user could not confirm the venue either, and then
    // counting would have been the honest choice.
    show({ prefs: { craving: ['roti canai'], range_m: 0 } })
    const link = await screen.findByRole('link', { name: 'Devi’s Corner' })
    expect(link.getAttribute('href')).toContain('query_place_id=')
  })

  it('says plainly that it cannot show the writing', async () => {
    show({ prefs: { craving: ['roti canai'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText(/cannot show you what people wrote/i)).toBeTruthy())
    expect(screen.getByText(/no longer open/i)).toBeTruthy()
  })

  it('says these are not picks', async () => {
    // The failure mode is this reading as a third confident register beside
    // "naming that dish" and "closest in meaning". It has to disclaim itself.
    show({ prefs: { craving: ['roti canai'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText(/these are not picks/i)).toBeTruthy())
  })

  it('does not also show the generic empty state guessing a different reason', async () => {
    // #82 all over again if both render: two explanations, one of them invented.
    show({ prefs: { craving: ['roti canai'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText(/cannot show you what people wrote/i)).toBeTruthy())
    expect(screen.queryByText(/anywhere in the corpus/i)).toBeNull()
    expect(screen.queryByText(/Search All Of KL/i)).toBeNull()
  })

  it('leaves the ordinary empty state alone when there is no gap', async () => {
    recommend.mockReset().mockResolvedValue(empty)
    show({ prefs: { craving: ['poutine'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText(/anywhere in the corpus/i)).toBeTruthy())
    expect(screen.queryByText(/cannot show you what people wrote/i)).toBeNull()
  })
})

/**
 * The companion and the page must not contradict each other.
 *
 * Measured on prod: the gap screen showed `Filtered by your answers: nasi lemak
 * 椰浆饭, On my own, All of KL, Something familiar` with the companion directly
 * beneath it reading `Answer the four questions and this fills in.` Two elements
 * on one screen, and the companion's was the false one — the `curious` mood
 * collapsed "nothing searched yet" into "searched and found nothing".
 *
 * Asserted as AGREEMENT between the two elements rather than against the string
 * the fix chose, because a check that only reads the new copy passes the moment
 * somebody changes the copy back.
 */
describe('the companion and the page agree about what has happened', () => {
  const phase = () => companionProps[companionProps.length - 1]?.phase

  it('does not ask for answers the page is already reciting', async () => {
    recommend.mockReset().mockResolvedValue(empty)
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    // The page's own claim that the questions were answered.
    await waitFor(() => expect(screen.getByText(/Filtered by your answers/i)).toBeTruthy())
    // `phase` and not `phase()` in the first draft: a function reference is never
    // equal to 'idle', so the assertion could not fail. Caught by mutating the
    // component to always pass 'idle' and watching this test stay green -- which
    // is why the mutation run happens before the commit and not after it.
    expect(phase(), 'the page recites the answers, so the companion may not ask for them').not.toBe('idle')
  })

  it('reports picks when there are picks', async () => {
    recommend.mockReset().mockResolvedValue({
      results: [
        {
          venue: { id: 'v1', name: 'Village Park', area: null, lat: null, lng: null, maps_url: '', dishes: [] },
          rank: 1,
          why: '',
          distance_m: null,
          citations: [
            {
              post_url: 'https://rednote/a',
              excerpt: 'sedap',
              platform: 'rednote',
              author_handle: null,
              posted_at: null
            }
          ]
        }
      ],
      degraded: false,
      sources_used: ['rednote']
    })
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText('Village Park')).toBeTruthy())
    expect(phase()).toBe('picks')
  })

  it('reports empty on the evidence-gap screen, where there is nothing to tap Ask on', async () => {
    recommend.mockReset().mockResolvedValue(GAP)
    show({ prefs: { craving: ['roti canai'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText('Kapitan')).toBeTruthy())
    expect(phase()).toBe('empty')
  })
})

/**
 * The list-level half. `coverage_gaps` names what the corpus cannot answer at
 * all, which is a different sentence from how well the matching went — and the
 * Malay persona only ever saw the second one.
 */
const HALAL = {
  results: [
    {
      venue: {
        id: 'v1',
        name: 'Hock Kee Heritage',
        area: null,
        lat: null,
        lng: null,
        maps_url: '',
        dishes: [],
        gap_mentions: ['halal']
      },
      rank: 1,
      why: '',
      distance_m: null,
      match: { basis: 'semantic', dish: null, similarity: 0.5 },
      citations: [
        {
          post_url: 'https://maps/1',
          excerpt: '清真友好',
          platform: 'google_maps',
          author_handle: null,
          posted_at: null
        }
      ]
    },
    {
      venue: { id: 'v2', name: '鱼你', area: null, lat: null, lng: null, maps_url: '', dishes: [], gap_mentions: [] },
      rank: 2,
      why: '',
      distance_m: null,
      match: { basis: 'semantic', dish: null, similarity: 0.5 },
      citations: [
        { post_url: 'https://rednote/2', excerpt: '好吃', platform: 'rednote', author_handle: 'a', posted_at: null }
      ]
    }
  ],
  degraded: false,
  sources_used: ['google_maps', 'rednote'],
  coverage_gaps: ['halal']
}

describe('the page says what the corpus cannot answer', () => {
  it('states the coverage gap, not just the match quality', async () => {
    recommend.mockReset().mockResolvedValue(HALAL)
    show({ prefs: { craving: ['halal'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText(/We hold no halal information/i)).toBeTruthy())
  })

  it('does not let the relevance line stand in for it', async () => {
    // The exact substitution UAT found: a relevance disclaimer answering a
    // question she did not ask, while the page stayed silent on the one she did.
    recommend.mockReset().mockResolvedValue(HALAL)
    show({ prefs: { craving: ['halal'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText(/We hold no halal information/i)).toBeTruthy())
    const body = document.body.textContent ?? ''
    const relevanceOnly = /match your words exactly|close in meaning/i.test(body)
    expect(relevanceOnly && !/We hold no halal information/i.test(body)).toBe(false)
  })

  it('says nothing about coverage when the query raised no gap', async () => {
    recommend.mockReset().mockResolvedValue({ ...HALAL, coverage_gaps: [] })
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await waitFor(() => expect(screen.getByText('Hock Kee Heritage')).toBeTruthy())
    expect(screen.queryByText(/We hold no halal information/i)).toBeNull()
  })
})

/**
 * The wizard was unreachable from inside the app.
 *
 * Its only route from /discover was an inline "Change" link inside a sentence
 * that rendered only once you already had answers — so somebody arriving without
 * them, or not reading that paragraph, had no way to the companion at all. The
 * owner could not find it.
 */
describe('the wizard is reachable from the results page', () => {
  it('offers a route to it even with nothing to summarise', async () => {
    // Not `range_m: 0` -- that summarises to "All of KL", so the page does have an
    // answer to recite and the label is correctly the redo one. The empty case is
    // prefs that exist and say nothing.
    recommend.mockReset().mockResolvedValue(empty)
    show({ prefs: { craving: [] } })
    await waitFor(() => expect(screen.getByRole('link', { name: /Answer Four Questions/i })).toBeTruthy())
    expect(screen.getByRole('link', { name: /Answer Four Questions/i }).getAttribute('href')).toBe('/taste')
  })

  it('names it for what it does once there are answers to redo', async () => {
    recommend.mockReset().mockResolvedValue(empty)
    show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    await waitFor(() => expect(screen.getByRole('link', { name: /Redo My Taste/i })).toBeTruthy())
    expect(screen.getByRole('link', { name: /Redo My Taste/i }).getAttribute('href')).toBe('/taste')
  })

  it('is a control on the filter row, not a word inside a paragraph', () => {
    // The reason the old one could not be found. Asserting the ROLE and the class
    // rather than the text, because "there is a link whose href is /taste" was
    // true before this change too.
    recommend.mockReset().mockResolvedValue(empty)
    const { container } = show({ prefs: { craving: ['nasi lemak'], range_m: 0 } })
    expect(container.querySelector('.find-filters .find-taste')).toBeTruthy()
  })
})

describe('the gap surface tells the two evidence classes apart', () => {
  // #144's park note: `85b9220` added the per-entry flag and the client did not
  // read it, so every entry was named identically and none offered evidence. Both
  // classes are real -- `roti canai` on prod returns Devi's Corner at
  // `live_citations: 0`, and the flag is what separates "nobody's surviving post
  // describes this" from "we have posts and this is simply too far".
  const twoClasses = {
    results: [],
    degraded: false,
    sources_used: [],
    distance_gap: {
      term: 'roti canai',
      nearest: [
        {
          name: 'Nasi Lemak Bumbung',
          area: 'Cheras',
          distance_m: 4200,
          maps_url: 'https://maps.example/1',
          live_citations: 9,
          verifiable: true
        },
        {
          name: 'Devi’s Corner',
          area: '印度区',
          distance_m: 1914,
          maps_url: 'https://maps.example/2',
          live_citations: 0,
          verifiable: false
        }
      ]
    }
  }

  function rowFor(name: string | RegExp) {
    return screen.getByText(name).closest('li')
  }

  it('counts the posts that still open where any of them do', async () => {
    recommend.mockReset().mockResolvedValue(twoClasses)
    show({ prefs: { craving: ['roti canai'], range_m: 800 }, geo: { lat: 3.139, lng: 101.6869 } })
    await screen.findByText(/Nasi Lemak Bumbung/i)
    expect(rowFor(/Nasi Lemak Bumbung/i)?.textContent).toMatch(/9 posts still open/i)
  })

  it('says nothing survives rather than implying evidence it cannot show', async () => {
    recommend.mockReset().mockResolvedValue(twoClasses)
    show({ prefs: { craving: ['roti canai'], range_m: 800 }, geo: { lat: 3.139, lng: 101.6869 } })
    await screen.findByText(/Devi’s Corner/i)
    const row = rowFor(/Devi’s Corner/i)?.textContent ?? ''
    expect(row).toMatch(/no post still opens/i)
    // The specific failure this replaces: a zero rendered as a count.
    expect(row).not.toMatch(/\b0 posts?\b/)
  })

  it('never prints a bare zero when the flag and the count disagree', async () => {
    // Defensive on the ONE combination the payload should never carry. `verifiable`
    // is the flag the copy branches on, so a true flag with no live post must not
    // produce "0 posts still open" -- the count names a property, and the property
    // has to be true of what is rendered.
    recommend.mockReset().mockResolvedValue({
      ...twoClasses,
      distance_gap: {
        term: 'roti canai',
        nearest: [
          {
            name: 'Contradiction Corner',
            area: null,
            distance_m: 900,
            maps_url: 'https://maps.example/3',
            live_citations: 0,
            verifiable: true
          }
        ]
      }
    })
    show({ prefs: { craving: ['roti canai'], range_m: 800 }, geo: { lat: 3.139, lng: 101.6869 } })
    await screen.findByText(/Contradiction Corner/i)
    expect(rowFor(/Contradiction Corner/i)?.textContent).not.toMatch(/\b0 posts?\b/)
  })
})

describe('the filter line names only what actually filtered', () => {
  // #170. The line said "Filtered by your answers" and listed all five while the
  // API was silently discarding three of them -- `prefs` was not a field on
  // `RecommendRequest`, so Pydantic dropped the object. #171 wires them and returns
  // `applied_prefs`, naming only what shaped that response.
  const answered = { craving: ['bak kut teh'], company: 'family', range_m: 0, mood: 'comfort', budget: 'mid' }

  async function line(container: HTMLElement) {
    await screen.findByText(/Filtered by your answers/i)
    return container.querySelector('.find-prefs')?.textContent ?? ''
  }

  it('names nothing the response did not claim', async () => {
    // An API that predates #171 sends no `applied_prefs` at all, and on that build
    // the three genuinely did nothing. Absent and empty mean the same thing here.
    recommend.mockReset().mockResolvedValue(empty)
    const { container } = show({ prefs: answered })
    const text = await line(container)
    expect(text).toMatch(/bak kut teh/)
    expect(text).toMatch(/All of KL/)
    expect(text).not.toMatch(/Family|Something familiar|Mid/)
  })

  it('names the ones the response says applied, and no others', async () => {
    recommend.mockReset().mockResolvedValue({ ...empty, applied_prefs: ['company', 'mood'] })
    const { container } = show({ prefs: answered })
    const text = await line(container)
    expect(text).toMatch(/Family/)
    expect(text).toMatch(/Something familiar/)
    // Budget dropped out because the corpus had no priced candidate for this query.
    expect(text).not.toMatch(/Mid/)
  })

  it('still names craving and distance, which are not in applied_prefs by design', async () => {
    // They are already the query string and radius_m. The API excludes them so one
    // filter is not counted twice, so the client keeps owning those two.
    recommend.mockReset().mockResolvedValue({ ...empty, applied_prefs: [] })
    const { container } = show({ prefs: answered })
    const text = await line(container)
    expect(text).toMatch(/bak kut teh/)
    expect(text).toMatch(/All of KL/)
  })
})
