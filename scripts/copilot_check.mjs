/**
 * Is the copilot a copilot, and is there still only one of her?
 *
 * Two things here fail silently and neither is visible in a screenshot.
 *
 * **One WebGL context, moved, never two.** The character lives in the `/discover`
 * aside; the ask dialog needs her too. Mounting a second Live2D stage gives one
 * character two GL contexts, and depending on the driver the second silently kills
 * the first — the page keeps rendering, the aside just goes blank, and nothing is
 * logged. So the aside unmounts hers while the dialog is open, and this asserts the
 * count across the handoff rather than asserting she is "present".
 *
 * **The tool trace is the evidence claim made watchable.** `makanlah/copilot.py`
 * enforces that she answers from stored excerpts or declines, and that has always
 * been invisible. If the trace stops rendering, the product loses the only place a
 * user can watch the guarantee hold, and every other check still passes.
 *
 * `/ask/stream` is stubbed with a scripted turn because the point is the client's
 * handling of the event sequence, not the model's answer. The fallback path is
 * exercised separately, because "the stream is not deployed" is production today.
 *
 * `node scripts/copilot_check.mjs http://host`
 */
import { chromium } from 'playwright'

const BASE = process.argv[2] ?? process.env.BASE ?? 'http://localhost:4180'
const PREFS = { craving: ['char siew'], company: 'solo', range_m: 0, mood: 'comfort' }

const TURN = [
  { type: 'tool_call', id: 't1', name: 'read_citations', args: { venue_id: 'x' } },
  { type: 'tool_result', id: 't1', summary: '4 posts, 2 platforms', count: 4 },
  { type: 'tool_call', id: 't2', name: 'filter_by_topic', args: { topic: 'halal' } },
  { type: 'tool_result', id: 't2', summary: '1 post mentions it', count: 1 },
  { type: 'delta', text: 'One of the four posts mentions halal, ' },
  { type: 'delta', text: 'and the writer says the pork is on a separate counter.' },
  {
    type: 'done',
    covered: true,
    citations: [
      {
        post_id: 'p1',
        post_url: 'https://www.rednote.com/explore/abc',
        platform: 'rednote',
        posted_at: 'Feb 17',
        excerpt: 'x',
        author_handle: 'a'
      }
    ]
  }
]

const fail = []
const note = (ok, msg) => {
  if (!ok) fail.push(msg)
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${msg}`)
}

const browser = await chromium.launch()

/** A results page with saved answers, ready to open the dialog from. */
async function results(page) {
  await page.route('**/recommend', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [
          {
            venue: {
              id: 'v1',
              name: '叉烧杨家家来 Char Siew Yoong',
              area: 'Cheras',
              lat: 3.1,
              lng: 101.7,
              maps_url: 'https://www.google.com/maps/search/?api=1&query=x',
              dishes: ['叉烧'],
              corroboration: { posts: 2, authors: 1, platforms: 2 }
            },
            rank: 1,
            why: 'x',
            match: { basis: 'dish', dish: 'char siew', similarity: 0.5 },
            distance_m: 1200,
            citations: [
              {
                post_id: 'p1',
                post_url: 'https://www.rednote.com/explore/a',
                platform: 'rednote',
                excerpt: '汤头浓郁',
                author_handle: 'a',
                posted_at: 'Feb 17',
                dead: null
              }
            ]
          }
        ],
        degraded: false,
        sources_used: ['rednote']
      })
    })
  )
  await page.route('**/suggestions', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"chips":[],"band":"","source":"corpus"}' })
  )
  await page.route('**/companion', (route) => route.fulfill({ status: 200, body: '{}' }))
  await page.goto(BASE, { waitUntil: 'domcontentloaded' })
  await page.evaluate((p) => localStorage.setItem('makanlah.prefs', JSON.stringify(p)), PREFS)
  await page.goto(`${BASE}/discover`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.result', { timeout: 30000 })
  await page.waitForTimeout(600)
}

// ------------------------------------------------------------------ the stream
{
  // Wide enough that the stage mounts at all; below 48rem she is deliberately absent
  // everywhere and this assertion would be vacuously true.
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } })
  await page.route('**/ask/stream', (route) =>
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: TURN.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
    })
  )
  await results(page)

  // Give the aside's stage time to paint before measuring the handoff.
  await page.waitForSelector('.ask-stage canvas', { timeout: 30000 }).catch(() => {})
  const before = await page.locator('canvas').count()
  note(before === 1, `the aside owns exactly one stage before the dialog opens (${before})`)

  await page.locator('.ask-trigger').first().click()
  await page.waitForSelector('dialog.modal[open]', { timeout: 15000 })
  await page.waitForSelector('.chat-stage canvas', { timeout: 30000 }).catch(() => {})
  await page.waitForTimeout(600)

  const during = await page.locator('canvas').count()
  const inAside = await page.locator('.ask-stage canvas').count()
  const inChat = await page.locator('.chat-stage canvas').count()
  // THE ASSERTION THAT MATTERS. Two contexts is the failure, and a check that only
  // asked "is she in the dialog" would pass while the aside quietly went black.
  note(during === 1, `exactly one stage while the dialog is open (${during} total)`)
  note(inAside === 0 && inChat === 1, `she moved rather than duplicated (aside ${inAside}, chat ${inChat})`)

  await page.locator('.chat-form .ask-input').fill('is it halal?')
  await page.locator('.chat-form button[type=submit]').click()
  await page.waitForSelector('.chat-answer', { timeout: 20000 })
  await page.waitForTimeout(400)

  note((await page.locator('.steps-done').count()) === 1, 'the trace collapsed once she answered')
  const summary = (await page.locator('.steps-toggle').first().innerText()).trim()
  note(/2 steps/.test(summary), `the collapsed row counts the steps  ${JSON.stringify(summary)}`)

  await page.locator('.steps-toggle').first().click()
  await page.waitForTimeout(200)
  const steps = (await page.locator('.steps li').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ').trim())
  note(steps.length === 2, `the trace reopens with both steps (${steps.length})`)
  note(
    steps.some((t) => /read citations/.test(t) && /4 posts/.test(t)),
    `each step names itself and its result  ${JSON.stringify(steps)}`
  )
  note(!steps.some((t) => /_/.test(t)), 'tool names are readable, not identifiers')

  const answer = await page.locator('.chat-answer').first().innerText()
  note(/separate counter/.test(answer), 'the streamed deltas assembled into one answer')
  note((await page.locator('.ask-sources li').count()) === 1, 'the answer carries its citation')

  await page.close()
}

// ---------------------------------------------------------------- the fallback
{
  // Production today: /ask/stream does not exist. The conversation must still work.
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } })
  let usedOneShot = 0
  page.on('request', (r) => {
    if (/\/ask$/.test(r.url())) usedOneShot++
  })
  await page.route('**/ask/stream', (route) => route.fulfill({ status: 404, body: 'Not Found' }))
  await page.route('**/ask', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ covered: false, answer: 'The posts do not mention parking.', citations: [] })
    })
  )
  await results(page)
  await page.locator('.ask-trigger').first().click()
  await page.waitForSelector('dialog.modal[open]', { timeout: 15000 })
  await page.locator('.chat-form .ask-input').fill('parking?')
  await page.locator('.chat-form button[type=submit]').click()
  await page.waitForSelector('.chat-answer', { timeout: 20000 })
  await page.waitForTimeout(300)

  note(usedOneShot > 0, 'a missing stream falls back to POST /ask')
  note((await page.locator('.steps-done').count()) === 0, 'no trace is invented when there was no stream')
  note((await page.locator('.chat-uncited').count()) === 1, 'an uncovered answer says why there is nothing to cite')
  // The answer already says the posts do not cover it; a second refusal underneath
  // said the same thing twice.
  const body = await page.locator('.chat-reply').first().innerText()
  note(!/Nobody wrote about that one/.test(body), 'the refusal is not printed twice')
  await page.close()
}

await browser.close()
if (fail.length > 0) {
  console.error(`\n${fail.length} failed:\n${fail.map((f) => `  - ${f}`).join('\n')}`)
  process.exit(1)
}
console.log('\nthe copilot shows its working, and there is one of her')
