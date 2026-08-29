import { useEffect, useId, useState } from 'react'
import { loadTheme, saveTheme, type Theme } from '../theme'

const ORDER: { value: Theme; label: string }[] = [
  { value: 'system', label: 'Auto' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' }
]

/**
 * Three segments rather than a sun/moon toggle.
 *
 * A two-state toggle cannot express "follow my machine", so the first tap silently
 * takes that away from somebody whose laptop flips at sunset. Three named segments
 * cost one extra control and say exactly what each does.
 *
 * Real radios behind visually hidden inputs, which is the same idiom the taste
 * wizard's options use. Buttons with role="radio" would need a hand-rolled arrow
 * key handler and a roving tabindex; a native radio group is given both, by the
 * platform, correctly.
 */
export function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(loadTheme)
  const name = useId()

  // A stored 'system' means the OS decides, and the OS can change while the page is
  // open. The tokens follow on their own -- that is a media query -- but the hint
  // that native widgets read does not.
  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const on = () => saveTheme('system')
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [theme])

  return (
    <fieldset className="theme-switch">
      <legend className="sr-only">Theme</legend>
      {ORDER.map((t) => (
        <label className="theme-seg" key={t.value}>
          <input
            className="sr-only"
            type="radio"
            name={name}
            value={t.value}
            checked={theme === t.value}
            onChange={() => {
              setTheme(t.value)
              saveTheme(t.value)
            }}
          />
          <span>{t.label}</span>
        </label>
      ))}
    </fieldset>
  )
}
