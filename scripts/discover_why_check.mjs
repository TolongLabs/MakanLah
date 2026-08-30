/**
 * Does a result actually say why it is on screen?
 *
 * The owner read his own results page and reported that nothing told him why any
 * pick was there. The information had been on the card since the first build --
 * `basisLine` said "Here because a post names this dish" -- as the EIGHTH line, in
 * the same grey as two neighbouring sentences answering different questions. The
 * data was never the problem, so a check asserting the data is present would have
 * passed throughout and is worthless here. This asserts the rendered HIERARCHY.
 *
 * `/recommend` is stubbed rather than called. Two reasons, and neither is
 * convenience: CI builds the client with no API to reach, and the cases that matter
 * most here are the awkward ones -- a dish match with zero similarity, a venue with
 * no named author, a sentiment count that disagrees with the post count. Waiting for
 * those to turn up in a live query is how a check ends up asserting only the happy
 * path. **Every fixture below is a real shape copied from production**, not an
 * invented one; the figures in the comments were measured against the live API on
 * 2026-08-30.
 *
 * Point it at a running build: `node scripts/discover_why_check.mjs http://host`.
 */
import { chromium } from 'playwright'

const BASE = process.argv[2] ?? process.env.BASE ?? 'http://localhost:4180'
const PREFS = { craving: ['bak kut teh'], company: 'family', range_m: 0, mood: 'comfort' }

const cite = (over = {}) => ({
  post_url: 'https://www.rednote.com/explore/6990402100000',
  excerpt: '汤头浓郁，本地人回头率高。Sedap sangat, worth the queue.',
  platform: 'rednote',
  author_handle: '我就是自由',
  posted_at: 'Feb 17',
  dead: null,
  shared_with: [],
  ...over
})

const RESULTS = [
  {
    // THE CASE THAT DECIDES THE WHOLE DESIGN. Live: `basis: 'dish'` with
    // `similarity: 0.0` on 15 of 35 sampled results -- 63% of every dish match. The
    // lexical lane found this venue where the vector lane never saw it, so a printed
    // number reads "0% match" on one of the strongest answers the corpus holds.
    venue: {
      id: 'v-zero',
      name: '興记肉骨茶',
      area: null, // absent on 19 of 35 sampled results
      lat: 3.1,
      lng: 101.7,
      maps_url: 'https://www.google.com/maps/search/?api=1&query=a',
      dishes: ['干肉骨茶', '三层肉', '排骨'],
      corroboration: { posts: 2, authors: 2, platforms: 1 },
      sentiment: { positive: 6, mixed: 0, negative: 0 } // 6 vs 2 posts: must stay dark
    },
    rank: 1,
    why: 'Michelin Bib Gourmand, tender ribs, consistent quality.',
    match: { basis: 'dish', dish: 'bak kut teh', similarity: 0.0 },
    distance_m: 9391,
    citations: [cite(), cite({ post_url: 'https://www.rednote.com/explore/b', author_handle: '猪粟耶' })]
  },
  {
    // An anonymous Google Maps reviewer: `authors: 0` on 12 of 35 sampled results.
    // The card must say "1 post" and never "0 people".
    venue: {
      id: 'v-anon',
      name: '阿喜',
      area: 'Cheras',
      lat: 3.1,
      lng: 101.7,
      maps_url: 'https://www.google.com/maps/search/?api=1&query=b',
      dishes: ['肉骨茶', '油条'],
      corroboration: { posts: 1, authors: 0, platforms: 1 },
      sentiment: null
    },
    rank: 2,
    why: 'Well-done soup, attentive service.',
    match: { basis: 'dish', dish: 'bak kut teh', similarity: 0.5514 },
    distance_m: 1200,
    citations: [cite({ post_url: 'https://maps.example/1', platform: 'google_maps', author_handle: null })]
  },
  {
    // The weak lane, and #140 makes it the common outcome: every ingredient word
    // resolves to no canonical dish and routes here. Sentiment agrees with the post
    // count on this one, so the breakdown is allowed to render.
    venue: {
      id: 'v-semantic',
      name: 'Village Park',
      area: 'Damansara Uptown',
      lat: 3.1,
      lng: 101.6,
      maps_url: 'https://www.google.com/maps/search/?api=1&query=c',
      dishes: ['nasi lemak', 'ayam goreng berempah'],
      corroboration: { posts: 3, authors: 2, platforms: 2 },
      sentiment: { positive: 2, mixed: 0, negative: 1 }
    },
    rank: 3,
    why: 'A queue that means something.',
    match: { basis: 'semantic', dish: null, similarity: 0.5877 },
    distance_m: 420,
    citations: [
      cite({ post_url: 'https://www.rednote.com/explore/c' }),
      cite({ post_url: 'https://maps.example/2', platform: 'google_maps', author_handle: null })
    ]
  }
]

const fail = []
const note = (ok, msg) => {
  if (!ok) fail.push(msg)
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${msg}`)
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

await page.route('**/recommend', (route) =>
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ results: RESULTS, degraded: false, sources_used: ['rednote', 'google_maps'] })
  })
)
// The companion and the chips are not under test and both are slow to nothing here.
await page.route('**/companion', (route) => route.fulfill({ status: 200, body: '{}' }))
await page.route('**/suggestions', (route) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: '{"chips":[],"band":"","source":"corpus"}' })
)

// /discover sends anyone without saved answers back through the wizard.
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.evaluate((p) => localStorage.setItem('makanlah.prefs', JSON.stringify(p)), PREFS)
await page.goto(`${BASE}/discover`, { waitUntil: 'domcontentloaded' })

try {
  await page.waitForSelector('.result', { timeout: 30000 })
} catch {
  console.error('FAIL  no result rendered from the stubbed response')
  await browser.close()
  process.exit(1)
}
await page.waitForTimeout(400)

const cards = await page.locator('.result').count()
note(cards === RESULTS.length, `every stubbed result rendered (${cards}/${RESULTS.length})`)

const rows = await page.locator('.why-row').count()
note(rows === cards, `every card has a why-row (${rows}/${cards})`)

const leads = await page.locator('.why-lead').allTextContents()
note(leads.length === cards, `every card leads with what matched (${leads.length}/${cards})`)
note(leads[0] === 'Names bak kut teh', `the dish match names the dish  ${JSON.stringify(leads[0])}`)
note(leads[2] === 'Close in meaning', `the semantic match says so plainly  ${JSON.stringify(leads[2])}`)

const list = (await page.locator('.results').innerText()).replace(/\s+/g, ' ')

// A dish match carrying similarity 0.0 is on screen. If any number leaks, it leaks here.
note(!/\b0?\.\d{2,4}\b/.test(list), 'no retrieval number anywhere in the list')
note(!/\d\s?% match/i.test(list), 'no percentage match anywhere in the list')
note(!/\b0 (people|person|posts?)\b/.test(list), 'never claims zero of anything')

// The anonymous reviewer: one post, nobody nameable.
const anon = page.locator('.result').nth(1)
const anonRow = await anon.locator('.why-row').innerText()
note(/1 post/.test(anonRow), `the anonymous venue counts its post  ${JSON.stringify(anonRow)}`)
note(!/person|people/.test(anonRow), 'the anonymous venue claims no people')

// THE FIX ITSELF. Every assertion above passed on the old card too, because the old
// card carried the same words. What was wrong was their weight.
const weight = await page.evaluate(() => {
  const lead = document.querySelector('.why-lead')
  const fact = document.querySelector('.why-row .why-fact')
  if (!lead || !fact) return null
  const a = getComputedStyle(lead)
  const b = getComputedStyle(fact)
  return { leadColor: a.color, factColor: b.color, leadWeight: +a.fontWeight, factWeight: +b.fontWeight }
})
note(weight != null, 'the row has both a lead and a context token to compare')
if (weight) {
  note(
    weight.leadColor !== weight.factColor || weight.leadWeight > weight.factWeight,
    `the answer outweighs the metadata beside it (${weight.leadWeight} ${weight.leadColor} vs ${weight.factWeight} ${weight.factColor})`
  )
}

// The model-written line answers the same question the row now answers, and only one
// of the two can be checked against a post.
note(!list.includes('Michelin Bib Gourmand'), 'no model-written prose on a ranked card')

// Sentiment counts mention rows, not posts (#143). Card one reads 6 sentiment against
// 2 posts and must stay silent; card three agrees at 3 and may speak.
await page.locator('.why-more-toggle').first().click()
await page.waitForTimeout(150)
const firstDetail = await page.locator('.result').first().locator('.why-more-body').innerText()
// Held entirely (#149): `negative <= -0.2` catches mild qualification, and eight of
// ten venues carrying a negative bucket contain no negative language at all. Both
// directions stay dark -- showing only the favourable half biases every card.
note(!/positive|critical|mixed/i.test(firstDetail), 'no sentiment verdict while the buckets are untrusted')
note(firstDetail.trim().length > 0, `the disclosure opens onto real content (${firstDetail.trim().length} chars)`)
note(!/close in meaning/i.test(firstDetail), 'the disclosure does not restate the subtitle above it')

await page.locator('.result').nth(2).locator('.why-more-toggle').click()
await page.waitForTimeout(150)
const thirdDetail = await page.locator('.result').nth(2).locator('.why-more-body').innerText()
// This fixture's counts DO agree (3 vs 3), so it would render but for the hold. It is
// the case that proves the hold is doing the work rather than the unit gate.
note(!/critical|positive|mixed/i.test(thirdDetail), 'held even where the counts agree')
note(/across 2 platforms/.test(thirdDetail), `the rest of the disclosure still renders  ${JSON.stringify(thirdDetail)}`)

await browser.close()
if (fail.length > 0) {
  console.error(`\n${fail.length} failed:\n${fail.map((f) => `  - ${f}`).join('\n')}`)
  process.exit(1)
}
console.log('\na result says why it is on screen')
