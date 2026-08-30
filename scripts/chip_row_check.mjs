// The chip row must be a PREFIX of the ranking, not whatever happens to fit.
//
// The chips carry post counts and are served in descending order, so the number on
// each one is evidence volume. A row that shows `fish 246` while hiding `curry 272`
// and `BKT 256` is not a shorter row, it is a wrong one -- it tells you the corpus
// ranks fish above curry.
//
// That shipped. `fitOneRow` hid a wrapped chip and read the next chip's offsetTop in
// the same loop, but `hidden` reflows immediately, so the chips after the hidden one
// moved up into the gap and were then measured against the layout the hiding had
// just created. At 390px -- the most common phone width -- `fish` was narrow enough
// to fit the space `curry` vacated, so it survived and the two dishes ranked above it
// did not. Every other width happened to come out a prefix by luck.
//
// No unit test can hold this: jsdom has no layout, so `offsetTop` is 0 for every
// element and the wrap never happens. It has to be a real browser.
//
// The chips are SERVED FROM A FIXTURE here, not from the live API. Two reasons: the
// real /suggestions is time-banded, so the row changes with the hour and a CI run at
// 03:00 MYT would test a different set than one at noon; and the layout job has no API
// behind it, which the first version of this check discovered by measuring nothing at
// all seven widths and failing rather than passing.
//
// The fixture is not invented. It is the exact row production served when the bug was
// found -- six dishes, descending counts, with a narrow one (`fish`) last. That shape
// is what triggers the defect: `fish` is slim enough to fit the space `curry` frees
// when it is hidden. A tidier fixture would not reproduce it.
//
// Usage: node scripts/chip_row_check.mjs [baseUrl]

import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = process.argv[2] || process.env.BASE || 'http://localhost:5177'
const WIDTHS = [360, 390, 430, 520, 700, 1024, 1280]
const PREFS = JSON.stringify({ craving: ['nasi lemak'], company: 'family', range_m: 0, mood: 'comfort' })

const CHIPS = [
  { label: 'soup', query: 'soup', posts: 728, venues: 310 },
  { label: 'rice', query: 'rice', posts: 665, venues: 397 },
  { label: 'chicken', query: 'chicken', posts: 619, venues: 351 },
  { label: 'curry', query: 'curry', posts: 272, venues: 191 },
  { label: 'BKT', query: 'BKT', posts: 256, venues: 162 },
  { label: 'fish', query: 'fish', posts: 246, venues: 180 }
]

const browser = await chromium.launch({ channel: 'chrome' })
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await ctx.newPage()
page.setDefaultTimeout(30000)
await page.route('**/suggestions', (route) =>
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ chips: CHIPS, band: 'fixture', source: 'corpus' })
  })
)
// Neither is under test, and both are slow to nothing without an API behind them.
await page.route('**/recommend', (route) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: '{"results":[],"degraded":false}' })
)
await page.route('**/companion', (route) => route.fulfill({ status: 200, body: '{}' }))
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.evaluate((p) => localStorage.setItem('makanlah.prefs', p), PREFS)

const findings = []
let measured = 0

// Load ONCE and resize, rather than reloading per width. A fresh load at each width
// measures the row before the webfont settles, and the fallback face gives different
// chip widths -- which made this check pass against the very bug it was written for.
// One load, fonts ready, then resize: that is the sequence that reproduces it.
await page.goto(`${BASE}/discover`, { waitUntil: 'networkidle' }).catch(() => {})
await page.waitForSelector('.chip-button', { timeout: 25000 }).catch(() => {})
await page.evaluate(() => document.fonts.ready)
await page.waitForTimeout(600)

for (const width of WIDTHS) {
  await page.setViewportSize({ width, height: 844 })
  await page.waitForTimeout(250)

  const r = await page.evaluate(() => {
    const all = [...document.querySelectorAll('.chip-button')]
    const label = (e) => (e.textContent || '').trim().split(/\s+/)[0]
    const dom = all.map(label)
    const shown = all.filter((e) => !e.hidden).map(label)
    const rows = new Set(all.filter((e) => !e.hidden).map((e) => Math.round(e.getBoundingClientRect().top)))
    return { dom, shown, rows: rows.size }
  })

  // A width where the chips never arrived measures nothing; say so rather than
  // counting it as a pass.
  if (!r.dom.length) {
    console.log(`  --  ${width}px: no chips rendered, not measured`)
    continue
  }
  measured++

  const isPrefix = r.shown.every((v, i) => v === r.dom[i])
  if (!isPrefix) {
    const skipped = r.dom.filter(
      (d) => !r.shown.includes(d) && r.dom.indexOf(d) < r.dom.indexOf(r.shown[r.shown.length - 1])
    )
    findings.push(`${width}px shows [${r.shown}] but skips [${skipped}] from the middle of the ranking`)
  } else if (r.rows > 1) {
    findings.push(`${width}px renders ${r.rows} rows; the rail is one row always`)
  } else {
    console.log(`  ok  ${width}px: ${r.shown.length} of ${r.dom.length} chips, one row, prefix of the ranking`)
  }
}

await browser.close()

console.log(`\nmeasured ${measured} of ${WIDTHS.length} widths`)

// Every width failing to render is indistinguishable from every width passing, if
// the only thing checked is the absence of findings.
if (measured < 2) {
  console.log('too few widths rendered chips to conclude anything')
  process.exit(1)
}

if (!findings.length) {
  console.log('the chip row is a prefix of the ranking at every width measured')
  process.exit(0)
}

console.log(`\n${findings.length} problem(s):\n`)
for (const f of findings) console.log(`  ${f}`)
process.exit(1)
