// Every control and surface must be solid or glass. Never half-transparent.
//
// Owner decision, 2026-08-30: "ALL of the CTA buttons, cards, components have
// either solid or glassmorphism background, never half-transparent or transparent
// background." Glass is allowed because it is a real material -- a translucent
// layer WITH a backdrop-filter behind it. What is banned is the middle state: a
// partly-transparent background with nothing filtering behind it, which is what
// makes a control look unfinished rather than deliberate.
//
// This reads COMPUTED styles from a real browser rather than grepping the CSS,
// because the thing that matters is what composites on screen. A rule can be
// overridden, inherited, or beaten on specificity, and none of that shows in the
// source. `background: transparent` in a file is a lead, not a finding.
//
// Usage: node scripts/opaque-check.mjs [baseUrl]
// Exits 1 and prints each offender. Mutation-test it before trusting a pass.

import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = process.argv[2] || process.env.CHECK_BASE || 'http://localhost:5177'

// Surfaces and controls. Plain text, list items and layout wrappers are not in
// scope: a paragraph with no background is correct, and demanding one would be a
// check nobody could ever make green.
const SELECTOR = [
  'button',
  'a.btn',
  '.btn',
  '.result',
  '.skeleton',
  '.chip-button',
  '.option',
  '.segment',
  '.modal',
  '[role="dialog"]',
  'dialog',
  '.foot',
  '.card',
  '.ask-trigger',
  '.nav-drawer-panel',
  '.topbar'
].join(',')

const ROUTES = ['/', '/discover', '/taste']

const PREFS = JSON.stringify({
  craving: ['bak kut teh'],
  company: 'family',
  range_m: 0,
  mood: 'comfort',
  budget: 'mid'
})

const browser = await chromium.launch({ channel: 'chrome' })
const findings = []
let inspected = 0

for (const theme of ['light', 'dark']) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await ctx.newPage()
  page.setDefaultTimeout(25000)

  await page.goto(BASE, { waitUntil: 'domcontentloaded' })
  await page.evaluate((p) => localStorage.setItem('makanlah.prefs', p), PREFS)

  for (const route of ROUTES) {
    await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle' }).catch(() => {})
    await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
    // /discover searches on arrival; the cards are the point of this check.
    await page.waitForTimeout(route === '/discover' ? 9000 : 1500)

    const bad = await page.evaluate(
      ({ sel, route, theme }) => {
        const out = []
        let seen = 0
        for (const el of document.querySelectorAll(sel)) {
          const cs = getComputedStyle(el)
          // Invisible elements composite nothing, so they cannot look unfinished.
          if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden) continue
          const r = el.getBoundingClientRect()
          if (r.width < 2 || r.height < 2) continue
          seen++

          const bg = cs.backgroundColor || ''
          const m = bg.match(/rgba?\(([^)]+)\)/)
          if (!m) continue
          const parts = m[1].split(',').map((x) => Number.parseFloat(x.trim()))
          const alpha = parts.length > 3 ? parts[3] : 1

          const filtered = (cs.backdropFilter || cs.webkitBackdropFilter || 'none') !== 'none'
          // An image background (a gradient, a texture) is a background.
          const painted = (cs.backgroundImage || 'none') !== 'none'

          if (alpha >= 1 || filtered || painted) continue

          out.push({
            route,
            theme,
            tag: el.tagName.toLowerCase(),
            cls: (el.getAttribute('class') || '').slice(0, 60),
            text: (el.textContent || '').trim().slice(0, 28),
            bg,
            alpha
          })
        }
        return { out, seen }
      },
      { sel: SELECTOR, route, theme }
    )
    inspected += bad.seen
    findings.push(...bad.out)
  }
  await ctx.close()
}

await browser.close()

console.log(`inspected ${inspected} visible controls and surfaces across ${ROUTES.length} routes x 2 themes`)

if (!findings.length) {
  console.log('all solid or glass')
  process.exit(0)
}

// De-duplicate: the same class on ten cards is one defect, not ten.
const byClass = new Map()
for (const f of findings) {
  const key = `${f.cls}|${f.theme}`
  if (!byClass.has(key)) byClass.set(key, { ...f, count: 0 })
  byClass.get(key).count++
}

console.log(`\n${byClass.size} distinct offenders (${findings.length} elements):\n`)
for (const f of byClass.values()) {
  console.log(`  [${f.theme}] ${f.route}  <${f.tag} class="${f.cls}">  bg=${f.bg} alpha=${f.alpha}  x${f.count}`)
  if (f.text) console.log(`      text: ${f.text}`)
}
process.exit(1)
