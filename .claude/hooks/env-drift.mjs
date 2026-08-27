#!/usr/bin/env node
// SessionStart: report a local .env that disagrees with the repository.
//
// .env is gitignored, so no diff and no reviewer can catch a stale base URL, a
// dead session path, or a worker key that lapsed on one of the two 2026-09
// cliffs. Two comparisons, neither covering the other: .env against
// .env.example, and, inside a linked worktree, .env against the main
// checkout's .env.
//
// Never prints a value from .env. Exits 0 on any internal failure.

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const git = (cwd, ...args) => {
  try {
    return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return ''
  }
}

const read = (path) => {
  try {
    return readFileSync(path, 'utf8')
  } catch {
    return null
  }
}

// Mirrors dotenv, which is what actually loads this file: quotes delimit the
// value, an unquoted value ends at the first inline comment. Diverging would
// report a difference the running app does not see.
const parseEnv = (text) => {
  const out = new Map()
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq < 1) continue
    const key = line.slice(0, eq).replace(/^export\s+/, '').trim()
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue
    let value = line.slice(eq + 1).trim()
    const quote = value.length > 1 && (value[0] === '"' || value[0] === "'") ? value[0] : ''
    if (quote) {
      const close = value.indexOf(quote, 1)
      value = close === -1 ? value.slice(1) : value.slice(1, close)
    } else {
      value = value.split(/\s+#/)[0].trim()
    }
    out.set(key, value)
  }
  return out
}

// Safe to compare by value only where .env.example assigns one: the example is
// tracked, so its values are already public. The secret is the empty entry.
const isPublic = (v) => v !== '' && !(v.includes('<') && v.includes('>'))

const vsExample = (local, example) =>
  [...example]
    .filter(([k, v]) => isPublic(v) && local.has(k) && local.get(k) !== v)
    .map(([k, v]) => `  ${k} (.env.example pins ${v})`)

const vsMain = (local, main) =>
  [...new Set([...local.keys(), ...main.keys()])]
    .map((k) => {
      if (!main.has(k)) return `  ${k} (set here, absent there)`
      if (!local.has(k)) return `  ${k} (absent here, set there)`
      return local.get(k) === main.get(k) ? null : `  ${k} (differs)`
    })
    .filter(Boolean)
    .sort()

// A linked worktree needs both git-dir and common-dir to differ; a submodule
// looks the same, hence the superproject guard.
const mainCheckoutRoot = (root) => {
  if (git(root, 'rev-parse', '--show-superproject-working-tree')) return null
  const gitDir = git(root, 'rev-parse', '--absolute-git-dir')
  const commonDir = git(root, 'rev-parse', '--git-common-dir')
  if (!gitDir || !commonDir) return null
  const common = resolve(root, commonDir)
  return gitDir === common ? null : dirname(common)
}

const main = () => {
  const root = process.env.CLAUDE_PROJECT_DIR || git(process.cwd(), 'rev-parse', '--show-toplevel') || process.cwd()
  const localText = read(resolve(root, '.env'))
  if (localText === null) return

  const local = parseEnv(localText)
  const sections = []

  const exampleText = read(resolve(root, '.env.example'))
  if (exampleText !== null) {
    const found = vsExample(local, parseEnv(exampleText))
    if (found.length) sections.push(`Your .env overrides a value the repository pins:\n${found.join('\n')}`)
  }

  const mainRoot = mainCheckoutRoot(root)
  // An empty .env there is still a real disagreement, so test against null, not truthiness.
  const mainText = mainRoot === null ? null : read(resolve(mainRoot, '.env'))
  if (mainText !== null) {
    const found = vsMain(local, parseEnv(mainText))
    if (found.length) sections.push(`This worktree disagrees with the main checkout at ${mainRoot}:\n${found.join('\n')}`)
  }

  if (!sections.length) return

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'SessionStart',
        additionalContext: [
          '.env drift detected. Values from .env are deliberately not shown.',
          '',
          sections.join('\n\n'),
          '',
          'Each line may be a deliberate local override or a stale copy. Tell the user what',
          'disagrees and let them decide; do not edit .env to resolve it.'
        ].join('\n')
      }
    })
  )
}

try {
  main()
} catch {
  // Unreadable file, missing git, anything: stay out of the way.
}
process.exit(0)
