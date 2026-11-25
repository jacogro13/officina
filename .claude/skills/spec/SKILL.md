---
name: spec
description: Factory gate 1 — turn an idea for one app into an approved-ready spec.md by asking the user questions. Use only when the user runs /spec.
argument-hint: <App> <idea in a few words>  |  <App> <NNN> to revise a draft
disable-model-invocation: true
---

# /spec — write a change's spec with the user

You are running step 1 of the factory (`factory/README.md`). Your only output is one
file: `<App>/docs/work/NNN-slug/spec.md`. You do not plan, design or write code.

Arguments: `$ARGUMENTS`

## 1. Find the app and the record

- The first argument is the app folder name under `Apps/` (e.g. `Famiglia`). If it's
  missing or not an app folder with a `backend/` or `frontend/`, list the apps and ask.
- **From the backlog**: the idea may be a line in `Apps/factory/BACKLOG.md` (the user
  may quote it, or say "the backlog item about …"). Use that line as the starting point,
  and when you write the spec, append `→ <App> NNN` to it. That edit to `BACKLOG.md` is
  the only other file you touch; leave it uncommitted with the spec. If the idea came
  up in conversation and isn't in the backlog, don't add it.
- **New idea** (the rest is text): next number = highest `NNN` in `<App>/docs/work/` + 1
  (start at `001`). Propose a slug (2–4 lowercase words joined by `-`) and continue.
- **Revising** (the second argument is a number): open that `spec.md`. If its status is
  not `draft`, stop and say so — an approved spec only changes if the user sets it back
  to `draft` themselves.

## 2. Read just enough context

- `Apps/BLUEPRINT.md` "Rules at a glance", and the app's `CLAUDE.md`.
- The titles of the app's ADRs (`docs/adr/`) and earlier work records (`docs/work/`).
- The app's section of `Apps/factory/BACKLOG.md`, and *All apps*: mention any item the
  idea overlaps with, so the user can fold it in or leave it.
- Only the code needed to understand the idea (e.g. the screen or entity it touches).
  Read, never edit.

## 3. Interview the user

Goal: fill the template's sections — Why, What changes, Out of scope, Acceptance
checks — with the user's intent, not your guesses.

- Ask **at most three questions at a time**, the most important first. For each, offer
  your best guess as a default the user can just accept.
- Ask about *what* and *why*, not *how*. Implementation belongs to `/plan`.
- Every acceptance check must be **checkable**: a test, a command, or something the
  user can try in the app. Rewrite vague ones ("works well") until they are.
- If the idea is too big for one change (it would need more than ~10 small tasks, or
  touches several unrelated areas), propose splitting it into several specs and agree
  on which one to write now.
- Anything still undecided goes under **Open questions**. Don't invent answers to
  close them.

## 4. Write the spec

- Copy `Apps/factory/templates/spec.md` to `<App>/docs/work/NNN-slug/spec.md` (or update
  the existing draft) and fill it in. Write in English, short and concrete.
- `Status: draft`. Today's date in `Created:`.
- **Never touch the `Approved by:` line.** Only the user fills it in.

## 5. Stop

Show the user the path and a 3–5 line summary of the spec, then say:

- what's in **Open questions** (if anything) — the spec can't be approved until it's empty;
- that approving means editing the last line to `Approved by: <name> · Date: <date>` and
  setting `Status: approved` themselves;
- that the next step is `/plan <App> NNN`, which only runs on an approved spec.

Do not commit, do not start planning, do not touch any other file (except the one
backlog line, as above).
