// A glass surface has to be VISIBLE, not merely translucent.
//
// scripts/opaque-check.mjs asks whether a surface is solid or glass, and glass
// passes it. That is the wrong question for a footer: `--glass` was white at 58%,
// which over the cream `--paper` composited to five values off the page ground and
// read as no background at all. Every property was set correctly. The check agreed
// with itself and the owner spotted it by looking.
//
// So this one never reads a style. It screenshots the page and samples the pixels
// either side of a surface's own top edge, which is the only thing that can tell a
// visible band from an invisible one.
//
// Usage: node scripts/glass-contrast.mjs [baseUrl]

import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const { PNG } = (() => {
  try {
    return { PNG: require('pngjs').PNG }
  } catch {
    return { PNG: null }
  }
})()

const BASE = process.argv[2] || process.env.CHECK_BASE || 'http://localhost:5177'

// A surface step is meant to be quiet, not loud. Below this it is not a step.
const MIN_RATIO = 1.1

const SURFACES = [{ sel: '.foot', name: 'site footer' }]
const ROUTES = ['/', '/dashboard']

const lin = (c) => {
  const s = c / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const luminance = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const browser = await chromium.launch({ channel: 'chrome' })
const findings = []
let checked = 0

for (const theme of ['light', 'dark']) {
  for (const route of ROUTES) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
    const page = await ctx.newPage()
    page.setDefaultTimeout(25000)
    await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle' }).catch(() => {})
    await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
    // Read the footer where a reader meets it: at the end of the page. The landing
    // page opens on a full-viewport hero, and the fixed footer sits behind it by
    // design until you scroll past. Sampling at scroll-0 measures the hero twice
    // and calls the footer invisible, which it is not -- it is covered, on purpose.
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await page.waitForTimeout(1500)

    for (const s of SURFACES) {
      const geo = await page.evaluate((sel) => {
        const el = document.querySelector(sel)
        if (!el) return null
        const r = el.getBoundingClientRect()
        return { top: Math.round(r.top), left: Math.round(r.left), width: Math.round(r.width) }
      }, s.sel)
      if (!geo) continue

      const shot = await page.screenshot({ type: 'png' })
      const png = PNG.sync.read(shot)
      // Row MEANS across the full width, not one pixel each side. On the landing
      // page the fixed footer sits over the hero photograph, where two single
      // pixels are two bits of the same picture and their ratio says nothing about
      // the bar. A mean still moves, because an 80% tint pulls the whole row toward
      // itself whatever is underneath.
      //
      // Offsets clear the 1px rule and the inset highlight on the surface's own
      // edge, so this weighs the two fills rather than the line between them.
      const above = rowMean(png, geo.left, geo.width, geo.top - 6)
      const below = rowMean(png, geo.left, geo.width, geo.top + 10)
      if (!above || !below) continue
      checked++
      const ratio = contrast(above, below)
      const line = `[${theme}] ${route} ${s.name}: page ${rgb(above)} vs surface ${rgb(below)} = ${ratio.toFixed(3)}:1`
      if (ratio < MIN_RATIO) findings.push(line)
      else console.log(`  ok  ${line}`)
    }
    await ctx.close()
  }
}

await browser.close()

function rowMean(png, left, width, y) {
  if (y < 0 || y >= png.height) return null
  const x0 = Math.max(0, left)
  const x1 = Math.min(png.width, left + width)
  if (x1 - x0 < 8) return null
  let r = 0
  let g = 0
  let b = 0
  for (let x = x0; x < x1; x++) {
    const i = (png.width * y + x) << 2
    r += png.data[i]
    g += png.data[i + 1]
    b += png.data[i + 2]
  }
  const n = x1 - x0
  return [Math.round(r / n), Math.round(g / n), Math.round(b / n)]
}
function rgb([r, g, b]) {
  return `rgb(${r},${g},${b})`
}

console.log(`\nsampled ${checked} surface edges across ${ROUTES.length} routes x 2 themes, floor ${MIN_RATIO}:1`)

if (!findings.length) {
  console.log('every glass surface reads against the ground behind it')
  process.exit(0)
}

console.log(`\n${findings.length} surface(s) below the floor -- translucent but invisible:\n`)
for (const f of findings) console.log(`  ${f}`)
process.exit(1)
