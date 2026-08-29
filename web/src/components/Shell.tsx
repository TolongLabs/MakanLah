import type { ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { loadSession, saveSession, signOut } from '../auth'
import { Chop } from './Chop'

export function Shell({ children }: { children: ReactNode }) {
  const location = useLocation()
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
          <nav className="nav-links" aria-label="Main">
            <NavLink className="nav-link" to="/discover">
              Discover
            </NavLink>
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
                  className="nav-link nav-signout"
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
              <NavLink className="nav-link" to="/sign-in">
                Sign In
              </NavLink>
            )}
            <Link className="btn btn-primary nav-cta" to="/sign-up">
              Get Started
            </Link>
          </nav>
        </div>
      </header>
      <main>{children}</main>
      {/* Centred and stacked: mark, name, one line, one link. A footer is the last
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
