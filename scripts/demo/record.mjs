// Demo capture for MakanLah. Records the page, not the screen: no window chrome,
// no notifications, identical on any machine.
//
// Deliberately slow. Default automation types and clicks instantly, which reads
// as fake, and the pauses on cited posts are the point of the product.
//
// Writes beats.json alongside the capture: the wall-clock offset of every moment
// worth narrating. narrate.sh reads it, so narration lands on the beat even when
// a page gets slower. Hand-tuned millisecond offsets drift the moment anything
// upstream changes, and a narration that contradicts the picture is worse than
// silence.

import { mkdirSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const DIR = process.env.DEMO_DIR || join(tmpdir(), 'makanlah-demo')
const WEB = process.env.DEMO_WEB || 'http://localhost:5188'
const API = process.env.DEMO_API || 'http://127.0.0.1:8000'
// The craving list is deterministic from the clock, so the dish on offer first
// depends on the hour the recording runs. At 19:00 that is bak kut teh, whose
// RedNote posts are dead -- leadPair then correctly refuses to pair a dead post
// with a live one and the corroboration frame cannot render. This picks a
// craving by index instead of filming whichever dish the hour happens to lead
// with. Unset, the walk is unchanged.
const CRAVING = process.env.DEMO_CRAVING === undefined ? -1 : Number(process.env.DEMO_CRAVING)
const OUT = join(DIR, 'capture')

// Prefer a playwright installed into DEMO_DIR, which is how the README sets this
// up: it pulls a browser and used to have no business in the app's tree. That is
// no longer strictly true -- playwright is now a root dev dependency for the
// cross-engine motion check -- so fall back to the repo's own copy rather than
// failing. The DEMO_DIR path resolved a resolve-from-here.cjs shim that nothing
// ever created, so this file could not run at all.
const require = createRequire(import.meta.url)
let chromium
try {
  chromium = createRequire(join(DIR, 'package.json'))('playwright').chromium
} catch {
  chromium = require('playwright').chromium
}

rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })

const started = Date.now()
const beats = []
// A beat is a name and the offset it happened at. Recorded after the wait that
// settles the frame, so it points at what the viewer is looking at.
const mark = (name) => {
  const ms = Date.now() - started
  beats.push({ name, ms })
  console.log(`  ${String(ms).padStart(6)}ms  ${name}`)
}
const beat = (page, ms) => page.waitForTimeout(ms)

const browser = await chromium.launch({ channel: 'chrome' })
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  recordVideo: { dir: OUT, size: { width: 1440, height: 900 } }
})
const page = await ctx.newPage()
page.setDefaultTimeout(20000)

const errors = []
page.on('pageerror', (e) => errors.push(String(e).slice(0, 120)))
page.on('console', (m) => m.type() === 'error' && errors.push(m.text().slice(0, 120)))

let pairs = 0

try {
  // 1. Landing. The ?api= is how this client is pointed at a backend; it is
  //    stored, so later navigations do not need it.
  await page.goto(`${WEB}/?api=${encodeURIComponent(API)}`, { waitUntil: 'networkidle' })
  // Landing is the slowest route -- reveal sections plus corpus figures from
  // /health, measured settling at ~1845ms. Hold past that before the beat.
  await beat(page, 2600)
  mark('landing')

  // The chatbot-versus-real-post comparison IS the pitch's opening argument and
  // it got four seconds in the launch cut. Scroll onto it and stay there.
  const compare = page.locator('text=/Ask A Chatbot/i').first()
  if (await compare.isVisible().catch(() => false)) {
    await compare.scrollIntoViewIfNeeded()
  } else {
    await page.mouse.wheel(0, 700)
  }
  await beat(page, 1400)
  mark('compare')
  await beat(page, 7000)
  await page.mouse.wheel(0, 420)
  await beat(page, 7200)

  // 2. The taste wizard. This is the thing that makes it not a search box.
  await page.goto(`${WEB}/taste`, { waitUntil: 'networkidle' })
  // Layout settles at ~749ms but the mascot needs ~4s more: pixi fetches a
  // 508KB chunk, the moc3 and the textures. Filming her half-painted is worse
  // than filming her late.
  await beat(page, 5200)
  mark('taste')

  for (let step = 0; step < 6; step++) {
    // Options are <label class="option"> wrapping an sr-only checkbox or radio.
    // Click the label: it toggles the input and is what a person actually hits.
    const options = page.locator('.taste-steps label.option:visible')
    const n = await options.count()
    const steered = step === 0 && CRAVING >= 0
    if (n > 0) {
      await options.nth(steered ? CRAVING : 0).click()
      await beat(page, 900)
      // A second pick, but never the "Say It In My Own Words" escape hatch,
      // which opens a text field and stalls the flow.
      if (n > 2 && !steered) {
        await options.nth(1).click()
        await beat(page, 900)
      }
    }
    const next = page.getByRole('button', { name: /Continue|Find Food/ })
    if (!(await next.isVisible().catch(() => false))) break
    const label = (await next.textContent())?.trim()
    await beat(page, 700)
    await next.click()
    await beat(page, 1100)
    if (label === 'Find Food') break
  }

  // 3. Results. Hold on the evidence -- the cited post IS the product.
  await page.waitForURL(/discover/, { timeout: 20000 }).catch(() => {})
  await page.waitForLoadState('networkidle')
  await beat(page, 3200)
  mark('discover')
  await page.mouse.wheel(0, 500)
  await beat(page, 3000)
  await page.mouse.wheel(0, 500)
  await beat(page, 3000)

  // 4. Two platforms carrying the same venue, side by side. This is the single
  //    strongest frame in the product and it did not render until #20 was fixed,
  //    so assert it rather than assuming: a silent one-column fallback is exactly
  //    the failure that shipped last time.
  const twoUp = page.locator('.evidence-pair').filter({ has: page.locator('.testimony:nth-child(2)') })
  pairs = await twoUp.count()
  if (pairs > 0) {
    await twoUp.first().scrollIntoViewIfNeeded()
    await beat(page, 900)
    mark('corroboration')
    await beat(page, 4200)
  }

  // 5. A venue page and its citation trail.
  const firstResult = page.locator('a[href^="/r/"]').first()
  if (await firstResult.isVisible().catch(() => false)) {
    await firstResult.click()
    await page.waitForLoadState('networkidle')
    await beat(page, 2800)
    mark('venue')
    await page.mouse.wheel(0, 600)
    await beat(page, 4000)
    // The closing line is read over this. Scrolling through the rest of the trail
    // keeps it moving rather than holding a dead frame under the narration.
    await page.mouse.wheel(0, 500)
    await beat(page, 3200)
  }

  // 6. The honesty beat. The venue the route lands on may have no dead citation
  //    at all, so this navigates to one that has BOTH -- 興记肉骨茶 carries two
  //    live posts and one that no longer opens. An all-dead page would make the
  //    line "it says so" land without the contrast that gives it meaning.
  const DEAD_VENUE = process.env.DEMO_DEAD_VENUE || '6ac6d7e4-e048-4298-8437-a060c6a30fa9'
  await page.goto(`${WEB}/r/${DEAD_VENUE}`, { waitUntil: 'networkidle' })
  await beat(page, 2600)
  const deadRow = page.locator('text=/no longer opens/i').first()
  if (await deadRow.isVisible().catch(() => false)) {
    await deadRow.scrollIntoViewIfNeeded()
    await beat(page, 1200)
    mark('dead')
    await beat(page, 6000)
  } else {
    console.log('  ! no dead-citation row on the venue page -- the honesty beat did not film')
  }
  mark('end')
} catch (e) {
  console.log(`  FAILED: ${String(e).slice(0, 200)}`)
} finally {
  const video = page.video()
  await ctx.close()
  await browser.close()
  if (video) {
    renameSync(await video.path(), join(DIR, 'capture.webm'))
    console.log(`video: ${join(DIR, 'capture.webm')}`)
  }
  writeFileSync(join(DIR, 'beats.json'), `${JSON.stringify(beats, null, 2)}\n`)
  console.log(`corroboration pairs on screen: ${pairs}`)
  console.log(`console errors: ${errors.length}`)
  for (const e of errors.slice(0, 5)) {
    console.log(`  ! ${e}`)
  }
}
