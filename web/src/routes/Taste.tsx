import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Prefs } from '../api'
import { Mascot } from '../components/Mascot'
import { savePrefs } from '../prefs'
import { BUDGET, type Choice, COMPANY, cravingOptions, MOOD, RANGE, STEPS } from '../taste/options'

type Geo = { lat: number; lng: number } | null

/**
 * The front door. Four discrete steps, a floating island carrying Back, Continue and
 * the counter, and a step index with ticks, following the pattern in the owner's Kawan
 * app rather than a scrolling form.
 *
 * Nothing is written until the final CTA. No localStorage, no PUT /auth/prefs, no
 * partial state left behind by somebody who opened the wizard and changed their mind.
 */
export function Taste() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [reached, setReached] = useState(0)

  const [craving, setCraving] = useState<string[]>([])
  const [ownWords, setOwnWords] = useState('')
  const [showOwnWords, setShowOwnWords] = useState(false)
  const [company, setCompany] = useState<Prefs['company']>()
  const [range, setRange] = useState<number>()
  const [mood, setMood] = useState<Prefs['mood']>()
  const [budget, setBudget] = useState<Prefs['budget']>()

  const [geo, setGeo] = useState<Geo>(null)
  const [geoRefused, setGeoRefused] = useState(false)

  // Generated once per visit, so the options cannot change under the user while they
  // are reading them.
  const cravings = useMemo(() => cravingOptions(), [])

  const typed = ownWords.trim()
  const done = [craving.length > 0 || typed.length > 0, company != null, range != null, mood != null]
  const canContinue = done[step] === true
  const isLast = step === STEPS.length - 1

  function locate(chosen: number) {
    if (chosen === 0 || !navigator.geolocation) {
      if (chosen !== 0) setGeoRefused(true)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setGeo({ lat: p.coords.latitude, lng: p.coords.longitude })
        setGeoRefused(false)
      },
      // Refusing location must never dead-end the wizard. It falls back to KL-wide.
      () => setGeoRefused(true),
      { timeout: 8000 }
    )
  }

  function goTo(next: number) {
    setStep(next)
    setReached((r) => Math.max(r, next))
  }

  function finish() {
    const prefs: Prefs = {
      craving: [...craving, ...(typed ? [typed] : [])],
      ...(company ? { company } : {}),
      ...(range != null ? { range_m: range } : {}),
      ...(mood ? { mood } : {}),
      ...(budget ? { budget } : {})
    }
    // The one write in the whole wizard.
    savePrefs(prefs)
    navigate('/discover', { state: { prefs, geo, geoRefused } })
  }

  return (
    <div className="page taste">
      <div className="taste-steps">
        <Panel step={step} index={0} title="What Are You Craving?" hint="Pick as many as you like.">
          <div className="options">
            {cravings.map((c) => (
              <Toggle
                key={c.value}
                choice={c}
                pressed={craving.includes(c.value)}
                onClick={() =>
                  setCraving((cur) => (cur.includes(c.value) ? cur.filter((v) => v !== c.value) : [...cur, c.value]))
                }
              />
            ))}
            <Toggle
              choice={{ value: 'own', label: 'Say It In My Own Words' }}
              pressed={showOwnWords}
              onClick={() => setShowOwnWords((v) => !v)}
            />
          </div>
          {showOwnWords && (
            <div className="field own-words">
              <label htmlFor="own-words">In Your Own Words</label>
              <input
                id="own-words"
                value={ownWords}
                onChange={(e) => setOwnWords(e.target.value)}
                placeholder="something soupy, not too far"
                autoComplete="off"
              />
              <p className="field-help">Malay, Chinese and English all work, including mixed together.</p>
            </div>
          )}
        </Panel>

        <Panel step={step} index={1} title="Who Is Eating?">
          <div className="options">
            {COMPANY.map((c) => (
              <Radio
                key={c.value}
                name="company"
                choice={c}
                checked={company === c.value}
                onClick={() => setCompany(c.value)}
              />
            ))}
          </div>
        </Panel>

        <Panel step={step} index={2} title="How Far Will You Go?">
          <div className="options">
            {RANGE.map((c) => (
              <Radio
                key={c.value}
                name="range"
                choice={c}
                checked={range === c.value}
                onClick={() => {
                  setRange(c.value)
                  locate(c.value)
                }}
              />
            ))}
          </div>
          {geoRefused && range != null && range > 0 && (
            <p className="notice-plain own-words">
              We could not get your location, so this searches all of KL and distances stay hidden. Everything else
              still works.
            </p>
          )}
          {geo && <p className="notice-plain own-words">Located. Distances will be measured from where you are.</p>}
        </Panel>

        <Panel step={step} index={3} title="What Kind Of Meal?">
          <div className="options">
            {MOOD.map((c) => (
              <Radio key={c.value} name="mood" choice={c} checked={mood === c.value} onClick={() => setMood(c.value)} />
            ))}
          </div>
          <fieldset className="budget-set">
            <legend className="rail-heading">Budget (Optional)</legend>
            <div className="options options-tight">
              {BUDGET.map((c) => (
                <Radio
                  key={c.value}
                  name="budget"
                  choice={c}
                  checked={(budget ?? 'any') === c.value}
                  onClick={() => setBudget(c.value === 'any' ? undefined : (c.value as Prefs['budget']))}
                />
              ))}
            </div>
          </fieldset>
        </Panel>
      </div>

      <aside className="taste-rail">
        <Mascot mood="curious" />
        <nav className="index-island" aria-label="Steps">
          <p className="rail-heading">Your Answers</p>
          <ul className="index-list">
            {STEPS.map((name, i) => (
              <li key={name}>
                <button
                  type="button"
                  className="index-link"
                  aria-current={step === i ? 'step' : undefined}
                  disabled={i > reached}
                  onClick={() => goTo(i)}
                >
                  <span>{name}</span>
                  {done[i] && (
                    <span className="index-tick">
                      <span aria-hidden="true">✓</span>
                      <span className="sr-only">Answered</span>
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <nav className="bottom-island" aria-label="Step navigation">
        <button type="button" className="island-back" onClick={() => goTo(step - 1)} disabled={step === 0}>
          Back
        </button>
        <span className="island-counter" aria-live="polite">
          {`Step ${step + 1} of ${STEPS.length}`}
        </span>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!canContinue}
          onClick={() => (isLast ? finish() : goTo(step + 1))}
        >
          {isLast ? 'Find Food' : 'Continue'}
        </button>
      </nav>
    </div>
  )
}

function Panel({
  step,
  index,
  title,
  hint,
  children
}: {
  step: number
  index: number
  title: string
  hint?: string
  children: React.ReactNode
}) {
  const active = step === index
  return (
    // Keyed on the step so the entry animation replays on every change. The animation
    // itself is a class, and the reduced-motion override in base.css collapses it.
    <section key={active ? `on-${index}` : `off-${index}`} className="step-panel rise-in" hidden={!active}>
      <h1 className="step-question">{title}</h1>
      {hint && <p className="step-hint">{hint}</p>}
      {children}
    </section>
  )
}

function Toggle<T extends string>({
  choice,
  pressed,
  onClick
}: {
  choice: Choice<T>
  pressed: boolean
  onClick: () => void
}) {
  return (
    <label className="option">
      <input className="sr-only" type="checkbox" checked={pressed} onChange={onClick} />
      <span className="option-label">
        <span lang="und">{choice.label}</span>
        {choice.note && <span className="option-note">{choice.note}</span>}
      </span>
      <Tick on={pressed} />
    </label>
  )
}

function Radio<T extends string | number>({
  name,
  choice,
  checked,
  onClick
}: {
  name: string
  choice: Choice<T>
  checked: boolean
  onClick: () => void
}) {
  return (
    <label className="option">
      <input className="sr-only" type="radio" name={name} checked={checked} onChange={onClick} />
      <span className="option-label">
        {choice.label}
        {choice.note && <span className="option-note">{choice.note}</span>}
      </span>
      <Tick on={checked} />
    </label>
  )
}

function Tick({ on }: { on: boolean }) {
  if (!on) return null
  return (
    <span className="option-tick">
      <span aria-hidden="true">✓</span>
      <span className="sr-only">Selected</span>
    </span>
  )
}
