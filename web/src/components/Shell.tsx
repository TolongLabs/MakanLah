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

  return (
    <div className="shell">
      <header className="nav">
        <div className="nav-inner">
          <Link className="wordmark" to="/">
            <Chop size={26} />
            <span className="wordmark-name">MakanLah</span>
          </Link>
          {/* The bar carries ONE action, and which one depends on where you are.
              The landing sells, so it offers Get Started and nothing that competes
              with it -- a Discover link beside it is a second door out of a page
              whose only job is the first one. Once you are inside, the only thing
              the bar owes you is a way out. */}
          <nav className="nav-links" aria-label="Main">
            <button
              type="button"
              ref={drawerToggleRef}
              className="nav-drawer-toggle"
              data-nav-drawer-toggle
              onClick={() => setDrawerOpen((open) => !open)}
              aria-expanded={drawerOpen}
              aria-controls="nav-drawer"
              aria-label="Menu"
            >
              <MenuIcon />
            </button>
            <ThemeSwitch />
            {session ? (
              <>
                {/* The shared guest has to stay visible. Disclosing it once at the
                    sign-in and never again would let somebody forget, mid-session,
                    that every other guest can see what they are doing. */}
                {session.user.shared ? (
                  <span className="nav-account nav-account-shared">Guest, Shared</span>
                ) : (
                  <span className="nav-account">{session.user.email ?? 'Signed In'}</span>
                )}
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
              </>
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
