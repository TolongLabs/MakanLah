import type { ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { loadSession, saveSession, signOut } from '../auth'

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
            MakanLah
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
            <Link className="btn btn-primary nav-cta" to="/taste">
              Find Food
            </Link>
          </nav>
        </div>
      </header>
      <main>{children}</main>
      <footer className="foot">
        <div className="foot-inner">
          <p>
            Recommendations are drawn from posts written by other people. We show them as written, in the language they
            were written in, and link back to the original.
          </p>
        </div>
      </footer>
    </div>
  )
}
