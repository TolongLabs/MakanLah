import { useEffect, useRef } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { loadSession, saveSession, signOut } from '../auth'
import { Chop } from './Chop'
import { ThemeSwitch } from './ThemeSwitch'

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
          <NavLink className="nav-drawer-link" to="/discover" onClick={onClose}>
            Discover
          </NavLink>
          {session ? (
            <>
              <button type="button" className="nav-drawer-link nav-drawer-action" onClick={handleSignOut}>
                Sign Out
              </button>
              <Link className="btn btn-primary nav-drawer-cta" to="/discover" onClick={onClose}>
                Get Started
              </Link>
            </>
          ) : (
            <>
              <NavLink className="nav-drawer-link" to="/sign-in" onClick={onClose}>
                Sign In
              </NavLink>
              <Link className="btn btn-primary nav-drawer-cta" to="/sign-up" onClick={onClose}>
                Get Started
              </Link>
            </>
          )}
        </nav>
        <div className="nav-drawer-footer">
          <ThemeSwitch />
        </div>
      </div>
    </div>
  )
}
