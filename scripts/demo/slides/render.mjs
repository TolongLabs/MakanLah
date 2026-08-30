// Slides are HTML rendered by the same browser that captures the product, so the
// deck and the app cannot drift apart on type, colour or spacing -- they read the
// same tokens. Screenshot rather than SVG export: web fonts and CJK glyphs need a
// real text engine, and this one is already a dependency.

import { join } from 'node:path'
import { chromium } from 'playwright'

const DIR = process.env.DEMO_DIR || '/tmp/makanlah-demo'
const HERE = new URL('.', import.meta.url).pathname
const browser = await chromium.launch({ channel: 'chrome' })
const page = await (
  await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1
  })
).newPage()

for (const name of ['arch', 'market']) {
  await page.goto(`file://${join(HERE, `${name}.html`)}`, { waitUntil: 'networkidle' })
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(400)
  const out = join(DIR, `slide-${name}.png`)
  await page.screenshot({ path: out })
  const empty = await page.evaluate(() => document.body.innerText.trim().length < 40)
  console.log(`${name}: ${out}${empty ? '  !! PAGE LOOKS EMPTY' : ''}`)
}
await browser.close()
