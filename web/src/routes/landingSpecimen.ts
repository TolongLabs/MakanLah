import type { Citation, Result } from '../api'

/**
 * One real pick, frozen so the landing page renders it on first paint instead of
 * waiting on a re-rank the visitor did not ask for. Every field below came back from
 * `POST /recommend` for the query "nasi lemak sedap", captured 2026-08-29.
 *
 * One deliberate edit, subtractive: author handles are dropped to null, matching how
 * docs/source/ redacts them. The chip then names the platform and the date, which
 * attributes the post without republishing a person's account name on a marketing
 * page. The Google Maps excerpt needed a second edit when this was first frozen -- it
 * carried the platform's own "... More" truncation marker -- and no longer does,
 * because #40 and #42 strip scrape chrome in the pipeline where it belongs.
 *
 * RE-FREEZE THIS WHEN THE CORPUS MOVES, and do not assume a live URL means a live
 * exhibit. Both posts here survived the #42 repair untouched, yet the response still
 * went stale twice over: the RedNote excerpt lost a "1.Village Park 椰浆饭" label that
 * was never the writer's words, and #27 changed citation ordering from extractor
 * confidence to what the excerpt actually says, which moved the lead. A frozen
 * response the API no longer produces is the same problem as a citation that no longer
 * resolves -- the page claims an evidence trail nobody can walk.
 *
 * It is also the clearest thing the corpus has said. The claim comes back in Malay
 * because the query was Malay, one writer answers in Chinese and one in English, and
 * all three sit in a single row. That is the product in one exhibit.
 */
export const SPECIMEN: Result = {
  venue: {
    id: 'cbf2a04f-3193-4379-875c-34b66e012523',
    name: 'Village Park',
    area: null,
    lat: 3.1376947,
    lng: 101.6233261,
    maps_url:
      'https://www.google.com/maps/search/?api=1&query=Village%20Park%20%20Kuala%20Lumpur&query_place_id=0x31cc4931330bf621:0x21aac39e1d6f6f3c',
    dishes: ['nasi lemak', '炸鸡', 'sambal', '椰浆炸鸡饭', '酸梅刺梨汁', '薏米水']
  },
  rank: 1,
  match: { basis: 'semantic', dish: null, similarity: 0.5861 },
  why: 'Nasi lemak terkenal, nasi beraroma kelapa dan sambal sedap.',
  distance_m: null,
  citations: [
    {
      post_url: 'https://www.rednote.com/explore/6941419f000000000d03fe99',
      excerpt: '2️⃣ Village Park Nasi Lemak\n排队也值得！椰香米饭搭配香脆炸鸡和微辣sambal，早午晚都适合吃！',
      platform: 'rednote',
      author_handle: null,
      posted_at: 'Edited at 12/26/2025'
    },
    {
      post_url: 'https://www.google.com/maps/search/?api=1&query=Village%20Park%20Nasi%20Lemak%20Kuala%20Lumpur',
      excerpt:
        'This is definitely one of the most famous restaurants in Malaysia, as a lot of foreigners keep posting about their experience here on social media.',
      platform: 'google_maps',
      author_handle: null,
      posted_at: '3 months ago'
    },
    {
      post_url: 'https://www.rednote.com/explore/6915e7320000000005033723',
      excerpt:
        '冲就完了，懒得多说，就是好吃爆炸了，而且是其他家的椰浆饭都打不过的程度！我一个不爱椰子制品和叁巴酱/虾酱的人都爱疯。这家店的酸梅刺梨汁和薏米水也很好喝。',
      platform: 'rednote',
      author_handle: null,
      posted_at: '11/13/2025'
    }
  ]
}

/**
 * A second real capture, used by the landing page's language section. Same treatment
 * as SPECIMEN: verbatim, handle dropped to null, platform and date kept. From
 * `GET /venue/aa16ddc2-1412-49c8-879c-8417d0eaa913`, captured 2026-08-29.
 *
 * A different venue on purpose. It used to be another Village Park post, and #27's
 * reordering promoted that exact post to SPECIMEN's lead citation -- so the page would
 * have printed one excerpt twice, in the two places whose whole job is to show that
 * the evidence is varied. Any replacement here has to come from a venue SPECIMEN does
 * not already cite.
 *
 * This one carries all three languages in two lines: a Malay dish, an English
 * preposition and price, and a Chinese verdict that is not pure praise. The mild
 * complaint is the reason it was chosen over louder candidates -- a corpus that only
 * ever agrees is not evidence, it is marketing.
 */
export const MIXED_SCRIPT: Citation = {
  post_url: 'https://www.rednote.com/explore/69d38715000000001a028456',
  excerpt: 'Lemang Bakar with Chicken Redang -RM35\n米饭真的很香 但是觉得这个分量和价格就稍微有点贵了',
  platform: 'rednote',
  author_handle: null,
  posted_at: 'Apr 6'
}
