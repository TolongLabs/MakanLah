import type { Citation } from '../api'
import { sourceLabel } from '../format'

/**
 * An excerpt and the post it came from, welded together. They are one component
 * because docs/DESIGN.md makes the citation the point rather than a footnote, and a
 * quote that can drift away from its attribution is how the trail gets broken.
 */
export function Testimony({
  citation,
  large = false,
  attributed = true,
  href
}: {
  citation: Citation
  large?: boolean
  /** Overrides the citation's own URL. Used for Google Maps, where the corpus can
      only store a name search and the venue carries an exact place_id link. */
  href?: string
  /** False where the surrounding layout already names the platform and date, so the
      chip would print both a second time. The link still has to be here: an excerpt
      you cannot open is the thing this product exists not to show. */
  attributed?: boolean
}) {
  const { excerpt, post_url, platform, author_handle, posted_at } = citation
  const to = href ?? post_url
  return (
    <figure className="testimony">
      {excerpt && (
        <blockquote className={large ? 'excerpt excerpt-lg' : 'excerpt'} lang="und">
          {excerpt}
        </blockquote>
      )}
      {!attributed && (
        <figcaption className="attribution">
          <a className="link" href={to} target="_blank" rel="noreferrer noopener">
            Read The Post
          </a>
          {author_handle && <span className="posted">{author_handle}</span>}
        </figcaption>
      )}
      {/* Platform and author in the chip, date beside it. Folding the date in made the
          pill long enough to ellipsis on a phone, and what got cut was the attribution. */}
      {attributed && (
        <figcaption className="attribution">
          <a className="chip" href={to} target="_blank" rel="noreferrer noopener">
            {sourceLabel(platform, author_handle)}
          </a>
          {posted_at && <span className="posted">{posted_at}</span>}
        </figcaption>
      )}
    </figure>
  )
}
