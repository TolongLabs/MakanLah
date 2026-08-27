export function distance(m: number | null): string | null {
  if (m == null) return null
  if (m < 950) return `${Math.round(m / 10) * 10} m`
  return `${(m / 1000).toFixed(m < 9500 ? 1 : 0)} km`
}

/** Names and dishes render in the script the writer used. Never translated. */
export function dishLine(dishes: string[], max = 3): string | null {
  if (!dishes.length) return null
  const shown = dishes.slice(0, max).join(', ')
  return dishes.length > max ? `${shown} +${dishes.length - max}` : shown
}

export function sourceLabel(platform: string, author: string | null): string {
  const p = platform === 'rednote' ? 'RedNote' : platform === 'google_maps' ? 'Google Maps' : platform
  return author ? `${p} · ${author}` : p
}
