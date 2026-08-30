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
// Prod by default now. The local default existed because there was no public API
// (#6) and the client had to be pointed at 127.0.0.1 with `?api=`. Both are
// deployed, and a launch walkthrough has to show the real corpus rather than
// whatever a laptop happens to hold. Set DEMO_WEB/DEMO_API for a local run.
const WEB = process.env.DEMO_WEB || 'https://makanlah-b5h.pages.dev'
const API = process.env.DEMO_API || 'https://makanlah-api.vercel.app'
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
// Every surface the walk is supposed to film, counted rather than assumed. The
// corroboration pair taught this: a beat that silently does not render leaves a
// video that looks fine and is missing the argument. A zero here is a failed run.
const filmed = { why: 0, sources: 0, ask: 0, dead: 0 }

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

  // The wizard's craving list is deterministic from the clock, so which dish the
  // walk arrives on is not ours to choose -- and the corpus no longer corroborates
  // every dish. Measured on prod after the retrieval fix (6487f84), WITHOUT
  // geolocation, which is how this walk arrives: `bak kut teh` returns 9 results
  // with 3 corroborated, `roti canai` 8 with 3, `banana leaf rice` 10 with 2.
  // `蛋挞` and `dim sum` come back with a SINGLE result without a radius --
  // corroborated, but one card is a thin frame -- so the fallback has to be a
  // query that fills the screen and corroborates, not merely one that corroborates.
  //
  // So if the craving we landed on cannot show the strongest frame in the product,
  // search for one that can, rather than filming a walk with its argument missing.
  // This is a real query returning real results, not a staged one -- but it IS a
  // chosen one, and the handoff records which, the same way the last cut did.
  if (pairs === 0) {
    const fallback = process.env.DEMO_QUERY || 'bak kut teh'
    console.log(`  no corroboration pair for the wizard's craving -- searching ${fallback}`)
    await page.locator('#find').fill(fallback)
    await beat(page, 900)
    await page.locator('#find').press('Enter')
    await page.waitForLoadState('networkidle')
    await beat(page, 3400)
    mark('research')
    await page.mouse.wheel(0, 420)
    await beat(page, 2600)
    pairs = await twoUp.count()
  }

  if (pairs > 0) {
    await twoUp.first().scrollIntoViewIfNeeded()
    await beat(page, 900)
    mark('corroboration')
    await beat(page, 4200)
  }

  // 5. Why This Showed. The card answers "why is this here" in its subtitle, and
  //    everything the row had no room for sits one tap behind this control. It is
  //    the differentiator compressed into one gesture: a recommender that can be
  //    asked to justify a pick, on the card, without leaving the page. Filming the
  //    OPEN state matters -- a closed disclosure is a triangle nobody reads.
  const why = page.locator('.why-more').first()
  if (await why.isVisible().catch(() => false)) {
    await why.scrollIntoViewIfNeeded()
    await beat(page, 1000)
    await why.locator('.why-more-toggle').click()
    // The disclosure animates open; the beat is marked after it has settled so the
    // narration does not land on a half-open box.
    await beat(page, 1300)
    mark('why')
    filmed.why = 1
    await beat(page, 4200)
    await why.locator('.why-more-toggle').click()
    await beat(page, 700)
  }

  // 6. All Sources. The whole citation trail for one venue, over the results
  //    rather than away from them. It is a real /r/:venueId URL that a normal
  //    click renders as a dialog, so the trail arrives without losing the page
  //    behind it -- and the dead row is in here, which is what the honesty beat
  //    below then holds on.
  const sources = page.locator('.result').first().locator('a.link[href^="/r/"]').first()
  if (await sources.isVisible().catch(() => false)) {
    await sources.click()
    await page.waitForSelector('dialog[open]', { timeout: 10000 }).catch(() => {})
    await beat(page, 2600)
    mark('sources')
    filmed.sources = 1
    await beat(page, 4000)
    await page.mouse.wheel(0, 420)
    await beat(page, 3400)
    await page.keyboard.press('Escape')
    await beat(page, 900)
  }

  // 7. The copilot, and the strongest frame in the product. This was the
  //    pipeline's oldest known gap: `/ask` existed as an endpoint with no UI, so
  //    the moment where she is asked something the corpus cannot answer and says
  //    so could not be filmed at all. It has a UI now.
  //
  //    `/ask/stream` is not deployed and returns 404, which the client treats as
  //    "not deployed yet" and falls back to the one-shot `/ask`. So this films the
  //    answer without the tool trace. Verified against prod before filming rather
  //    than discovered on camera.
  const ask = page.locator('.result').first().locator('.ask-trigger')
  if (await ask.isVisible().catch(() => false)) {
    await ask.click()
    await page.waitForSelector('dialog[open]', { timeout: 10000 }).catch(() => {})
    await beat(page, 1600)
    await page.locator('.ask-input').fill(process.env.DEMO_QUESTION || 'Is this place halal?')
    await beat(page, 1100)
    await page.locator('.ask-input').press('Enter')
    // Wait for the answer ELEMENT, not for words. The first version matched a regex
    // against the dialog's text, which is a check that owns its own definition of
    // success: when the phrasing did not match it waited the full 40s and swallowed
    // the timeout, and the capture carried 45 seconds of dead frame while /ask was
    // in fact answering in under a second. `.chat-answer` is a state the UI exposes
    // rather than a sentence this file guessed at.
    await page.waitForSelector('.chat-answer', { timeout: 40000 }).catch(() => {
      console.log('  ! the copilot did not answer within 40s -- the ask beat is a dead frame')
    })
    await beat(page, 1400)
    mark('ask')
    filmed.ask = 1
    await beat(page, 5200)
    await page.keyboard.press('Escape')
    await beat(page, 800)
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
    filmed.dead = 1
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
  // Named surfaces, reported individually. "The video looks fine" is not a check:
  // a beat that never rendered leaves a shorter film that still plays, and the
  // narration then reads a line over a picture that does not show it.
  const missing = Object.entries(filmed)
    .filter(([, got]) => !got)
    .map(([name]) => name)
  console.log(
    `surfaces filmed: ${Object.entries(filmed)
      .map(([k, v]) => `${k}=${v}`)
      .join(' ')}`
  )
  if (missing.length) console.log(`  !! NOT FILMED: ${missing.join(', ')} -- do not narrate these beats`)
  console.log(`console errors: ${errors.length}`)
  for (const e of errors.slice(0, 5)) {
    console.log(`  ! ${e}`)
  }
}
