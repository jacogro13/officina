# The factory

A repeatable, human-gated way to change an app (or create one) with Claude Code.
Every change leaves a written trail you can read; nothing reaches `main` without you.

```
idea / BACKLOG.md → /spec → spec.md ──(you approve)──→ /plan → plan.md ──(you approve)──→
       /build (task by task, checks after each) → /review → review.md ──(you ship)──→ main
```

`main` is production: the mini-PC's `docker-autoupdate` timer deploys every push to
`main` within ~5 minutes (BLUEPRINT §7). So the last gate, shipping, is always yours.

This file grows as the factory is built, one piece at a time.

**Always start Claude Code in `Apps/`** (not inside an app folder). The factory's
commands live in `Apps/.claude/skills/`, and Claude Code only finds them from a session
started in `Apps/` or below it *within the same git repo* — each app is its own repo, so
a session started in `Famiglia/` would not see them.

**Two kinds of repo, two kinds of push.** Each app is its own repo: pushing its `main`
deploys it. `Apps/` itself (blueprint, `shared/`, this factory, the backlog) is a
separate repo with its own GitHub remote: pushing it deploys nothing, but it's the only
backup of all of the above, so push it whenever factory commands commit there
(`/review` and `/release` commit backlog lines; changes to commands, blueprint or `shared/`).
`git -C <apps-root> push` is always safe.

## Work records (2a)

Each change gets one folder **in the app's own repo**, committed together with the code
it produces, so the *why* travels with the app's history:

```
<App>/docs/work/
├── 001-v2-migration/
│   ├── spec.md      # what and why — written with you, approved by you   (gate 1)
│   ├── plan.md      # how, as small checkable tasks — approved by you    (gate 2)
│   └── review.md    # what was checked, findings, verdict                 (gate 3: you ship)
└── 002-…/
```

- **Numbering:** three digits, per app, never reused (`001`, `002`, …). The slug is a
  few lowercase words joined by `-`.
- **Status** lives in one line at the top of `spec.md`, and the commands update it:
  `draft → approved → building → in review → shipped`, or `abandoned`.
  Abandoned records stay: why something was *not* done is worth keeping too.
- **Approvals are written down.** `spec.md` and `plan.md` end with
  `Approved by: … · Date: …`. A command only moves past a gate when that line is
  filled in by you, not by Claude.
- **Decisions go to ADRs.** If a change makes an architectural decision, the plan
  includes writing `docs/adr/NNN-*.md`; the work record links to it. Work records say
  what was done; ADRs say what was decided.
- **Templates:** `templates/spec.md`, `templates/plan.md`, `templates/review.md`.
  Copy them into the new folder; the commands do this for you once they exist.

## `/spec <App> <idea>` — gate 1 (2b)

Turns an idea into `docs/work/NNN-slug/spec.md` by asking you questions (at most three
at a time, each with a suggested default). It asks about *what* and *why*, never *how*;
makes every acceptance check checkable; suggests splitting ideas that are too big; and
parks anything undecided under *Open questions*.

It never fills in the approval line, never commits, and never starts planning. You
approve by editing `Status: approved` and `Approved by: … · Date: …` yourself.
`/spec <App> NNN` revises a spec that is still a draft.

Definition: `Apps/.claude/skills/spec/SKILL.md`.

## `/plan <App> <NNN>` — gate 2 (2c)

Runs only on a spec that is approved by you and has no open questions. Turns it into
`plan.md`: a short approach, then **small, self-contained tasks** — each names its
files, its change and its check, and leaves the app building with tests passing — and
the risks. Because a push to `main` deploys, it always spells out what any database
migration does to existing data. More than ~10 tasks means the spec should be split.

If planning shows the spec is wrong, it stops instead of quietly fixing it: you set the
spec back to `draft` and revise it with `/spec`. It never fills in the approval line and
never starts building.

Definition: `Apps/.claude/skills/plan/SKILL.md`.

## `/build <App> <NNN> [task | all]` — task by task (2d)

Runs only on an approved plan. Works on the branch `work/NNN-slug` in the app's repo —
never on `main`, never pushes, never merges. Every task is implemented within the files
the plan names, checked (the task's check, `make lint typecheck`, the unit tests) and
committed **on its own** on the branch.

- **Default:** one task per run, then it stops so you can look.
- **`all`** (added after the pilot): all remaining tasks in a row, then one summary and
  the review straight away, so you come back to a finished `review.md`. It stops and asks
  whenever something is unclear, a task needs what the plan didn't foresee, a check fails
  twice, or a task touches a canonical file, a migration, `deployment/`, CI or anything
  outside the app without the plan spelling out how. It never guesses.

- If the task needs something the plan didn't foresee, it stops: the plan gets revised
  (clear its approval line, run `/plan` again) instead of being improvised.
- It never makes a check pass by weakening it (deleting tests, adding ignore comments).
- After two failed attempts at a check, the task is marked `blocked` and it stops.
- It runs `make integration` itself (throwaway testcontainers), and `make e2e` too when
  the app's `CLAUDE.md` says `E2E self-contained: yes` (own throwaway db, no external
  services, `down -v`); otherwise it gives you the command. `/plan` adds that check the
  first time it plans for an app. It never stashes, discards or commits changes it didn't
  make.

Definition: `Apps/.claude/skills/build/SKILL.md`.

## `/review <App> <NNN>` — the independent check before shipping (2e, step 3)

`/review` doesn't review: it launches the **`reviewer` subagent**
(`.claude/agents/reviewer.md`), which starts in a fresh context that never saw the build,
gets only `<App> <NNN>` as its brief (and ignores anything else it's told), and writes
`review.md` itself. The launching session relays the verdict quoted from the file and may
not edit what the reviewer wrote. `/build … all` hands over to it the same way.

The reviewer **fixes nothing**. It runs lint, type check, unit and integration tests, the
drift check, and `make e2e` for self-contained apps; reads the *whole* diff against `main`
for scope creep, weakened tests, broken hard rules, unsafe migrations and committed
secrets; checks every acceptance check of the spec with evidence; and writes findings
(must-fix / should-fix / note, with `file:line`) and one of three verdicts: **ready to
ship**; **ready to ship once confirmed** (only something you must check is left, and
`/release` asks for it); **changes needed** (a must-fix finding or a failing check).

Fixes go into the plan as `todo` tasks under *Fixes from review*, with no new approval
when they stay within the approved spec; anything that changes *what* is built goes back
through `/plan`. Findings that belong elsewhere go to the backlog.

**Enforced, not just instructed:** the reviewer's tools are limited to reading, searching,
running commands and writing, and a write guard (`factory/hooks/reviewer_write_guard.py`,
tests: `make -C factory test`) refuses any file except `review.md`, `plan.md` and `spec.md`
in the work record, and the backlog. The guard covers the editing tools, not the shell;
writing through the shell is forbidden by its instructions, and would show in git.

Definitions: `Apps/.claude/agents/reviewer.md` (the procedure),
`Apps/.claude/skills/review/SKILL.md` (the launcher).

## `/release <App> <NNN>` — gate 3, yours (2f)

(Called `/ship` until 2026-11-25; renamed because Claude Code now has a built-in `/ship`.
Old work records still say `/ship`.)

Runs only on a change whose review says *ready to ship*, or *ready to ship once
confirmed* after you confirm the listed items. It checks that `main` hasn't moved since
the branch started, records `Status: shipped` on the branch (so no second push is needed
for paperwork), updates the backlog, and lists what must happen **before** the push —
new environment variables set on the mini-PC, a backup before any migration that
rewrites existing data, a `deployment/` change the new image needs to start — and,
separately, what can only happen **after** it (a Deployer *Deploy* for other changed
`deployment/` files, the deploy checks).

Then the push — the production deploy — happens one of two ways:
- **Ship on your word** (added after the pilot): if the *before* list is empty (after-push
  steps don't block; they're handed over once CI is green) and the app's
  CI is the pinned one, and you say explicitly, in that session, to ship *this* change
  *now* (e.g. `ship 001`), it merges, pushes, pushes `Apps/` and watches CI on GitHub. A
  vague "ok", an earlier go, or anything chained from another command never counts.
- **Hand over:** in every other case, or if you prefer, it gives you the exact commands.

Either way it never touches the mini-PC: it gives you the commands to confirm the deploy
and to roll back (pin the previous `IMAGE_TAG`), with the warning that a rollback doesn't
undo a migration that already ran. A failed CI deploys nothing; its fix goes through the
factory as a new change, never as a quick push.

Definition: `Apps/.claude/skills/release/SKILL.md`.

## Backlog

`factory/BACKLOG.md` holds everything that came up and should be done later, for every
app: ideas, fixes, follow-ups. One line per item (what — why — where it came from), in
sections per app plus *All apps*, *mini-PC / Infrastructure* and *Factory / Blueprint*.

- You add to it whenever you like. `/review` adds findings that belong outside the
  change; `/release` adds what the plan deferred or the deploy revealed.
- `/spec` can start from a backlog line, and marks it `→ <App> NNN` while the work is
  under way; `/release` removes it when the change is shipped.
- It's a memory aid, not a tracker: no priorities or statuses beyond that marker.
  Decide what's next by reading it.

## The local worker (step 4)

Some tasks are done by a **local model** instead of Claude: Qwen3.6-35B-A3B on the
mini-PC, driven by aider. Claude still writes the spec and plan, reads every worker diff,
reviews independently, and takes over when the worker fails. Why aider: see
`bakeoff-2026-11.md`.

**Swapping the model** (on the mini-PC; Gemma and Qwen can't both be loaded):
`sudo systemctl start llama-qwen.service` → Qwen; `sudo systemctl start llama.service
llama-ocr.service` → back to Gemma (`Infrastructure/llm/README.md`). While Qwen runs, the
apps' AI features get Qwen's answers and OCR is off. If Qwen isn't loaded, `/build`
simply does the `local` tasks itself.

**Which tasks** (`/plan` decides, you approve): only fully specified, small (≤ ~3 named
files), with a check that fails on the current code, and nothing sensitive — no
canonical files, migrations, `deployment/`, CI secrets, auth, or other repos. Each gets a
stand-alone *worker brief* in the plan: the only text the worker sees, together with
`worker/conventions.md` (test style, match the file's style, never delete tests,
"verbatim" means byte for byte), which goes with every task. Plain file copies and
anything touching secrets stay with Claude.

**What happens** (`/build`, per `local` task): the worker script
(`worker/run.py`) checks Qwen is loaded, the tree is clean and the check fails first;
runs aider on the named files only; reverts everything if anything else changed; runs
the check. Claude then reads the whole diff (deleted tests, ignore comments, scope) and
commits with `Implemented-by: local worker …`. Two failed runs, or a rejected result, and
Claude does the task instead — always noted.

**Reading the numbers:** each `local` task's status in the plan says who finished it
(`done (local)`, `done (local + fix)`, `done (claude: …)`); its commit has the runs,
seconds and tokens, and the path of the worker's raw diff (kept in `worker/logs/` before
Claude fixes anything); the review's *Local worker* section sums it up and lists what the
worker got wrong. That's the evidence for whether the worker saves anything.

**Network:** the worker only calls `$FACTORY_LLM_BASE` (see `.env.example`; set it in `.claude/settings.local.json` → `env`) (`/v1/models`, chat completions)
— the narrow exception in the user's global rules. Worker logs go to `worker/logs/`
(git-ignored). Tests for the worker and the write guard: `make -C factory test`.
