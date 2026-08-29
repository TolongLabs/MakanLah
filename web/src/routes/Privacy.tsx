/**
 * What we hold and what we do not.
 *
 * Written because the footer links here, and a Privacy link that 404s is worse than
 * no link at all. Kept to what is actually true of this build rather than padded into
 * a policy: the app has no analytics, no third-party scripts and no server-side
 * profile, and saying so plainly is more useful than a page of hedged boilerplate.
 *
 * If any of that changes, this page changes in the same PR.
 */
export function Privacy() {
  return (
    <div className="page prose-page">
      <h1 className="h-page">Privacy</h1>
      <p className="section-lede">
        Short, because there is not much to tell. If that stops being true, this page changes in the same pull request
        that makes it untrue.
      </p>

      <h2 className="h-section">What Stays On Your Device</h2>
      <p>
        Your taste answers and your theme choice are kept in your browser&rsquo;s local storage. They are not sent
        anywhere, and clearing your browser data removes them. The taste wizard writes nothing at all until you reach
        the final step.
      </p>

      <h2 className="h-section">Accounts</h2>
      <p>
        An account stores an email address and a session token, and nothing else. You can use the whole product without
        one. The guest account is deliberately shared, which means anyone else using it can see the same saved
        preferences, and the sign-in screen says so before you choose it.
      </p>

      <h2 className="h-section">What We Do Not Collect</h2>
      <p>
        No analytics, no advertising identifiers, no third-party scripts, no cookies beyond the session you create by
        signing in. Nothing on this site tracks you between visits.
      </p>

      <h2 className="h-section">Other People&rsquo;s Posts</h2>
      <p>
        Recommendations quote posts written by other people on RedNote and Google Maps. We show an excerpt as written,
        in the language it was written in, name the platform and the date, and link back to the original so you can read
        it in full at the source. Author handles are not republished. If you wrote something quoted here and want it
        removed, the link on the citation goes to the post, and we will remove it on request.
      </p>
    </div>
  )
}
