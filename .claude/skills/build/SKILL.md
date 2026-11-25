---
name: build
description: Factory step 3 — implement an approved plan.md on the change's branch, one task per run or all of them (`all`), checking and committing each task. Use only when the user runs /build.
argument-hint: <App> <NNN> [task-number | all]
disable-model-invocation: true
---

# /build — implement an approved plan, task by task

You are running step 3 of the factory (`factory/README.md`). Every task is implemented,
checked and committed **on its own** on the change's branch. Two modes:

- **One task** (default, or a task number): do that task, then stop for the user.
- **`all`**: do the remaining tasks in order, stopping only when something needs the
  user (section 7), then run the review. The user's gates don't move: they approved the
  spec and the plan, they read the review, and they push.

Arguments: `$ARGUMENTS`

## 1. Check the gate

In `<App>/docs/work/NNN-*/`: stop and say why unless `spec.md` is approved and
`plan.md`'s last line is filled in by the user (`Approved by: <name> · Date: <date>`).
Tasks under a `## Fixes from review` heading were added by `/review` and need no new
approval (they only fix findings within the approved spec); build them like any other.
If one of them seems to change *what* is built, stop and say so instead.

## 2. Get onto the branch (in the app's own repo)

- The working tree of `<App>` must be clean. If it has uncommitted changes, stop and
  show them; never stash, discard or commit them yourself. **Exception:** this change's
  own work record (`docs/work/NNN-slug/`, uncommitted after `/spec` and `/plan`) is
  expected — it is not someone else's change.
- Branch name: `work/NNN-slug`. If it exists, switch to it. If not, create it from the
  local `main`.
- **Never push, never merge, never touch `main`.** `main` is production.
- First run only: set the spec's `Status:` to `building`, and if the work record is not
  yet committed, commit it alone on the branch first: `NNN: spec and plan`.

## 3. Pick the task

The task number given as argument, otherwise the first task whose status is `todo`.
If it's `blocked`, stop and show why. If no task is left, say the next step is
`/review <App> NNN` and stop.

Read its **Worker** column: `local` → section 4a; `claude`, or no Worker column (plans
written before step 4) → section 4.

## 4. Implement it — within the task

- Change only what the task describes, in the files it names. If it turns out to need
  other files or a different approach, **stop and explain**: the plan needs revising
  (the user clears its approval line and runs `/plan` again). Don't improvise.
- Follow `Apps/BLUEPRINT.md`, the app's `CLAUDE.md` and the user's test style. Write
  the task's tests in the same task.
- Never edit a file with a `canonical:` header unless the task says so; if it does, the
  header gets a `+ local: <reason>` label or the change goes to `Apps/shared/` instead.

## 4a. A `local` task: the local worker does it, you check it

The local model (Qwen via aider, `Apps/factory/worker/run.py`) implements the task; you
prepare it, judge the result, and take over when it fails. Network: the worker only calls
the factory's LLM endpoint (the user's exception) — never call anything else on the LAN.

1. **Brief.** Copy the task's worker brief (*Worker briefs* → `### Task <k>`) to
   `Apps/factory/worker/logs/<App>-<NNN>-task<k>.md`. Files the brief names as read-only
   references become `--ref` arguments; the *Files* column becomes the `--file` arguments.
2. **Run** from `Apps/`:
   `python3 factory/worker/run.py --repo <App> --task-file <brief> --check "<Check>" --file … [--ref …]`
   It prints JSON. By `status`:
   - `worker_unavailable` (Qwen isn't loaded): do the task yourself (section 4) and note
     *worker unavailable*. Don't ask the user to swap models; you can't do it yourself.
   - `refused` because the check already passes on the unchanged code, or the tree isn't
     clean: **stop and explain** — the plan's check or the branch state is wrong.
   - `check_failed` or `scope_violation`: revert the worker's edits
     (`git checkout -- . && git clean -fd` in the app repo — only the worker's changes,
     the tree was clean before it ran) and run it **once more**. If the second run fails
     too, revert again and do the task yourself (section 4), noting *worker failed twice:
     <reason>*.
   - `passed`: go on.
3. **Keep the raw result:** save the worker's diff, before you change anything, to
   `Apps/factory/worker/logs/<App>-<NNN>-task<k>.diff` (`git diff > …`, plus `git diff
   --no-index /dev/null <file>` for new files). The reviewer compares it with what was
   committed.
   **Read the whole diff** against the brief before anything else. Look for: deleted or loosened tests (a removed test case, a weaker assertion),
   new `noqa` / `pyright: ignore` / `eslint-disable` / `@ts-ignore` / skips, anything the
   brief didn't ask for, and the app's conventions. A small problem (a few lines): fix it
   yourself and note *local + fix: <what>*. A bigger one: revert and do the task yourself,
   noting *worker result rejected: <why>*.
4. Then the normal checks (section 5) and the commit (section 6). The commit body gets a
   line `Implemented-by: local worker (qwen-code via aider <version>)` — or, if you took
   over, `Implemented-by: claude (<the note above>)` — plus the worker's numbers
   (runs, seconds, tokens in/out) and the path of the saved raw diff. The task's status becomes `done (local)`,
   `done (local + fix)` or `done (claude: <note>)`.

## 5. Check it

Run, from the app folder: the task's own *Check*, then `make lint typecheck` and the
unit tests (`make unit`), as far as those targets exist.

- **Never** make a check pass by weakening it: no deleting or loosening tests, no new
  `noqa` / `pyright: ignore` / `eslint-disable` / `@ts-ignore`, no skipped tests — unless
  the task explicitly says so. If that seems the only way, stop and explain.
- If a check fails, fix the code and re-run. After **two** failed attempts, stop: set the
  task's status to `blocked` with a one-line reason, and report.
- `make integration`: run it yourself when the task touches code it covers
  (testcontainers, test data only — allowed by the user).
- `make e2e`: run it yourself **only if the app's `CLAUDE.md` says its e2e stack is
  self-contained** (a line `E2E self-contained: yes (checked <date>)` — own throwaway db,
  mocked LLM/storage, only localhost, `down -v`). Otherwise give the user the exact
  command. One task: run it when the task's *Check* names it. `all`: run it once, after
  the last task. Never start the dev stack or a dev server.

## 6. Commit it (on the branch)

- Set the task's status to `done` in `plan.md`.
- One commit for the task, with the plan update, on `work/NNN-slug`:
  `NNN task <k>: <task title>`, a short body saying what changed and how it was checked,
  and the `Co-Authored-By` line.
- **One task:** report what changed (files, a few lines), the check results, any commands
  the user must run, and the next task's title. Stop.
- **`all`:** go back to step 3 for the next task.

## 7. `all`: when to stop and ask

Stop, report what's done so far and what you need, whenever:
- something in the task or the spec is unclear, or two readings are possible;
- a task needs files or an approach the plan didn't foresee (section 4);
- a check can't be fixed in two attempts (section 5);
- the worker refuses a `local` task because its check already passes or the tree isn't
  clean (section 4a);
- a task would touch a canonical file, a database migration, `deployment/`, CI, or
  anything outside the app's repo, and the plan doesn't spell out exactly how.

Never resolve these by guessing. Already-committed tasks stay; the user can continue
with `/build <App> NNN all` once it's sorted.

## 8. `all`: finish

When no task is left:
- Run `make e2e` as in section 5 (or list it for the user).
- Give the user **one summary**: per task, one or two lines on what changed and how it
  was checked; then anything they must run or decide.
- Then hand over to the independent reviewer: read `Apps/.claude/skills/review/SKILL.md`
  and follow it for `<App> NNN` — it launches the `reviewer` subagent with only
  `<App> <NNN>` as its brief. **Don't review the change yourself and don't brief the
  reviewer**: you built it, so your view is exactly what the review must not depend on.
  Its result (`review.md` and the verdict, relayed as written) is where the run ends.
