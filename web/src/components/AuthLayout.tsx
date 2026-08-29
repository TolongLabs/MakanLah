import type { ReactNode } from 'react'
import { Chop } from './Chop'

/**
 * The dual-pane frame both auth routes sit in, modelled on the pattern in the owner's
 * SolarSim app: a brand panel on the left, the form on the right, and the panel gone
 * below the breakpoint rather than stacked.
 *
 * It disappears rather than stacking on purpose. A decorative image pushed above a
 * sign-in form on a phone costs a screenful of scrolling before the first field, which
 * is the one place in the product where getting to the input fast is the whole job.
 *
 * The image is the one generated asset that carries no evidence claim. It names no
 * venue and quotes nobody, so it cannot be mistaken for a cited dish -- the same
 * carve-out the closing band on the landing page already uses. It never goes near a
 * result.
 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth-split">
      <aside className="auth-brand">
        <picture>
          <source media="(max-width: 80rem)" srcSet="/brand/auth-hero-small.webp" />
          <img className="auth-brand-image" src="/brand/auth-hero.webp" alt="" width={1000} height={1333} />
        </picture>
        <div className="auth-brand-copy">
          <span className="auth-brand-mark">
            <Chop size={34} />
          </span>
          <p className="auth-brand-line">Somebody already ate there.</p>
          <p className="auth-brand-sub">Every pick carries the post it came from.</p>
        </div>
      </aside>
      <div className="auth-pane">{children}</div>
    </div>
  )
}
