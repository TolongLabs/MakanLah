// lint-staged passes staged paths straight to each command, which bypasses the
// `includes` exclusions in biome.json and pyproject.toml. That matters for one
// directory: docs/source/ is the verbatim record and AGENTS.md forbids
// reformatting it. A config function is the only place that filter can live.

const VERBATIM = /^docs\/source\//
const keep = (files, re) => files.filter((f) => re.test(f) && !VERBATIM.test(f))

export default {
  '*': (files) => {
    const web = keep(files, /\.(ts|tsx|js|jsx|mjs|cjs|json|jsonc|css|html)$/)
    const docs = keep(files, /\.(md|markdown|ya?ml)$/)
    const py = keep(files, /\.py$/)
    return [
      web.length && `biome check --write --no-errors-on-unmatched ${web.join(' ')}`,
      docs.length && `prettier --write ${docs.join(' ')}`,
      py.length && `uv tool run ruff@latest check --fix ${py.join(' ')}`,
      py.length && `uv tool run ruff@latest format ${py.join(' ')}`
    ].filter(Boolean)
  }
}
