// Writes dist/build.json so the deployed site can state which commit it is.
//
// The alternative -- rebuild main in CI and compare bundle hashes against the live
// ones -- makes the check hostage to build determinism, and a probe that cries stale
// because a hash moved for an unrelated reason is a probe everyone learns to ignore.
// A stamp is a fact the build asserts about itself, and reading it back is not a
// second opinion about the same computation.

import { execSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'

function commit() {
  // GITHUB_SHA on a push to main is the commit being deployed. Locally there is no
  // such variable and git is the only source; neither existing is a real state on a
  // machine that unpacked a tarball, and 'unknown' reads better than a crash.
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA
  try {
    return execSync('git rev-parse HEAD', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return 'unknown'
  }
}

const stamp = { commit: commit(), built_at: new Date().toISOString() }
writeFileSync(new URL('../dist/build.json', import.meta.url), `${JSON.stringify(stamp, null, 2)}\n`)
console.log(`stamped dist/build.json  ${stamp.commit}  ${stamp.built_at}`)
