/**
 * Where the place is, from an image the ingestion pass already fetched.
 *
 * **`docs/DESIGN.md` bans images beside a cited result, and this is a deliberate
 * fourth exception rather than an oversight.** The ban exists because a generated or
 * stock photograph of food, sitting next to evidence, would be a fabricated image on
 * the screen whose whole claim is that nothing here is fabricated. Every allowed
 * exception passes the same test: it cannot be mistaken for evidence.
 *
 * A map passes it. It depicts a location, not an opinion, and says nothing about
 * whether the food is good — which is the only thing the citations are evidence
 * *of*. **And the product already stakes more on these coordinates than this does**:
 * every card prints "9.4 km" from the same geocode and the whole list is ordered by
 * it. If the pin is wrong, the distance was already wrong. This makes an existing
 * claim visible rather than adding a new one.
 *
 * **The tiles are NOT fetched here, and that was a correction.** The first version
 * built the slippy-tile maths and pulled OSM rasters from the browser on every
 * dialog open. It worked. It was still wrong: OSM's tile usage policy is explicit
 * about bulk use by applications, and shipping a third-party tile request to every
 * viewer of every venue is a rate-limit exposure on infrastructure we neither own
 * nor pay for. `makanlah-13` objected and the objection was right — I had weighed
 * this against the corpus rule ("never fetch live on a user request") and argued
 * imagery was exempt, which missed that the binding constraint was somebody else's
 * terms rather than our own architecture.
 *
 * So the image is fetched once per venue at ingestion and served from our side.
 * Attribution still travels with it, because the tiles are still OSM's.
 *
 * Renders nothing until that field exists, which is the same bargain every optional
 * field on `Venue` gets: absent is a normal state, not an error, and a missing map
 * costs the dialog nothing.
 */
export function MapPreview({
  src,
  name,
  href,
  width = 320,
  height = 150
}: {
  /** Stored at ingestion. Absent for a venue with no geocode, or before the
      ingestion pass has run over it. */
  src: string | null | undefined
  name: string
  /** Google Maps. The image is the picture; the link is still how you get there. */
  href: string
  width?: number
  height?: number
}) {
  if (!src) return null

  return (
    <figure className="mapshot" style={{ width, height }}>
      <a className="mapshot-frame" href={href} target="_blank" rel="noreferrer noopener">
        {/* Real text rather than an aria-label. Everything else inside this anchor is
            decorative and hidden, so without it the link announces as its own URL --
            and a label attribute is dropped by translation tooling in a way node
            text is not, on a product whose users read three languages. */}
        <span className="sr-only">{`Open ${name} in Google Maps`}</span>
        <img className="mapshot-img" src={src} alt="" aria-hidden="true" loading="lazy" decoding="async" />
        <span className="mapshot-pin" aria-hidden="true" />
      </a>
      {/* Required by the OSM tile usage policy wherever the tiles are served from. */}
      <figcaption className="mapshot-credit">
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer noopener">
          © OpenStreetMap
        </a>
      </figcaption>
    </figure>
  )
}
