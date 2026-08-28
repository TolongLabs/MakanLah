// Demo capture for MakanLah. Records the page, not the screen: no window chrome,
// no notifications, identical on any machine.
//
// Deliberately slow. Default automation types and clicks instantly, which reads
// as fake, and the pauses on cited posts are the point of the product.

import { mkdirSync, rmSync } from 'node:fs'
import { chromium } from 'playwright'

const WEB = 'http://localhost:5188'
const API = 'http://127.0.0.1:8000'
const OUT =
  '/tmp/claude-1000/-home-user-Documents-TolongLabs-MakanLah/4964dd32-db7a-44dc-bbfa-966c1ec73068/scratchpad/capture'

rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })

const beat = (page, ms) => page.waitForTimeout(ms)
const log = (m) => console.log(`  ${m}`)

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

try {
  // 1. Landing. The ?api= is how this client is pointed at a backend; it is
  //    stored, so later navigations do not need it.
  log('landing')
  await page.goto(`${WEB}/?api=${encodeURIComponent(API)}`, { waitUntil: 'networkidle' })
  await beat(page, 2500)
  await page.mouse.wheel(0, 700)
  await beat(page, 2000)
  await page.mouse.wheel(0, 900)
  await beat(page, 2000)
  await page.mouse.wheel(0, -1600)
  await beat(page, 1200)

  // 2. The taste wizard. This is the thing that makes it not a search box.
  log('taste wizard')
  await page.goto(`${WEB}/taste`, { waitUntil: 'networkidle' })
  await beat(page, 2000)

  for (let step = 0; step < 6; step++) {
    // Options are <label class="option"> wrapping an sr-only checkbox or radio.
    // Click the label: it toggles the input and is what a person actually hits.
    const options = page.locator('.taste-steps label.option:visible')
    const n = await options.count()
    if (n > 0) {
      await options.nth(0).click()
      await beat(page, 1000)
      // A second pick, but never the "Say It In My Own Words" escape hatch,
      // which opens a text field and stalls the flow.
      if (n > 2) {
        await options.nth(1).click()
        await beat(page, 1000)
      }
    }
    const next = page.getByRole('button', { name: /Continue|Find Food/ })
    if (!(await next.isVisible().catch(() => false))) break
    const label = (await next.textContent())?.trim()
    await beat(page, 800)
    await next.click()
    await beat(page, 1200)
    if (label === 'Find Food') break
  }

  // 3. Results. Hold on the evidence -- the cited post IS the product.
  log('discover')
  await page.waitForURL(/discover/, { timeout: 20000 }).catch(() => {})
  await page.waitForLoadState('networkidle')
  await beat(page, 3500)
  await page.mouse.wheel(0, 500)
  await beat(page, 3000)
  await page.mouse.wheel(0, 500)
  await beat(page, 3000)

  // 4. A venue page and its citation trail.
  log('venue')
  const firstResult = page.locator('a[href^="/r/"]').first()
  if (await firstResult.isVisible().catch(() => false)) {
    await firstResult.click()
    await page.waitForLoadState('networkidle')
    await beat(page, 3500)
    await page.mouse.wheel(0, 600)
    await beat(page, 3500)
  } else {
    log('  no venue link found, skipping')
  }
} catch (e) {
  console.log(`  FAILED: ${String(e).slice(0, 200)}`)
} finally {
  const video = page.video()
  await ctx.close()
  await browser.close()
  if (video) console.log(`video: ${await video.path()}`)
  console.log(`console errors: ${errors.length}`)
  for (const e of errors.slice(0, 5)) {
    console.log(`  ! ${e}`)
  }
}
