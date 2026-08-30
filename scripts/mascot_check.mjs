/**
 * Did the mascot actually paint?
 *
 * This exists because the check that came before it did not ask that. It asserted
 * a WebGL context existed and was not lost, which is true of a completely blank
 * canvas, so `scale: 0.3, anchorY: 0.08` shipped to production and rendered
 * nothing at all. Every asset returned 200, `onReady` fired, the context was
 * live, and the rail was empty. The owner found it by looking at the page.
 *
 * The model canvas is 4648x8000 units and the character's ink starts 34.3% down
 * it. The old anchor framed the empty third above her head. See
 * `web/src/live2d/modelRegistry.ts` for how the ink box was measured.
 *
 * The assertion here is deliberately about PIXELS, not about state:
 *
 *   1. The canvas exists and has a real size at desktop width.
 *   2. A meaningful fraction of it is opaque. A live context is not enough.
 *   3. Her head is near the top of the box rather than cropped out of it.
 *   4. Below 56rem no canvas is created at all -- not hidden, never mounted,
 *      because a phone was downloading 500 KB of pixi for a 1x1 canvas.
 *
 * It screenshots the element rather than calling readPixels, on purpose. A WebGL
 * drawing buffer is cleared after compositing unless preserveDrawingBuffer is on,
 * so a naive readPixels returns zeros whether or not anything rendered -- a check
 * that reports the failure it is looking for no matter what is worse than none.
 * A screenshot is what the viewer actually sees.
 *
 *   node scripts/mascot_check.mjs                  # BASE defaults to the dev server
 *   BASE=https://makanlah-b5h.pages.dev node scripts/mascot_check.mjs
 */

import { inflateSync } from 'node:zlib'
import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://127.0.0.1:4188'

// Under this and she is not in the box. Measured at 57.8% with the correct
// framing, so the bar sits far below the real value and far above blank.
const MIN_COVERAGE = 12
// Her head has to be in the top third, or the crop has slid down her body.
const MAX_TOP_ROW_FRACTION = 0.35

/** Decode a Playwright PNG screenshot to {width, height, rgba}. 8-bit RGB or RGBA only. */
function decodePng(buf) {
  let pos = 8
  const idat = []
  let width = 0
  let height = 0
  let colorType = 6
  let bitDepth = 8
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos)
    const type = buf.toString('ascii', pos + 4, pos + 8)
    const data = buf.subarray(pos + 8, pos + 8 + len)
    if (type === 'IHDR') {
      width = data.readUInt32BE(0)
      height = data.readUInt32BE(4)
      bitDepth = data[8]
      colorType = data[9]
    } else if (type === 'IDAT') idat.push(data)
    else if (type === 'IEND') break
    pos += 12 + len
  }
  if (bitDepth !== 8 || (colorType !== 6 && colorType !== 2)) {
    throw new Error(`unsupported PNG: bitDepth ${bitDepth}, colorType ${colorType}`)
  }
  const channels = colorType === 6 ? 4 : 3
  const raw = inflateSync(Buffer.concat(idat))
  const stride = width * channels
  const out = Buffer.alloc(height * stride)
  let rp = 0
  for (let y = 0; y < height; y++) {
    const filter = raw[rp++]
    const line = raw.subarray(rp, rp + stride)
    rp += stride
    const cur = out.subarray(y * stride, (y + 1) * stride)
    const prev = y > 0 ? out.subarray((y - 1) * stride, y * stride) : null
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? cur[x - channels] : 0
      const b = prev ? prev[x] : 0
      const c = x >= channels && prev ? prev[x - channels] : 0
      let v = line[x]
      if (filter === 1) v += a
      else if (filter === 2) v += b
      else if (filter === 3) v += (a + b) >> 1
      else if (filter === 4) {
        const p = a + b - c
        const pa = Math.abs(p - a)
        const pb = Math.abs(p - b)
        const pc = Math.abs(p - c)
        v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c
      }
      cur[x] = v & 0xff
    }
  }
  return { width, height, channels, pixels: out }
}

/**
 * Ink is anything that differs from the page ground behind the canvas. Alpha is
 * not usable here: Playwright composites the element onto the page, so a
 * transparent canvas screenshots as opaque paper rather than as alpha 0.
 */
function inkOf(png, ground) {
  const { width, height, channels, pixels } = png
  let lit = 0
  let topRow = height
  let botRow = -1
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * channels
      const d =
        Math.abs(pixels[i] - ground[0]) + Math.abs(pixels[i + 1] - ground[1]) + Math.abs(pixels[i + 2] - ground[2])
      if (d > 24) {
        lit++
        if (y < topRow) topRow = y
        if (y > botRow) botRow = y
      }
    }
  }
  return { coverage: (lit / (width * height)) * 100, topRow, botRow }
}

let failures = 0
const say = (ok, line) => {
  if (!ok) failures++
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${line}`)
}

const browser = await chromium.launch()

// -------------------------------------------------------------- desktop: she paints
{
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
  await page.goto(`${BASE}/taste`, { waitUntil: 'networkidle' })
  const canvas = page.locator('.companion canvas')
  try {
    await canvas.waitFor({ state: 'attached', timeout: 20000 })
  } catch {
    say(false, 'desktop: no mascot canvas was ever created')
  }
  // pixi needs a few frames after the model resolves before it has drawn one.
  await page.waitForTimeout(4000)

  if (await canvas.count()) {
    const ground = await page.evaluate(() => {
      const el = document.querySelector('.companion')
      const rgb = getComputedStyle(el).getPropertyValue('background-color')
      // The canvas is transparent, so the ground is the page's paper token.
      const paper = getComputedStyle(document.body).backgroundColor
      const m = (rgb === 'rgba(0, 0, 0, 0)' ? paper : rgb).match(/\d+/g)
      return m ? m.slice(0, 3).map(Number) : [255, 255, 255]
    })
    const png = decodePng(await canvas.screenshot())
    const ink = inkOf(png, ground)
    say(png.width > 100 && png.height > 100, `desktop: canvas has a real box  ${png.width}x${png.height}`)
    say(
      ink.coverage >= MIN_COVERAGE,
      `desktop: the mascot is painted  coverage=${ink.coverage.toFixed(1)}% (want >=${MIN_COVERAGE}%)`
    )
    say(
      ink.topRow >= 0 && ink.topRow <= png.height * MAX_TOP_ROW_FRACTION,
      `desktop: her head is in frame  topRow=${ink.topRow} of ${png.height}`
    )
  }
  await page.close()
}

// ------------------------------------------------------------- tablet: she paints
//
// The band between phone and desktop had no companion at all: `Companion.tsx` gated
// her at 56rem to match the width where the rail becomes a second column, which
// answered "is there room for a character" with the answer to "is there room for a
// column". Measured at 834 before the fix: canvas NONE, and 549px of empty page
// between the last option and the island.
//
// Asserted HERE, in the check that counts pixels, rather than only in the geometry
// run -- a reserved 288x220 box with nothing drawn in it is precisely the failure
// that shipped once already, and a box is not a mascot.
{
  const page = await (await browser.newContext({ viewport: { width: 834, height: 1112 } })).newPage()
  await page.goto(`${BASE}/taste`, { waitUntil: 'networkidle' })
  const canvas = page.locator('.companion canvas')
  try {
    await canvas.waitFor({ state: 'attached', timeout: 20000 })
  } catch {
    say(false, 'tablet: no mascot canvas was ever created at 834')
  }
  await page.waitForTimeout(4000)

  if (await canvas.count()) {
    const ground = await page.evaluate(() => {
      const paper = getComputedStyle(document.body).backgroundColor
      const m = paper.match(/\d+/g)
      return m ? m.slice(0, 3).map(Number) : [255, 255, 255]
    })
    const png = decodePng(await canvas.screenshot())
    const ink = inkOf(png, ground)
    // The same box as the rail column, not the full page width. `frame()` scales by
    // height and centres on w/2, so a full-width stage leaves her small and adrift
    // in a 4:1 letterbox with the bubble's tail pointing at nothing.
    say(png.width <= 320, `tablet: her stage is the width she is framed for  ${png.width}x${png.height}`)
    say(
      ink.coverage >= MIN_COVERAGE,
      `tablet: the mascot is painted  coverage=${ink.coverage.toFixed(1)}% (want >=${MIN_COVERAGE}%)`
    )
    say(
      ink.topRow >= 0 && ink.topRow <= png.height * MAX_TOP_ROW_FRACTION,
      `tablet: her head is in frame  topRow=${ink.topRow} of ${png.height}`
    )
  }
  await page.close()
}

// ------------------------------------------- she does not follow the cursor
//
// `pixi-live2d-display` defaults `autoInteract` to true, which makes her eyes and
// head track the pointer across the whole document. Removed on request, and
// asserted here because a library upgrade would silently restore a default.
//
// Measured as a RATIO against a control, not as an absolute. The model breathes,
// blinks and sways on its own, so "the pixels changed" proves nothing: the floor
// is how much they change with the pointer held still, and gaze has to clear it.
// Validated in both directions before being trusted -- with autoInteract true the
// ratio is 2.38, with it false 0.55.
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  await page.goto(`${BASE}/taste`, { waitUntil: 'networkidle' })
  const canvas = page.locator('.companion canvas')
  await canvas.waitFor({ state: 'attached', timeout: 20000 }).catch(() => {})
  if (await canvas.count()) {
    await page.waitForTimeout(4000)
    const frame = async () => decodePng(await canvas.screenshot())
    const delta = (a, c) => {
      const n = Math.min(a.pixels.length, c.pixels.length)
      let sum = 0
      for (let i = 0; i < n; i++) sum += Math.abs(a.pixels[i] - c.pixels[i])
      return sum / n
    }
    await page.mouse.move(720, 450)
    await page.waitForTimeout(800)
    const still = await frame()
    await page.waitForTimeout(800)
    const noise = delta(still, await frame())
    await page.mouse.move(8, 8)
    await page.waitForTimeout(800)
    const left = await frame()
    await page.mouse.move(1432, 892)
    await page.waitForTimeout(800)
    const moved = delta(left, await frame())
    say(
      moved < noise * 2,
      `she does not follow the cursor  idle=${noise.toFixed(2)} corner-to-corner=${moved.toFixed(2)} ` +
        `ratio=${(moved / (noise || 0.001)).toFixed(2)} (tracking is >=2)`
    )
  }
  await ctx.close()
}

// ------------------------------- the chunk fails: onboarding must still work
//
// Break the subject on purpose. `React.lazy` plus `Suspense` handles a PENDING
// import, not a REJECTED one, so before StageBoundary a single failed fetch of the
// 508 KB mascot chunk threw through render and took /taste with it: measured with a
// control at ZERO step panels and ZERO options, against 4 and 4 with the chunk
// allowed. That is the first screen every guest has to complete, and the failure is
// silent -- a white page, no error, no retry.
//
// The trigger is mundane. A redeploy leaves a browser holding an index.html naming a
// chunk hash that no longer exists; a mobile connection drops one request; a proxy or
// a CDN edge misses.
//
// Asserting that she mounts when the chunk loads cannot fail on any of that, which is
// the whole reason this block aborts the request rather than trusting the happy path.
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await ctx.route('**/MascotStage-*.js', (route) => route.abort())
  const page = await ctx.newPage()
  await page.goto(`${BASE}/taste`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(3000)
  const state = await page.evaluate(() => ({
    panels: document.querySelectorAll('.step-panel').length,
    options: document.querySelectorAll('.step-panel:not([hidden]) .option').length,
    heading: (document.querySelector('.step-question')?.textContent ?? '').trim().length,
    bubble: (document.querySelector('.companion-bubble')?.textContent ?? '').trim().length,
    canvas: document.querySelectorAll('.companion canvas').length,
    body: (document.body.innerText ?? '').trim().length
  }))
  say(state.body > 0, `chunk fails: the page is not blank  bodyLen=${state.body}`)
  say(state.panels > 0, `chunk fails: the step panels render  panels=${state.panels}`)
  say(state.options > 0, `chunk fails: there are options to pick  options=${state.options}`)
  say(state.heading > 0, `chunk fails: the question is on screen  chars=${state.heading}`)
  // The reading is the information and the face is the presentation. Losing one must
  // not lose the other.
  say(state.bubble > 0, `chunk fails: she still has a line to say  chars=${state.bubble}`)
  say(state.canvas === 0, `chunk fails: no half-built canvas is left behind  found=${state.canvas}`)
  await ctx.close()
}

// ------------------------------------------------- phone: never mounted, not hidden
{
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage()
  await page.goto(`${BASE}/taste`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(4000)
  const state = await page.evaluate(() => ({
    canvas: document.querySelectorAll('.companion canvas').length,
    bubble: (document.querySelector('.companion-bubble')?.textContent ?? '').trim().length
  }))
  say(state.canvas === 0, `phone: no canvas is created at all  found=${state.canvas}`)
  say(state.bubble > 0, 'phone: she still has a line to say')
  await page.close()
}

await browser.close()
console.log(failures === 0 ? '\nthe mascot is on screen' : `\n${failures} mascot assertions failed`)
process.exit(failures === 0 ? 0 : 1)
