import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'

export function Shell({ children }: { children: ReactNode }) {
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
            <NavLink className="nav-link" to="/sign-in">
              Sign In
            </NavLink>
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
          <p>Kuala Lumpur</p>
        </div>
      </footer>
    </div>
  )
}
