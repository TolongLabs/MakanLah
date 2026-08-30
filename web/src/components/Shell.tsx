import { type ReactNode, useCallback, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { loadSession, saveSession, signOut } from '../auth'
import { Chop } from './Chop'
import { MenuIcon } from './MenuIcon'
import { NavDrawer } from './NavDrawer'
import { ThemeSwitch } from './ThemeSwitch'

export function Shell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const drawerToggleRef = useRef<HTMLButtonElement>(null)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
  const navigate = useNavigate()
  // Re-read on navigation. Signing in navigates, so the nav is never a route behind,
  // and this costs less than a context for one value read in one place.
  const session = loadSession()
  void location.key
  // The landing is a different bar, not the same bar with a different link in it.
  const selling = location.pathname === '/'

  return (
    <div className="shell">
      <header className="nav">
        <div className="nav-inner">
          {/* Leftmost, and it REPLACES the wordmark rather than sitting beside it.
              Two brand marks on one bar -- the chop in the nav and the chop in the
              drawer it opens -- said the same thing twice and pushed the one
              control that does something to the far side of the screen. */}
          {selling ? (
            <Link className="wordmark" to="/">
              <Chop size={26} />
              <span className="wordmark-name">MakanLah</span>
            </Link>
          ) : (
            <button
              type="button"
              ref={drawerToggleRef}
              className="nav-drawer-toggle nav-drawer-toggle-lead"
              data-nav-drawer-toggle
              onClick={() => setDrawerOpen((open) => !open)}
              aria-expanded={drawerOpen}
              aria-controls="nav-drawer"
              aria-label="Menu"
            >
              <MenuIcon />
            </button>
          )}
          <nav className="nav-links" aria-label="Main">
            <ThemeSwitch />
            {/* THE LANDING CTA IS INVARIANT. Same label, same place, whatever the
                auth state, the scroll position or anything else -- a page whose one
                job is to start you must not move or rename its own door. Where it
                GOES changes, because sending somebody who is already signed in back
                to a sign-up form is a dead end wearing the right label. */}
            {selling ? (
              <Link className="btn btn-primary nav-cta" to={session ? '/taste' : '/sign-up'}>
                Get Started
              </Link>
            ) : session ? (
              <button
                type="button"
                className="btn btn-quiet nav-cta"
                onClick={() => {
                  void signOut(session.token)
                  saveSession(null)
                  navigate('/')
                }}
              >
                Sign Out
              </button>
            ) : (
              <Link className="btn btn-primary nav-cta" to="/sign-up">
                Get Started
              </Link>
            )}
          </nav>
        </div>
      </header>
      <NavDrawer open={drawerOpen} onClose={closeDrawer} toggleRef={drawerToggleRef} />
      <main>{children}</main>
      {/* Right aligned and stacked: mark, name, one line, one link. A footer is the last
          thing between a visitor and leaving, and the old one spent four lines
          restating the product to somebody already on their way out. */}
      <footer className="foot" role="contentinfo">
        <div className="foot-inner">
          <Link className="foot-brand" to="/" aria-label="MakanLah home">
            <Chop size={30} />
            <span className="foot-name">MakanLah</span>
          </Link>
          <p className="foot-motto">Recommendations you can trace.</p>
          <Link className="foot-link" to="/privacy">
            Privacy
          </Link>
        </div>
      </footer>
    </div>
  )
}
