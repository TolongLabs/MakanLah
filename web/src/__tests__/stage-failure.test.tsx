import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Break the subject on purpose: the ONE request for the lazy mascot chunk fails.
 *
 * Measured on prod with a control, single variable. Chunk allowed: 4 step panels,
 * 4 options, onboarding usable. Only the chunk aborted: **bodyLen 0, zero panels,
 * zero options**, with
 *
 *   TypeError: Failed to fetch dynamically imported module: .../MascotStage-*.js
 *
 * `React.lazy` plus `Suspense` does not catch a REJECTED import -- Suspense handles
 * the pending promise, not the failed one. The rejection throws during render and,
 * with no error boundary above it, React unmounts the tree. So a decorative
 * component's network failure took down the screen every guest must complete.
 *
 * The realistic launch-day trigger is not exotic: a redeploy leaves a client holding
 * an index.html that references a chunk hash which no longer exists. Also a flaky
 * mobile connection, a CDN edge miss, or a proxy. The user sees white, silently.
 *
 * A test asserting the mascot mounts when the chunk loads cannot fail on any of
 * that, which is why this file exists and why the module is made to reject.
 */
vi.mock('../live2d/MascotStage', () => {
  throw new TypeError('Failed to fetch dynamically imported module')
})

import { AskCompanion } from '../components/AskCompanion'
import { Taste } from '../routes/Taste'

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('navigator', { ...navigator, geolocation: undefined })
  // matchMedia decides whether the stage mounts at all. Wide, so it does: the point
  // is the failure path, and at phone width there is nothing to fail.
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: true,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {}
  }))
})

describe('when the mascot chunk cannot be fetched', () => {
  it('still renders onboarding', async () => {
    render(
      <MemoryRouter>
        <Taste />
      </MemoryRouter>
    )
    // The question is the screen. If this is absent, a guest has no way in.
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeTruthy())
  })

  it('still offers options to pick', async () => {
    const { container } = render(
      <MemoryRouter>
        <Taste />
      </MemoryRouter>
    )
    await waitFor(() => expect(container.querySelectorAll('.step-panel').length).toBeGreaterThan(0))
    expect(container.querySelectorAll('.step-panel:not([hidden]) .option').length).toBeGreaterThan(0)
  })

  it('keeps her line, because the reading is the information and the face is not', async () => {
    render(
      <MemoryRouter>
        <Taste />
      </MemoryRouter>
    )
    await waitFor(() => expect(document.querySelector('.companion-bubble')?.textContent?.trim()).toBeTruthy())
  })

  it('leaves the results companion usable too', async () => {
    render(<AskCompanion evidence="single" degraded={false} phase="picks" />)
    await waitFor(() => expect(screen.getByText(/Only one post backs this/i)).toBeTruthy())
    expect(screen.getByText(/Tap Ask on any pick/i)).toBeTruthy()
  })
})
