import type { Citation } from '../api'
import { sourceLabel } from '../format'

/**
 * An excerpt and the post it came from, welded together. They are one component
 * because docs/DESIGN.md makes the citation the point rather than a footnote, and a
 * quote that can drift away from its attribution is how the trail gets broken.
 */
export function Testimony({ citation, large = false }: { citation: Citation; large?: boolean }) {
  const { excerpt, post_url, platform, author_handle, posted_at } = citation
  return (
    <figure className="testimony">
      {excerpt && (
        <blockquote className={large ? 'excerpt excerpt-lg' : 'excerpt'} lang="und">
          {excerpt}
        </blockquote>
      )}
      <figcaption>
        <a className="chip" href={post_url} target="_blank" rel="noreferrer noopener">
          {sourceLabel(platform, author_handle)}
          {posted_at ? ` · ${posted_at}` : ''}
        </a>
      </figcaption>
    </figure>
  )
}
