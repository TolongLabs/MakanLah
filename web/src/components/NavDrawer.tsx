import { useEffect, useRef } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { loadSession, saveSession, signOut } from '../auth'
import { Chop } from './Chop'

function focusable(root: HTMLElement): HTMLElement[] {
  const nodes = Array.from(
    root.querySelectorAll<HTMLElement>('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])')
  )
  return nodes.filter(
    (el) =>
      !el.hasAttribute('disabled') &&
      !el.hasAttribute('inert') &&
      !el.closest('[inert]') &&
      el.getAttribute('aria-hidden') !== 'true'
  )
}

export function NavDrawer({
  open,
  onClose,
  toggleRef
}: {
  open: boolean
  onClose: () => void
  toggleRef: React.RefObject<HTMLButtonElement | null>
}) {
  const drawerRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const navigate = useNavigate()
  const session = loadSession()
  const wasOpenRef = useRef(false)

  // biome-ignore lint/correctness/useExhaustiveDependencies: close drawer on route change
  useEffect(() => {
    onClose()
  }, [location.key])

  useEffect(() => {
    if (!open) return
    const drawer = drawerRef.current
    if (!drawer) return

    const first = focusable(drawer)[0]
    first?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const elements = focusable(drawer)
      const firstEl = elements[0]
      const lastEl = elements[elements.length - 1]
      if (!firstEl || !lastEl) return
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault()
        lastEl.focus()
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault()
        firstEl.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    const original = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = original
    }
  }, [open, onClose])

  useEffect(() => {
    if (open) {
      wasOpenRef.current = true
    } else if (wasOpenRef.current) {
      wasOpenRef.current = false
      toggleRef.current?.focus()
    }
  }, [open, toggleRef])

  const onBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose()
  }

  function handleSignOut() {
    if (!session) return
    void signOut(session.token)
    saveSession(null)
    navigate('/')
    onClose()
  }

  return (
    <div
      ref={drawerRef}
      id="nav-drawer"
      data-nav-drawer
      className={`nav-drawer${open ? ' is-open' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-label="Site menu"
      aria-hidden={!open}
      inert={!open}
      onClick={onBackdropClick}
    >
      <div ref={panelRef} className="nav-drawer-panel" onClick={(e) => e.stopPropagation()} aria-hidden={!open}>
        <div className="nav-drawer-head">
          <Link className="wordmark" to="/" onClick={onClose}>
            <Chop size={26} />
            <span className="wordmark-name">MakanLah</span>
          </Link>
        </div>
        <nav className="nav-drawer-nav" aria-label="Mobile">
          {session && (
            <NavLink className="nav-drawer-link" to="/dashboard" onClick={onClose}>
              Dashboard
            </NavLink>
          )}
          <NavLink className="nav-drawer-link" to="/discover" onClick={onClose}>
            Discover
          </NavLink>
          {/* The wizard had exactly one route into it from inside the app: an inline
              "Change" link inside a sentence that only rendered once you already had
              answers. The owner could not find it. This is the durable door. */}
          <NavLink className="nav-drawer-link" to="/taste" onClick={onClose}>
            Your Taste
          </NavLink>
          {/* Get Started is NOT repeated here. The topbar carries it, and the
              drawer sat directly under that topbar offering the same action a
              second time. Owner decision, 2026-08-30. */}
          {!session && (
            <NavLink className="nav-drawer-link" to="/sign-in" onClick={onClose}>
              Sign In
            </NavLink>
          )}
        </nav>
        <div className="nav-drawer-footer">
          {/* No shared-guest disclosure anywhere in the product now. The topbar
              label went, then the sign-in consent copy, and the owner was asked
              directly about this last one and said to remove it too. Recorded
              because it is a deliberate decision rather than an omission: a guest
              is no longer told that other guests can see what they are doing. */}
          {/* Sign Out belongs to the account, so it sits under the account it signs
              out of rather than in the navigation list above, where it read as a
              destination alongside Discover and Your Taste.

              The theme switch is gone for the same reason Get Started is: the
              topbar has one, and two controls for one setting is two places to
              wonder which is authoritative. */}
          {session && (
            <>
              <p className="nav-drawer-signed-in">{session.user.email ?? 'Signed In'}</p>
              <button type="button" className="nav-drawer-link nav-drawer-action" onClick={handleSignOut}>
                Sign Out
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
