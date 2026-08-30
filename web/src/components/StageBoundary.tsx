import { Component, type ErrorInfo, type ReactNode } from 'react'

/**
 * Keeps a decorative component's failure from taking the screen with it.
 *
 * `React.lazy` plus `Suspense` handles a PENDING import, not a REJECTED one. A
 * failed chunk fetch throws during render, and with nothing catching it React
 * unmounts the tree — so one aborted request for the 508 KB mascot chunk left
 * `/taste`, the screen every guest must complete, rendering **zero step panels
 * and zero options**. Measured with a control: same viewport, same run, the only
 * variable that one request.
 *
 * The realistic trigger is mundane. A redeploy leaves a client holding an
 * `index.html` that names a chunk hash which no longer exists; a mobile
 * connection drops one request; a proxy or a CDN edge misses. The user sees
 * white and nothing is logged.
 *
 * It catches render errors from inside the stage as well, which is the same
 * bargain: pixi and Cubism are the least trustworthy code in this client and the
 * least important thing on the page.
 *
 * The degraded layout is not new and does not need designing. She is already
 * absent below the stage breakpoint by design, so "no mascot" is a configuration
 * that already ships and is already tested.
 */
export class StageBoundary extends Component<{ onFail: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Reported, not swallowed. A silently absent mascot is how the framing bug
    // survived to production once already: every asset returned 200, the WebGL
    // context was live, and nothing was drawn.
    console.error('mascot stage failed, continuing without her', error, info.componentStack)
    this.props.onFail()
  }

  render() {
    return this.state.failed ? null : this.props.children
  }
}
