import type { Result } from '../api'

/**
 * One real pick, frozen so the landing page renders it on first paint instead of
 * waiting two seconds on a re-rank the visitor did not ask for. Every field below came
 * back from the live API for the query "nasi lemak sedap" and the excerpts are
 * verbatim substrings of the captured posts.
 *
 * Two deliberate edits, both subtractive. The Google Maps excerpt is cut at a sentence
 * boundary, because the captured text carries the platform's own "… More" truncation
 * marker and that is scrape chrome rather than the writer's words. Author handles are
 * dropped to null, matching how docs/source/ redacts them: the chip then names the
 * platform and the date, which attributes the post without republishing a person's
 * account name on a marketing page.
 *
 * It is also the clearest thing the corpus has said so far. Our claim comes back in
 * Malay because the query was Malay, one writer answers in Chinese and one in English,
 * and all three sit in a single row. That is the product in one exhibit.
 */
export const SPECIMEN: Result = {
  venue: {
    id: 'cbf2a04f-3193-4379-875c-34b66e012523',
    name: 'Village Park',
    area: 'Damansara Utama',
    lat: 3.1376947,
    lng: 101.6233261,
    maps_url:
      'https://www.google.com/maps/search/?api=1&query=Village%20Park%20%20Kuala%20Lumpur&query_place_id=0x31cc4931330bf621:0x21aac39e1d6f6f3c',
    dishes: ['nasi lemak', '椰浆饭', 'sambal', '炸鸡']
  },
  why: 'Nasi lemak sedap dengan sambal dan ayam goreng rangup.',
  distance_m: null,
  citations: [
    {
      post_url: 'https://www.rednote.com/explore/68b305d5000000001d00f479',
      excerpt:
        '1.Village Park 椰浆饭 谁懂啊！这才是吉隆坡椰浆饭的天花板！米饭裹满浓郁椰香，配的炸鸡腿外脆里嫩，小黄瓜和辣椒酱超解腻，人均20+RM吃到撑！',
      platform: 'rednote',
      author_handle: null,
      posted_at: '8/30/2025'
    },
    {
      post_url: 'https://www.google.com/maps/search/?api=1&query=Village%20Park%20Nasi%20Lemak%20Kuala%20Lumpur',
      excerpt:
        "We'd heard about Village Park's nasi lemak for years before finally making the trip out to Damansara Utama to try it ourselves. It's the kind of no-frills coffeeshop where you can tell the queue outside means something.",
      platform: 'google_maps',
      author_handle: null,
      posted_at: 'a month ago'
    }
  ]
}
