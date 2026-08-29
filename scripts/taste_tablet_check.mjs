/**
 * Is the wizard usable at tablet width, and is the companion actually on it?
 *
 * Three claims, and two of them pull against each other, which is the point. Giving
 * the companion a stage in the 48-56rem band spends vertical space to fix an empty
 * page; spending too much of it puts the last option under the fixed island, which
 * is a worse bug than the one being fixed (#93). A check that only asserted "she is
 * present" would pass while hiding content behind a bar.
 *
 * Every number is read from `getBoundingClientRect` in a real engine at a real
 * viewport. Nothing here reads CSS or a breakpoint constant: the rule under test is
 * the thing that would be wrong, so asking it whether it is right proves nothing.
 *
 *   node scripts/taste_tablet_check.mjs
 *   BASE=https://makanlah-b5h.pages.dev node scripts/taste_tablet_check.mjs
 */

import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://127.0.0.1:4198'
const WIDTHS = [390, 768, 834, 1024]

/* /discover sends anyone without saved answers back through the wizard, so measuring
   it means arriving with some. This is the shape `prefs.ts` writes; it is seeded
   rather than clicked through because four steps of UI is not what is under test. */
const PREFS = JSON.stringify({ craving: ['bak kut teh'], company: 'solo', range_m: 0, mood: 'light' })

let failures = 0
const say = (ok, line) => {
  if (!ok) failures++
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${line}`)
}

const READ = `(() => {
  const box = (el) => {
    if (!el) return null
    const r = el.getBoundingClientRect()
    return { top: Math.round(r.top), bottom: Math.round(r.bottom), w: Math.round(r.width), h: Math.round(r.height) }
  }
  const canvas = document.querySelector('.companion-stage canvas')
  const options = [...document.querySelectorAll('.step-panel:not([hidden]) .option')]
  return {
    vh: window.innerHeight,
    canvas: box(canvas),
    question: box(document.querySelector('.step-question')),
    lastOption: box(options[options.length - 1]),
    island: box(document.querySelector('.bottom-island')),
    optionCount: options.length
  }
})()`

const browser = await chromium.launch()
const results = {}

for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: 1112 } })
  const page = await ctx.newPage()
  await page.goto(`${BASE}/taste`, { waitUntil: 'domcontentloaded' })
  // Wait on the thing itself rather than a fixed timeout. A half-megabyte lazy chunk
  // plus a 900ms sleep measures the network, and on a cold context it measures it as
  // an absent mascot -- which is exactly the false report this run exists to avoid.
  await page.waitForSelector('.companion-stage canvas', { timeout: 20000 }).catch(() => {})
  await page.waitForTimeout(600)
  results[width] = await page.evaluate(READ)
  await ctx.close()
}

for (const width of WIDTHS) {
  const r = results[width]
  const c = r.canvas
  console.log(
    `\n--- ${width}px  canvas=${c ? `${c.w}x${c.h}` : 'NONE'} question.top=${r.question?.top} ` +
      `lastOption.bottom=${r.lastOption?.bottom} island.top=${r.island?.top} vh=${r.vh}`
  )

  if (width < 768) {
    say(c === null, `${width}: no stage on a phone, where 220px of character is the question below the fold`)
  } else {
    say(c !== null && c.w > 0 && c.h > 0, `${width}: the companion has a stage with a real box`)
    // Presence is not enough and this is the half that would silently regress. The
    // rail is a full-width row below 56rem, so without a cap the stage takes the page:
    // measured 770x160 at 834. `frame()` scales by height and centres on w/2, so that
    // does not make her bigger, it makes her small in the middle of a letterbox while
    // the bubble's tail stays at 41px pointing at nothing.
    if (c) say(c.w <= 320, `${width}: her stage is the width she is framed for  ${c.w}x${c.h}`)
  }

  // The bug being fixed and the bug it must not cause, asserted separately so that
  // satisfying one cannot mask the other.
  //
  // The guard on optionCount is not defensive tidiness, it is the whole assertion.
  // The first draft of this check read `lastOption.bottom <= island.top` against a
  // step that renders no `.option` at all, so the numbers were 0 <= 1031 and it
  // printed four green ticks at four widths while measuring nothing. A clearance
  // check with nothing to clear agrees with itself perfectly.
  say(r.optionCount > 0, `${width}: there are options on screen to measure  count=${r.optionCount}`)
  if (r.lastOption && r.island && r.optionCount > 0) {
    say(
      r.lastOption.bottom <= r.island.top,
      `${width}: the last option clears the island  ${r.lastOption.bottom} <= ${r.island.top}`
    )
  }
  if (r.question) {
    say(r.question.top < r.vh, `${width}: the question is above the fold  top=${r.question.top} vh=${r.vh}`)
  }
}

// The dead space this was opened for. Reported as a number at every width rather than
// asserted against a threshold nobody has agreed: 549 at 834 is the round-two reading.
for (const width of WIDTHS) {
  const r = results[width]
  if (r.lastOption && r.island && r.optionCount > 0) {
    console.log(`gap ${width}px: ${r.island.top - r.lastOption.bottom}px between the last option and the island`)
  }
}

// --------------------------------------------------- /discover, the same letterbox
//
// She is mounted here from 48rem already, but the aside is a full-width row rather
// than a 20rem column below 64rem, so an uncapped stage measured 720x180 at 834.
// Same defect as the wizard's and it needs its own assertion: the two screens have
// separate breakpoints and separate stage rules, which is exactly how one of them
// got fixed while the other stayed broken.
{
  // A fresh browser rather than a fifth context on the one above. Four Live2D mounts
  // in a row exhaust this machine and the page crashes, which reads in the log as an
  // absent mascot and is nothing of the sort.
  await browser.close()
  const b2 = await chromium.launch()
  const ctx = await b2.newContext({ viewport: { width: 834, height: 1112 } })
  await ctx.addInitScript(`localStorage.setItem('makanlah.prefs', ${JSON.stringify(PREFS)})`)
  const page = await ctx.newPage()
  await page.goto(`${BASE}/discover`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.ask-stage canvas', { timeout: 20000 }).catch(() => {})
  await page.waitForTimeout(600)
  const r = await page.evaluate(`(() => {
    const c = document.querySelector('.ask-stage canvas')
    const b = c && c.getBoundingClientRect()
    return { path: location.pathname, canvas: b ? { w: Math.round(b.width), h: Math.round(b.height) } : null }
  })()`)
  console.log(`\n--- /discover 834px  path=${r.path}  canvas=${r.canvas ? `${r.canvas.w}x${r.canvas.h}` : 'NONE'}`)
  // If the seeding failed we are on /taste and measuring the wrong screen, which is
  // the mistake that produced a whole round of false readings today.
  say(r.path === '/discover', `/discover 834: we are actually on /discover  path=${r.path}`)
  say(r.canvas !== null, '/discover 834: the companion has a stage')
  if (r.canvas) {
    say(r.canvas.w <= 320, `/discover 834: her stage is the width she is framed for  ${r.canvas.w}x${r.canvas.h}`)
  }
  await ctx.close()
  await b2.close()
}

console.log(failures === 0 ? '\nthe wizard holds at every width' : `\n${failures} assertions failed`)
process.exit(failures === 0 ? 0 : 1)
