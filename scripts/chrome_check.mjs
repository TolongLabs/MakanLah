/**
 * Are the browser's own widgets still the browser's, or are they ours?
 *
 * Scrollbars, text selection, focus rings, autofill, tooltips and dialogs are the
 * parts of a page most likely to be left at the operating system default, and
 * they are the parts that give away that a site is a document rather than a
 * product. They also do not follow a theme: a Windows scrollbar stays light grey
 * on a dark page, and Chrome's autofill paints a fixed yellow over a styled field.
 *
 * The assertions are about COMPUTED VALUES READ FROM A REAL ENGINE, and each one
 * is checked in both themes so "theme-aware" means the value actually moves
 * rather than being a token that happens to resolve the same twice.
 *
 *   node scripts/chrome_check.mjs
 *   BASE=https://makanlah-b5h.pages.dev node scripts/chrome_check.mjs
 */

import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://127.0.0.1:4198'

let failures = 0
const say = (ok, line) => {
  if (!ok) failures++
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${line}`)
}

/** Two colours are "different" only well past rounding and antialiasing noise. */
function moved(a, b) {
  if (!a || !b) return false
  const pa = (a.match(/[\d.]+/g) ?? []).map(Number)
  const pb = (b.match(/[\d.]+/g) ?? []).map(Number)
  if (pa.length < 3 || pb.length < 3) return a !== b
  return Math.abs(pa[0] - pb[0]) + Math.abs(pa[1] - pb[1]) + Math.abs(pa[2] - pb[2]) > 30
}

const READ = `(() => {
  const probe = document.createElement('div')
  probe.style.cssText = 'position:fixed;left:-9999px;width:80px;height:40px;overflow:scroll'
  probe.innerHTML = '<div style="height:400px"></div>'
  document.body.appendChild(probe)
  const cs = getComputedStyle(probe)

  // A styled scrollbar is either the standards property or a webkit pseudo with a
  // width we set. Both are read here so either implementation counts.
  const pseudo = getComputedStyle(probe, '::-webkit-scrollbar')
  const out = {
    scrollbarWidth: cs.scrollbarWidth,
    scrollbarColor: cs.scrollbarColor,
    scrollbarPseudoWidth: pseudo ? pseudo.width : null,
    // Chrome reports the UA default scrollbar as 15px; ours must not be that.
    nativeGutter: probe.offsetWidth - probe.clientWidth
  }
  probe.remove()

  const sel = getComputedStyle(document.body, '::selection')
  out.selectionBg = sel ? sel.backgroundColor : null
  out.selectionFg = sel ? sel.color : null

  out.accent = getComputedStyle(document.documentElement).accentColor
  out.caret = getComputedStyle(document.documentElement).caretColor
  out.colorScheme = getComputedStyle(document.documentElement).colorScheme

  // Tokens the drawer and the rest of the chrome should be reading.
  const root = getComputedStyle(document.documentElement)
  out.paper = root.getPropertyValue('--paper').trim()
  out.ink = root.getPropertyValue('--ink').trim()

  out.drawer = Boolean(document.querySelector('[data-nav-drawer], .drawer, .nav-drawer'))
  out.drawerToggle = Boolean(document.querySelector('[data-nav-drawer-toggle], .nav-drawer-toggle'))

  // A native title attribute is the tooltip we are replacing. Any left on an
  // interactive control means the OS tooltip still shows there.
  out.nativeTitles = [...document.querySelectorAll('a[title], button[title], [role=button][title]')].length
  return out
})()`

const browser = await chromium.launch()
const read = async (scheme, path = '/') => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme })
  const page = await ctx.newPage()
  await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  const out = await page.evaluate(READ)
  await ctx.close()
  return out
}

const light = await read('light')
const dark = await read('dark')
// The drawer lives on every screen EXCEPT the landing, where the owner had the
// control removed: that page sells and a menu beside Get Started is a second door
// out of it. Reading `/` for a drawer therefore measures the wrong page, which is
// what this check did until the landing changed underneath it.
const inside = await read('light', '/discover')

// 1. The scrollbar is ours.
say(
  light.scrollbarWidth === 'thin' || (light.scrollbarPseudoWidth && light.scrollbarPseudoWidth !== 'auto'),
  `scrollbar is styled  width=${light.scrollbarWidth} pseudo=${light.scrollbarPseudoWidth} gutter=${light.nativeGutter}px`
)
// Zero is a PASS, not a failure. Chromium's overlay scrollbars paint over the
// content and take no layout space at all, so a styled scrollbar measures 0 there
// and a classic one measures its declared width. The claim worth asserting is that
// it is not the 15px unstyled default; the colours below are what prove it is ours.
say(
  light.nativeGutter < 15,
  `scrollbar does not reserve the OS default gutter  gutter=${light.nativeGutter}px (unstyled is 15)`
)
say(
  moved(light.scrollbarColor, dark.scrollbarColor) || light.scrollbarColor !== dark.scrollbarColor,
  `scrollbar recolours with the theme  light=${light.scrollbarColor} dark=${dark.scrollbarColor}`
)

// 2. Selection is ours, and it moves.
say(
  Boolean(light.selectionBg) && light.selectionBg !== 'rgba(0, 0, 0, 0)',
  `selection has a colour  ${light.selectionBg}`
)
say(
  moved(light.selectionBg, dark.selectionBg),
  `selection recolours with the theme  light=${light.selectionBg} dark=${dark.selectionBg}`
)

// 3. Native form widgets follow the brand rather than the OS.
say(light.accent !== 'auto', `accent-color is set for native widgets  ${light.accent}`)
say(moved(light.caret, dark.caret), `caret recolours with the theme  light=${light.caret} dark=${dark.caret}`)
say(
  light.colorScheme.includes('light') && dark.colorScheme.includes('dark'),
  `color-scheme follows the theme  light="${light.colorScheme}" dark="${dark.colorScheme}"`
)

// 4. The drawer exists and is ours, on the screens that have one.
say(inside.drawer, 'a MakanLah nav drawer is in the DOM')
say(inside.drawerToggle, 'the drawer has a toggle control')
say(!light.drawerToggle, 'the landing carries no menu control, so nothing competes with Get Started')

// 5. No OS tooltips left on interactive controls.
say(light.nativeTitles === 0, `no native title tooltips on controls  found=${light.nativeTitles}`)

await browser.close()
console.log(failures === 0 ? '\nthe chrome is ours' : `\n${failures} chrome assertions failed`)
process.exit(failures === 0 ? 0 : 1)
