---
name: review
description: Factory step 4 — have the independent reviewer subagent review a finished change and write review.md. Use only when the user runs /review (or when /build … all finishes).
argument-hint: <App> <NNN>
disable-model-invocation: true
---

# /review — launch the independent reviewer

You are running step 4 of the factory (`factory/README.md`). **You don't review**: the
`reviewer` subagent does (`Apps/.claude/agents/reviewer.md`), in a fresh context that has
not seen how the change was built. Your job is to launch it without influencing it, and
to relay its result faithfully.

Arguments: `$ARGUMENTS`

## 1. Launch it with the fixed brief

- Take the app and the number from the arguments (e.g. `Famiglia 008`). If either is
  missing, ask the user.
- Launch the `reviewer` subagent with a task message that is **exactly** `<App> <NNN>` —
  nothing else. No summary of the change, no list of what was fixed or tested, no hint
  about where to look. Whatever you know about the change stays with you.
- Wait for it to finish (don't run it in the background: it must write in the user's
  checkouts).

## 2. Relay the result

- Read `<App>/docs/work/NNN-*/review.md` and show the user the verdict line **quoted
  from the file**, followed by the reviewer's final message.
- If the reviewer stopped without a review (gate not met, missing app or number), relay
  its reason as it gave it.
- **Never edit `review.md`**, the plan's *Fixes from review* section or the backlog lines
  the reviewer wrote, and never soften or reinterpret its verdict. If you disagree with a
  finding, say so to the user as your own opinion, separately.

## 3. Next step

- **ready to ship** → `/release <App> NNN`.
- **ready to ship once confirmed** → the user confirms the listed items; then `/release`.
- **changes needed** → the fixes are in the plan; `/build <App> NNN` (or `all`), then
  `/review` again.
