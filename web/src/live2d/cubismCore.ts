/**
 * The Cubism Core is a global script, not a module: bundling it breaks its own init.
 * Kawan loads it from index.html, which makes every visitor pay 147 KB before first
 * paint for a mascot most of them never scroll to. Issue #11 says the mascot must
 * never block first paint, so it is injected on demand instead and cached here.
 */
const SRC = '/live2dcubismcore.min.js'

let pending: Promise<void> | null = null

export function loadCubismCore(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'))
  if ('Live2DCubismCore' in window) return Promise.resolve()
  if (pending) return pending

  pending = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SRC}"]`)
    const el = existing ?? document.createElement('script')
    el.addEventListener('load', () => resolve(), { once: true })
    el.addEventListener(
      'error',
      () => {
        pending = null
        reject(new Error('cubism core failed to load'))
      },
      { once: true }
    )
    if (!existing) {
      el.src = SRC
      el.async = true
      document.head.appendChild(el)
    }
  })
  return pending
}
