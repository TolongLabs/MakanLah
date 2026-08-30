import type { Citation, Result, Venue } from '../../api'

/**
 * One result, shaped like the live API rather than like the type.
 *
 * The defaults are real: the name, the mixed-script excerpt and the dish list are
 * lifted from what `/recommend` actually returns for `bak kut teh`, so a test that
 * passes here is a test against the corpus the product ships with.
 *
 * `venue` MERGES rather than replaces. A test that wants to say "this one has no
 * area" should not have to restate an id, a name, coordinates and a maps URL to do
 * it — and a fixture that makes it restate them is a fixture where the next field
 * added to `Venue` silently goes missing from half the suite.
 */
export function citation(over: Partial<Citation> = {}): Citation {
  return {
    post_url: 'https://www.rednote.com/explore/abc',
    excerpt: '汤底浓郁药材香，肉质软烂入味，配白饭简直绝配！Sedap sangat.',
    platform: 'rednote',
    author_handle: 'author_ab12',
    posted_at: 'Feb 17',
    ...over
  }
}

export function result(over: Partial<Omit<Result, 'venue'>> & { venue?: Partial<Venue> } = {}): Result {
  const { venue, ...rest } = over
  return {
    venue: {
      id: 'v1',
      name: '兴记肉骨茶 Hing Kee Bakuteh',
      area: 'Jalan Ipoh',
      lat: 3.2,
      lng: 101.67,
      maps_url: 'https://www.google.com/maps/search/?api=1&query=x',
      dishes: ['肉骨茶', 'nasi lemak', 'ayam goreng berempah'],
      ...venue
    },
    rank: 1,
    why: 'Rich herbal broth, and the locals keep going back.',
    distance_m: 1200,
    citations: [citation()],
    ...rest
  }
}
