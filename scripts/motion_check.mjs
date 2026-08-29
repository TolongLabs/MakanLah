/**
 * Does the interface still move when the operating system says "no animations"?
 *
 * Windows Settings > Accessibility > Visual effects > Animation effects, and macOS
 * Reduce motion, both land on prefers-reduced-motion: reduce. People flip them for
 * performance and preference as often as for vestibular sensitivity, so "reduce" has
 * to mean less movement, not a dead interface.
 *
 * The contract this asserts, in BOTH engines because they are separate
 * implementations of it:
 *
 *   1. Nothing is ever left invisible or displaced. Whatever the preference, every
 *      animated element settles at opacity 1 with no transform. This is the failure
 *      that actually hurts -- content gated behind an animation that never runs.
 *   2. Under reduce, travel is gone: .rise-in resolves to the fade keyframes.
 *   3. Under reduce, motion is NOT gone: the fade still has a real duration.
 *   4. Under reduce, looping motion stops outright.
 *   5. Under reduce, hover and press feedback keeps a real transition. Cutting it to
 *      1ms was the bug -- it made every control feel dead.
 *
 * Probes are injected into the real page so the assertions read the real stylesheet
 * through the real engine, without needing the app in a particular state.
 *
 *   node scripts/motion_check.mjs            # BASE defaults to 127.0.0.1:4199
 */

import { chromium, firefox } from 'playwright'

const BASE = process.env.WEB_BASE || 'http://127.0.0.1:4199'
const ENGINES = [
  ['chromium', chromium],
  ['firefox', firefox]
]

const PROBE = () => {
  const host = document.createElement('div')
  host.id = 'motion-probe'
  host.innerHTML =
    '<div class="rise-in"></div><div class="fade-in"></div>' +
    '<div class="skeleton-bar"></div><button class="btn" type="button">probe</button>'
  document.body.appendChild(host)
  const read = (sel) => {
    const el = host.querySelector(sel)
    const cs = getComputedStyle(el)
    return {
      name: cs.animationName,
      duration: cs.animationDuration,
      iteration: cs.animationIterationCount,
      transition: cs.transitionDuration,
      opacity: cs.opacity,
      transform: cs.transform
    }
  }
  return {
    rise: read('.rise-in'),
    fade: read('.fade-in'),
    skeleton: read('.skeleton-bar'),
    btn: read('.btn'),
    // Precondition: proves the stylesheet is actually attached. Without it every
    // assertion below would pass just as happily against a blank page.
    stylesheetLoaded: getComputedStyle(document.body).backgroundColor !== 'rgba(0, 0, 0, 0)'
  }
}

const secs = (v) => Number.parseFloat(String(v).replace('s', '')) || 0
const settled = (o) =>
  Number.parseFloat(o.opacity) === 1 && (o.transform === 'none' || o.transform === 'matrix(1, 0, 0, 1, 0, 0)')

let failures = 0
const fail = (engine, mode, msg) => {
  console.log(`FAIL  [${engine}/${mode}] ${msg}`)
  failures += 1
}

for (const [engineName, engine] of ENGINES) {
  const browser = await engine.launch()
  for (const mode of ['no-preference', 'reduce']) {
    const context = await browser.newContext({ reducedMotion: mode === 'reduce' ? 'reduce' : 'no-preference' })
    const before = failures
    const page = await context.newPage()
    await page.goto(BASE, { waitUntil: 'load' })
    const r = await page.evaluate(PROBE)
    // Let every entrance run to completion before judging the resting state.
    await page.waitForTimeout(900)
    const after = await page.evaluate(() => {
      const host = document.getElementById('motion-probe')
      const st = (sel) => {
        const cs = getComputedStyle(host.querySelector(sel))
        return { opacity: cs.opacity, transform: cs.transform }
      }
      return { rise: st('.rise-in'), fade: st('.fade-in') }
    })

    if (!r.stylesheetLoaded) {
      fail(engineName, mode, 'the stylesheet is not attached, so nothing here was measured')
      await context.close()
      continue
    }

    // 1. Nothing invisible or displaced, either mode.
    for (const [label, o] of [
      ['rise-in', after.rise],
      ['fade-in', after.fade]
    ]) {
      if (!settled(o)) fail(engineName, mode, `${label} settled at opacity ${o.opacity} transform ${o.transform}`)
    }

    if (mode === 'reduce') {
      // 2. Travel removed.
      if (r.rise.name !== 'fade-in')
        fail(engineName, mode, `.rise-in animation is "${r.rise.name}", wanted fade-in (travel should be gone)`)
      // 3. But motion not removed.
      if (secs(r.rise.duration) <= 0) fail(engineName, mode, '.rise-in has no duration -- reduce became "off"')
      if (secs(r.fade.duration) <= 0) fail(engineName, mode, '.fade-in has no duration -- reduce became "off"')
      // 4. Looping motion stops.
      if (r.skeleton.name !== 'none') fail(engineName, mode, `.skeleton-bar still loops "${r.skeleton.name}"`)
      // 5. Feedback survives.
      if (secs(r.btn.transition) < 0.05)
        fail(engineName, mode, `.btn transition is ${r.btn.transition} -- controls feel dead`)
    } else {
      if (r.rise.name !== 'rise-in') fail(engineName, mode, `.rise-in animation is "${r.rise.name}", wanted rise-in`)
    }

    const tick = mode === 'reduce' ? 'reduce ' : 'default'
    // Label from what actually happened. Printing "ok" on a line whose mode just
    // failed is how a red run reads green at a glance.
    console.log(
      `${failures === before ? 'ok  ' : 'FAIL'}  ${engineName.padEnd(8)} ${tick}  rise=${r.rise.name}/${r.rise.duration}  ` +
        `fade=${r.fade.duration}  loop=${r.skeleton.name}  btn-transition=${r.btn.transition}  settled=${settled(after.rise)}`
    )
    await context.close()
  }
  await browser.close()
}

console.log(failures ? `\n${failures} motion assertions failed` : '\nmotion survives reduced-motion in both engines')
process.exit(failures ? 1 : 0)
