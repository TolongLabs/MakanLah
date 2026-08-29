export type Theme = 'light' | 'dark' | 'system'

const KEY = 'makanlah.theme'

/**
 * The theme, as a stored choice rather than only as an OS preference.
 *
 * Three states and not two. "System" is the default and is a real state, not the
 * absence of one: somebody whose laptop flips to dark at sunset should get that,
 * and a two-state toggle silently takes it away the first time they touch it.
 *
 * `system` stamps NO attribute, so `prefers-color-scheme` alone decides. The other
 * two stamp `data-theme`, which `tokens.css` declares against in both directions
 * so an explicit light choice beats a dark OS and vice versa.
 *
 * `docs/PRODUCT.md` promises nothing leaves the browser, and `Privacy.tsx` says the
 * theme choice is kept in local storage. It said that before this module existed
 * and was untrue at the time; it is true now.
 */
export function loadTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
  // Native widgets -- scrollbars, selects, date pickers, form controls -- read this
  // and nothing else. Without it a dark page keeps a light OS scrollbar.
  root.style.colorScheme = theme === 'system' ? 'light dark' : theme
}

export function saveTheme(theme: Theme): void {
  try {
    if (theme === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, theme)
  } catch {
    // Storage blocked. The choice still applies for this page.
  }
  applyTheme(theme)
}

/**
 * Applied before React mounts, from `main.tsx`.
 *
 * A stored dark choice applied in an effect paints the light theme for one frame
 * first, which is the flash every themed site gets wrong once.
 */
export function bootTheme(): void {
  applyTheme(loadTheme())
}
