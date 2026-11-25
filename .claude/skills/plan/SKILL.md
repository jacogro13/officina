---
name: plan
description: Factory gate 2 — turn an approved spec.md into plan.md, a list of small, checkable tasks. Use only when the user runs /plan.
argument-hint: <App> <NNN>
disable-model-invocation: true
---

# /plan — cut an approved spec into small, checkable tasks

You are running step 2 of the factory (`factory/README.md`). Your only output is
`<App>/docs/work/NNN-slug/plan.md`. You do not write code.

Arguments: `$ARGUMENTS`

## 1. Check the gate

Open `<App>/docs/work/NNN-*/spec.md`. Stop, and tell the user why, unless **all** hold:
- `Status: approved`;
- the last line is filled in by the user (`Approved by: <name> · Date: <date>`, not `—`);
- *Open questions* is empty.

If `plan.md` already exists and is approved, stop: an approved plan only changes if the
user clears its approval line themselves. A draft plan may be rewritten.

## 2. Read what the plan depends on

- The spec, in full.
- `Apps/BLUEPRINT.md`: "Rules at a glance" plus every section the change touches.
- `Apps/shared/README.md` if the change touches a canonical file or adopts one.
- The app's `CLAUDE.md`, the ADRs that concern this area, and the code the change touches.
- The user's test style (global `CLAUDE.md`): fakes not mocks, behaviour-named tests,
  setup / action / check separated, `parametrize` for variations, both sides of a rule.

If the spec turns out to be wrong or incomplete while you read, **don't fix it here**.
Stop and explain; the user sets it back to `draft` and revises it with `/spec`.

## 3. Cut the tasks

Each task must be:
- **Small** — one concern, reviewable in a few minutes (as a rough guide, under ~150
  changed lines).
- **Self-contained** — it names the files, the intended change and its check, so that
  someone with no other context could do it.
- **Safe to stop after** — when it's done, the app builds and its tests pass. Order the
  tasks so this holds at every step (e.g. add the new thing, switch to it, then remove
  the old thing).
- **Checked** — the *Check* column names a command (`make lint typecheck`,
  `make test-backend`, …) and/or the specific tests that must exist and pass. Tests for a
  behaviour are written in the same task as the behaviour.

Include, where they apply:
- a task to write an ADR, if the change makes an architectural decision;
- `make types` and committing `schema.d.ts`, if the API changes;
- `make drift`, if canonical files are copied or changed;
- a final task running the app's full gate (`make test`, including e2e);
- if the app's `CLAUDE.md` has no `E2E self-contained:` line yet: a task that checks whether
  `make e2e` is self-contained (own throwaway db, mocked LLM/storage, only localhost,
  `down -v`) by reading the Makefile, the e2e compose override and the specs — not by
  running it — and records the answer there as `E2E self-contained: yes|no (checked <date>)`.

**More than ~10 tasks** means the change is too big: stop, and propose how to split the spec.

### Who does each task: the Worker column

Every task gets `local` (the local model, via `factory/worker/run.py`) or `claude`.
Mark a task `local` **only if all of these hold** — when in doubt, `claude`:
- **Fully specified:** the task text says exactly what to change and where; no design
  choice, naming decision or judgement call is left. The worker gets *only* the task text,
  the named files and any read-only references — not the spec, the plan or this conversation.
- **Small and contained:** at most ~3 files, all named in *Files* (new files too), no new
  dependencies, and the named files plus references stay under ~40 KB (the model's
  context is 16k tokens).
- **A worker check:** the *Check* column is **one exact shell command**, run from the app
  folder, that **fails on the current code** and passes once the task is done (e.g. a
  grep for the old pattern plus the tests the task names). If you can't write such a
  command, the task is `claude`.
- **Not sensitive:** no canonical (`canonical:`) files, no database migrations, nothing in
  `deployment/`, no auth or security code, nothing outside the app's repo, and not the
  ADR, e2e-check or full-gate tasks. CI workflow edits **may** be `local` as long as they
  don't add, remove or change secrets (the bake-off's CI task went well).
- **Not a plain copy:** "copy file X verbatim" is not a model task — Claude does it with
  `cp` (the pilot's worker paraphrased a file it was told to copy).

For every `local` task, write a **worker brief** under *Worker briefs* (`### Task <k>`):
a short paragraph that stands on its own — what to change, in which files, which tests to
add (and in which style, e.g. the existing fakes), what must stay as it is. This brief is
the only text the worker receives, so anything not in it doesn't exist for the worker.
Keep existing tests explicitly ("keep every existing test case") — the bake-off showed
the model will otherwise delete one to make the new behaviour fit. The general rules
(test style, no unused imports, match the file's style) are sent with every task from
`Apps/factory/worker/conventions.md`; don't repeat them, but do name anything specific to
this app the brief depends on.

Good `local` candidates are mechanical, well-described edits: a pattern replaced in a few
files, a small function with the tests the task spells out, a config change that mirrors
a named reference file. Say in the plan's *Approach* how many tasks are `local` and why
the others aren't — the user approves this split with the plan.

## 4. Name the risks

`main` is production (a push deploys within ~5 minutes), so call out explicitly:
- **Database migrations** — every Alembic migration runs on the real data at deploy.
  Say what it does to existing rows, and make it safe for them.
- **Behaviour users will notice**, other apps or `Infrastructure/` affected, secrets or
  environment variables to add on the mini-PC (the user does that, via the Deployer).

## 5. Write the plan and stop

- Copy `Apps/factory/templates/plan.md` into the work folder and fill it in. English,
  short. **Never touch the `Approved by:` line.** Leave the spec's status as `approved`.
- Show the user: the approach in two or three lines, the number of tasks with their
  titles and their Worker (`local` / `claude`), and the risks.
- Say that approving means editing the plan's last line themselves, and that the next
  step is `/build <App> NNN`.

Do not commit, do not start building, do not edit any other file.
