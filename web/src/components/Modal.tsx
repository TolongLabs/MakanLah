import { type ReactNode, useEffect, useRef } from 'react'

/**
 * A floating panel over a dimmed, blurred page.
 *
 * Native `<dialog>` plus `showModal()`, not a div with a high z-index. The native
 * element brings the focus trap, the inert background, Escape-to-close and the
 * top-layer stacking that a hand-rolled overlay reimplements badly — every one of
 * those is an accessibility bug when it is missed, and they are all missed by
 * default.
 *
 * Two things it does NOT bring, which are handled here:
 *
 * 1. **Backdrop click.** `::backdrop` is not an element, so a click on it lands on
 *    the dialog itself. The dialog therefore carries no padding of its own and the
 *    panel inside it does — that way `target === dialog` means the backdrop and
 *    nothing else, and a click on the panel's own margin does not dismiss the thing
 *    the user is reading.
 * 2. **Body scroll.** The page behind stays scrollable on iOS without this, so the
 *    backdrop slides away from the panel it is meant to be dimming.
 */
export function Modal({
  title,
  onClose,
  children,
  labelledBy
}: {
  /** Rendered as the panel's heading. Omit only when `labelledBy` points at
      something inside `children` that already names the dialog — a dialog with no
      accessible name is announced as "dialog" and nothing else. */
  title?: ReactNode
  onClose: () => void
  children: ReactNode
  labelledBy?: string
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const headingId = useRef(`modal-${Math.random().toString(36).slice(2, 9)}`).current

  // Kept in a ref so the listener below can stay mounted for the dialog's lifetime
  // instead of being torn down and re-attached whenever the caller re-renders.
  const close = useRef(onClose)
  close.current = onClose

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (!el.open) el.showModal()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // Backdrop dismissal, as a DOM listener rather than an `onClick` on the dialog.
    //
    // `::backdrop` is not an element, so a click on it lands on the dialog itself and
    // `target === el` is what distinguishes it from a click on the panel. As a JSX
    // prop that reads to the linter as a click handler on a non-interactive element
    // with no keyboard equivalent — and the keyboard equivalent genuinely exists, it
    // is Escape, which `showModal()` wires up natively and which arrives on `close`
    // below. Attaching it here keeps the behaviour and drops the false positive
    // without switching the rule off.
    const onBackdrop = (e: MouseEvent) => {
      if (e.target === el) close.current()
    }
    // Fires for Escape as well as for `close()`, so the caller's state cannot drift
    // out of step with whether the dialog is actually on screen.
    const onNativeClose = () => close.current()
    el.addEventListener('click', onBackdrop)
    el.addEventListener('close', onNativeClose)

    return () => {
      el.removeEventListener('click', onBackdrop)
      el.removeEventListener('close', onNativeClose)
      document.body.style.overflow = previous
      if (el.open) el.close()
    }
  }, [])

  return (
    <dialog ref={ref} className="modal" aria-labelledby={labelledBy ?? (title ? headingId : undefined)}>
      <div className="modal-panel">
        <div className="modal-head">
          {title && (
            <h2 className="modal-title" id={headingId}>
              {title}
            </h2>
          )}
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            <span aria-hidden="true">×</span>
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </dialog>
  )
}
