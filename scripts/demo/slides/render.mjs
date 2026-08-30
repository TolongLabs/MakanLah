// Slides are HTML rendered by the same browser that captures the product, so the
// deck and the app cannot drift apart on type, colour or spacing -- they read the
// same tokens. Screenshot rather than SVG export: web fonts and CJK glyphs need a
// real text engine, and this one is already a dependency.

import { join } from 'node:path'
import { chromium } from 'playwright'

const DIR = process.env.DEMO_DIR || '/tmp/makanlah-demo'
const HERE = new URL('.', import.meta.url).pathname
const SUBTITLE_TOP = 852
const failures = []
const browser = await chromium.launch({ channel: 'chrome' })
const page = await (
  await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1
  })
).newPage()

for (const name of ['arch', 'market', 'close']) {
  await page.goto(`file://${join(HERE, `${name}.html`)}`, { waitUntil: 'networkidle' })
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(400)
  const out = join(DIR, `slide-${name}.png`)
  await page.screenshot({ path: out })
  const empty = await page.evaluate(() => document.body.innerText.trim().length < 40)

  // The subtitle is burned in later, so a slide cannot see the thing that will cover
  // it. 852 is the measured top row of a two-line libass plate at MarginV=28 on a
  // 1080 frame -- not a guess, and not a number this file gets to choose. A first
  // pass cleared every numeric check and still put a subtitle through the tagline.
  const floor = await page.evaluate(() => {
    let low = 0
    for (const el of document.querySelectorAll('body *')) {
      if (!el.textContent.trim() && !el.querySelector('svg, rect')) continue
      low = Math.max(low, el.getBoundingClientRect().bottom)
    }
    return Math.round(low)
  })
  const collides = floor > SUBTITLE_TOP
  if (collides) failures.push(`${name}: content reaches ${floor}, subtitle plate starts ${SUBTITLE_TOP}`)
  console.log(
    `${name}: ${out}  floor ${floor}/${SUBTITLE_TOP}${empty ? '  !! PAGE LOOKS EMPTY' : ''}${collides ? '  !! SUBTITLE COLLISION' : ''}`
  )
}
await browser.close()

if (failures.length) {
  console.error('\nslides overlap the subtitle band:')
  for (const f of failures) console.error(`  ${f}`)
  process.exit(1)
}
