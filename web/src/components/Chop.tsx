/**
 * The mark. A hanko chop reading "lah" in squared seal script.
 *
 * Inline rather than an <img> for two reasons that both matter: it inherits
 * currentColor, so one component serves cinnabar in the nav, paper on a dark ground
 * and ink in print without three files; and at 300 bytes it costs less than the
 * request it would otherwise make.
 *
 * The letterforms are on a strict grid -- stroke 9, counters 8-13, three columns at
 * 18/38/22 with 4 between. The `a` is double-storey on purpose: a squared ring reads
 * as an o, and the first version of this mark spelled "loh".
 */
const LETTERS =
  'M17 18h9v64h-9z M31 38h26v9H31z M31 47h9v13h-9z M31 60h26v9H31z ' +
  'M48 38h9v44h-9z M61 18h9v64h-9z M70 38h13v9H70z M74 47h9v35h-9z'

export function Chop({ size = 28, outline = false }: { size?: number; outline?: boolean }) {
  return (
    <svg
      className="chop"
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      {outline ? (
        <>
          <path fillRule="evenodd" d="M0 0h100v100H0z M9 9v82h82V9z" />
          <path d={LETTERS} />
        </>
      ) : (
        <path fillRule="evenodd" d={`M0 0h100v100H0z ${LETTERS}`} />
      )}
    </svg>
  )
}
