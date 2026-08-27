# Agent Skills

`.agents/skills/` is the canonical, tool-agnostic skill directory; `.claude/skills/` symlinks into it. **`impeccable` is
the one exception** and lives in `.claude/skills/` as a real directory, because `.claude/settings.json` wires a hook to
`scripts/hook.mjs` inside it.

**30 skills.** 29 in `.agents/skills/` — 14 superpowers, 8 business, 3 taste, 4 utility — plus `impeccable`. All
optional: invoke one when the task matches, not as a checkpoint before every action.

---

## Sources

29 of the 30 are tracked in [`../../skills-lock.json`](../../skills-lock.json).

| Source                                                                                    | Skills                                                                                                               |
| ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| [`obra/superpowers`](https://github.com/obra/superpowers)                                 | The 14 superpowers                                                                                                   |
| [`Leonxlnx/taste-skill`](https://github.com/Leonxlnx/taste-skill)                         | `design-taste-frontend`, `high-end-visual-design`, `image-to-code`                                                   |
| [`phuryn/pm-skills`](https://github.com/phuryn/pm-skills)                                 | `competitor-analysis`, `strategy-red-team`, `beachhead-segment`, `lean-canvas`, `market-sizing`, `value-proposition` |
| [`ailabs-393/ai-labs-claude-skills`](https://github.com/ailabs-393/ai-labs-claude-skills) | `startup-validator`                                                                                                  |
| [`owl-listener/designer-skills`](https://github.com/owl-listener/designer-skills)         | `jobs-to-be-done`                                                                                                    |
| [`graphify-labs/graphify`](https://github.com/graphify-labs/graphify)                     | `graphify`                                                                                                           |
| [`mattpocock/skills`](https://github.com/mattpocock/skills)                               | `handoff`, `diagnosing-bugs`                                                                                         |
| [`pbakaus/impeccable`](https://github.com/pbakaus/impeccable)                             | `impeccable`                                                                                                         |

Sources were identified by **content diff**, not by name: `jobs-to-be-done` had three same-named registry candidates at
1.3%, 1.0% and 99.9% similarity.

`diagnosing-bugs` was renamed from `diagnose` to its upstream name. At 73% it is the weakest match of the set: a best
guess, not a confirmed one.

**`claude-in-chrome` is the one untracked skill.** It has no reachable upstream and this copy is the only one that
exists. Recover it from git history if it is ever deleted.

---

## Installing And Updating

```bash
bunx skills add <owner/repo> -a claude-code -s <skill> -s <skill> -y
```

Four things the CLI does that this layout does not want:

| Behaviour                                                    | What To Do                                                                                                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `-s a,b,c` silently matches nothing                          | Pass **one `-s` per skill**. A comma list fails with "No matching skills found"                                                       |
| Installs to `.claude/skills/<name>/` as a **real directory** | Move it to `.agents/skills/<name>/`, then `ln -s ../../.agents/skills/<name> .claude/skills/<name>`                                   |
| Installs **every** skill in the repo without `-s`            | Always pass `-s`. `phuryn/pm-skills` carries 68, `owl-listener/designer-skills` over 100. A long skill list makes an agent pick worse |
| `-a universal` writes the gitignored `/agent/` tree          | Never use it. `-a claude-code` only                                                                                                   |

`impeccable` is the exception to the relocation: it stays a real directory, because that is where its hook path points.

**After any install**, confirm every `.claude/skills/*` entry resolves and `.claude/skills/impeccable/scripts/hook.mjs`
still exists.

---

## Choosing Between Them

| Skill                                                           | Use For                                                                    |
| --------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `startup-validator`, `competitor-analysis`, `strategy-red-team` | Is this worth building, and who already does it                            |
| `value-proposition`, `jobs-to-be-done`, `beachhead-segment`     | Why anyone switches, and which KL eater we serve first                     |
| `lean-canvas`, `market-sizing`                                  | The business on one page, and a defensible number                          |
| `design-taste-frontend`                                         | Frontend that does not look templated. **The taste tool**                  |
| `high-end-visual-design` / `image-to-code`                      | Polish on a working UI; a design image into markup                         |
| `diagnosing-bugs` / `handoff` / `graphify`                      | A bug that resisted the first fix; context handoff; architecture questions |
| `claude-in-chrome`                                              | The real browser. Read it before any browser tool call                     |

**`strategy-red-team` is the one to reach for first.** `docs/PRODUCT.md` rests on an unproven assumption — that
Xiaohongshu data can be pulled at usable volume — and red-teaming that before the spike is cheaper than discovering it
during.

**`brainstorming` is not the ideation skill.** It shapes a build once a concept is locked, and `docs/PRODUCT.md` already
locks it. Reach for it at phase boundaries, not at the top.

### Taste, Then Impeccable

**Do not start with `impeccable`.** Taste sets the target, `impeccable` hits it.

1. Brief inference from `design-taste-frontend`; state the one-line Design Read
2. Check what exists. The design system is recorded in `docs/DESIGN.md`, not reinvented per screen
3. Execute with `impeccable` (`craft`, then `layout` / `typeset` / `colorize`)
4. Audit with `impeccable critique` **and** the `design-taste-frontend` pre-flight
5. Adjust with `polish` / `bolder` / `quieter` for a **named** problem

---

## Where Superpowers Disagrees With This Repo

`using-superpowers` says to invoke a relevant skill **before any response, including clarifying questions**, and
`brainstorming` opens with "You MUST use this before any creative work". Both are gates. **Availability beats mandate
here** — reach for a skill when the task calls for it.

Two exceptions where the superpowers framing is right:

- **`verification-before-completion`.** Never claim something works without having run it and read the output. This repo
  has a sharper reason than most: [`docs/SWARM.md`](../../docs/SWARM.md#7-measurements) measured a worker producing
  output that reads correctly and fails hidden tests, and another producing nothing at all with no error. A self-report
  is not evidence
- **`using-git-worktrees`.** Two agents in one working tree collide, and GSD's `execute-phase` runs plans in parallel
  waves. Not hypothetical: it happened in the source repo on 2026-08-22, when `git add -A` in one session swept
  another's in-progress files into an unrelated commit

`systematic-debugging` overlaps `diagnosing-bugs`. Pick one, not both.

---

## Deliberately Not Taken

**The GSD skills (67).** Not a rejection of GSD — [`docs/SWARM.md`](../../docs/SWARM.md) builds the whole workflow on
it. They are thin pointers into a global `~/.claude/get-shit-done/` runtime and do nothing without it, so vendoring them
into the repo buys nothing and 67 extra entries is the single biggest degrader of skill selection. **Install the runtime
globally** (`npm i -g get-shit-done`) and invoke `/gsd-*` from there.

**Seven `hackathon-*` skills** carried by the source repo. Retargeted to a specific event's rules and irrelevant here.

**Ten of the 13 taste-skill packages** (brandkit, imagegen-\*, minimalist-ui, industrial-brutalist-ui,
stitch-design-taste, redesign-existing-projects, gpt-taste, full-output-enforcement, design-taste-frontend-v1). Not
wrong, but a long list makes an agent pick worse. Re-add any the same way. `brandkit` is the likeliest one to want back,
once there is a UI to art-direct.

---

## Permissions

`.claude/settings.json` is **strict JSON**: a `//` comment or trailing comma is a syntax error, so the reasoning lives
here instead.

The posture is deliberately broad so the harness does not stop to ask during a long unattended run — which
[`docs/SWARM.md`](../../docs/SWARM.md#6-unattended-long-runs) names as the second most common thing that stops one. What
stays denied is the short list a human should own: merging a PR, deleting the repo, force-pushing, `git reset --hard`,
and `rm -rf /`.

Three rules that are easy to get wrong:

| Rule                              | Why                                                                                                                                                                                                          |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Edit(./**)`, never `Write(./**)` | Claude Code consults path rules only for `Read` and `Edit`. A `Write`, `NotebookEdit`, `Glob` or `MultiEdit` path rule is accepted, never checked, and warns at startup. An `Edit` rule already covers Write |
| `Read(./.env)` + `Read(./.env.*)` | The documented pattern, and a `Read` deny also blocks Edit and Write on the same path                                                                                                                        |
| `Bash(git push --force*)`         | Prefix-matched, so `rtk git push --force` slips past it. `guard-git.sh` is what actually stops that, which is why both exist                                                                                 |

**A deny rule cannot carry exceptions.** `Read(./.env.*)` therefore also blocks the committed `.env.example`, which no
agent can edit. That is the cost of the documented pattern; narrowing it to the real env filenames is the only way out,
and it trades a little safety for the convenience.

`Bash(devin:*)`, `Bash(codex:*)`, `Bash(uv:*)`, `Bash(uvx:*)`, `Bash(ruff:*)` and `Bash(pytest:*)` are allowed ahead of
need. The worker and Python lanes are named in `SWARM.md` and `AGENTS.md`; a permission prompt at hour four of an
unattended run costs more than a broad allow does.

---

## Hooks

Four guards in `.claude/settings.json`, each exiting 0 on any internal failure so a broken guard can never wedge a
session.

| Hook               | Event             | Does                                                                                                                              |
| ------------------ | ----------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `session-brief.sh` | SessionStart      | Branch, uncommitted count, docs-gate state, and days remaining on the two 2026-09 model cliffs                                    |
| `env-drift.mjs`    | SessionStart      | Reports a local `.env` disagreeing with `.env.example`, or with the main checkout from a worktree. Names keys, never values       |
| `guard-git.sh`     | PreToolUse(Bash)  | Blocks direct and force pushes to `main`, `git add .env`, and a force-add of a scraped corpus. **The only one that can stop you** |
| `format-edited.sh` | PostToolUse(Edit) | Biome- or Prettier-formats the edited file. Silent, never blocks                                                                  |

`guard-git.sh` matches on the command substring, so an `rtk`-prefixed command is caught too. It also false-positives on
any command whose _text_ contains those patterns, including writing the hook itself: use a file, not an inline heredoc.

The `PostToolUse` impeccable hook is wired and does nothing until there is UI to check.

**The impeccable `Stop` hook is not wired** — a whole-session design pass on every turn end, including sessions touching
no UI. Add it when frontend work starts:

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "[ ! -f \"${CLAUDE_PROJECT_DIR}/.claude/skills/impeccable/scripts/hook.mjs\" ] || node \"${CLAUDE_PROJECT_DIR}/.claude/skills/impeccable/scripts/hook.mjs\"",
        "timeout": 30,
        "statusMessage": "Design deep pass"
      }
    ]
  }
]
```
