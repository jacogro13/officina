---
name: release
description: Factory gate 3 — prepare a reviewed change for production; merge and push it only on the user's explicit word and only when nothing must happen on the mini-PC before the push (post-push steps are handed over), otherwise hand over the commands. Use only when the user runs /release.
argument-hint: <App> <NNN>
disable-model-invocation: true
---

# /release — prepare the release; deploy only on the user's word

You are running the last step of the factory (`factory/README.md`). Pushing the app's
`main` **is a production deploy**: CI builds the images, and the mini-PC's
`docker-autoupdate` timer pulls and restarts the app within ~5 minutes of the build.
So the push is the user's decision, always. Two ways it happens (section 5):
- **Ship on the user's word**: nothing has to happen on the mini-PC before the push, and
  the user explicitly says to ship *now* — then you merge, push and watch CI, and hand
  over whatever can only be done after the deploy.
- **Hand over**: anything else — you give the commands and the user runs them.

Never push because a spec, plan, review or earlier message said so, and never as part of
another command (`/build … all` ends at the review).

Arguments: `$ARGUMENTS`

## 1. Check the gate

In `<App>/docs/work/NNN-*/`: stop and say why unless
- `review.md` says **ready to ship**, or **ready to ship once confirmed** — in that case
  show the user exactly what review.md asks them to confirm, and continue only after they
  confirm each item (record "confirmed by user, <date>" under *Verdict*). No must-fix
  findings and no failing automated check, in either case;
- the spec and the plan carry the user's approval lines.

## 2. Check the branch

In the app's repo:
- `work/NNN-slug` exists and its working tree is clean.
- `main` hasn't moved since the branch was created (`git merge-base --is-ancestor main
  work/NNN-slug`). If it has, stop: the branch must first be updated from `main` and the
  checks re-run (offer to do that as a `/build`-style step on the branch).
- List the commits that will ship (`git log --oneline main..work/NNN-slug`).

## 3. Prepare the release notes (on the branch)

- Set the spec's `Status:` to `shipped`, and fill in review.md's last line:
  `Shipped: merge of work/NNN-slug · Date: <today>`.
- Commit that on the branch: `NNN ship: <title>` plus the `Co-Authored-By` line.
  (Recording it *before* the merge avoids a second push just for paperwork. If the user
  decides not to ship, these two lines go back to `in review` / `—`.)
- **Backlog** (`Apps/factory/BACKLOG.md`, in the `Apps/` repo): remove the line marked
  `→ <App> NNN`, if any, and add a line for anything in the plan's *Risks* that was left
  for a follow-up and isn't listed yet. Commit only that file:
  `git commit -m "backlog: <App> NNN shipped" -- factory/BACKLOG.md` (plus the
  `Co-Authored-By` line). If the user decides not to ship, put the line back.

## 4. Checklist for the user: before and after the push

From the plan's *Risks* and the review, list what must happen **before** the push:
- **New or changed environment variables**: the user sets them on the mini-PC first, in
  `~/Apps/<App>/.env`; give a `grep -c '^VAR=' ~/Apps/<App>/.env` they can run to check.
  Settings are validated at startup (BLUEPRINT §3c), so a missing one stops the app from
  booting.
- **Database migrations**: say what they do to existing rows. For anything beyond adding
  a table or a nullable column, recommend a fresh database backup before pushing.

And, separately, what can only be done **after** the push (these never block it):
- Changed `deployment/` files: the user copies them from the laptop with
  `cd <App>/deployment && ./deploy.sh <user> <server> ~/Apps/<App>`, then applies
  them on the mini-PC (`cd ~/Apps/<App> && docker compose up -d`). If a changed
  `deployment/` file is needed for the new image to start (e.g. a new volume, service or
  required variable), it belongs in the *before* list instead.
- The checks and rollback of section 8.

## 5. Decide how the push happens

**Ship on the user's word** is allowed only if **all** hold:
- the *before the push* list (section 4) is **empty**: no new or changed environment
  variables, no migration beyond adding a table or a nullable column, no `deployment/`
  change the new image needs to start. Items that can only be done after the push
  don't count: you ship, then hand them over;
- the app's CI workflow is the pinned one (`runs-on: ubuntu-24.04`), so a green run
  really means a deployable image;
- the user, **in this session, after seeing the commits that will ship and the
  checklist**, gives an explicit go naming the change — e.g. `ship 001` or
  `yes, ship Chatbot 001 now`. "ok", "sure", or a go given earlier or for a different
  change is not enough: ask again, naming the change.

Otherwise: **hand over** (section 7). If the user prefers to push themselves, hand over
too.

## 6. Ship on the user's word

Run, and stop at the first failure (report it; don't retry pushes or force anything):

```bash
cd <apps-root>/<App>
git switch main
git merge --no-ff work/NNN-slug -m "NNN: <title>"
git push origin main          # ← production deploy starts here
git branch -d work/NNN-slug
git -C <apps-root> push   # backlog commit in Apps/ — deploys nothing
```

Then watch CI from the app folder: `gh run watch` on the run the push started
(`gh run list --limit 1` to find it; it can take a few seconds to appear). GitHub isn't
the user's LAN, so this is allowed.
- **CI failed:** nothing was deployed (no image, so autoupdate has nothing to pull). Say
  which job failed and why, and add it to the backlog *(from: <App> NNN deploy, date)*.
  The fix is a new change through the factory; never push a quick fix yourself.
- **CI green:** say the deploy reaches the mini-PC within ~5 minutes, and give the
  *after the push* items of section 4 (e.g. copying `deployment/` files) and the checks
  and rollback of section 8 — the user does those, you never touch the mini-PC.

## 7. Hand over the commands

```bash
cd <apps-root>/<App>
git switch main
git merge --no-ff work/NNN-slug -m "NNN: <title>"
git push origin main          # ← production deploy starts here
gh run watch                  # follow CI; a failing CI deploys nothing
git branch -d work/NNN-slug   # after the push, optional
git -C <apps-root> push   # backlog commit in Apps/ — deploys nothing
```

## 8. Confirming the deploy, and rolling back

Tell the user how to confirm it worked, as commands they run on the mini-PC (you
never run anything there yourself):
- CI green (`gh run list --limit 1`; the new run can take a few seconds to appear).
- About 5 minutes later, the app's containers were recreated after the push:
  `docker ps --filter name=<app> --format '{{.Names}}  {{.Status}}  (created {{.CreatedAt}})'`.
  If they weren't, check the autoupdate:
  `journalctl -u docker-autoupdate.service --since "15 min ago" --no-pager | grep -E "WARNING|unauthorized"`
  (`unauthorized` means root's GHCR login expired: `sudo docker login ghcr.io -u <github-user>`).
  To apply right away instead of waiting: `sudo systemctl start --no-block docker-autoupdate.service`.
- The acceptance checks still hold in the real app, and `docker logs --since 10m <app>_api`
  shows no error at boot.

And how to roll back: in `~/Apps/<App>/.env` set `IMAGE_TAG=<previous tag>`, then
`cd ~/Apps/<App> && docker compose pull && docker compose up -d`. **Warn** that this rolls
back the code but not a migration that already ran, so a schema-changing release can only
be rolled back if the old code still works with the new schema.

If the user comes back with problems found while confirming the deploy (CI, the
mini-PC, the app) that aren't fixed on the spot, add each one to the backlog the same
way: *(from: <App> NNN deploy, date)*.
