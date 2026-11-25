# NNN — Plan

Spec: [spec.md](spec.md) (approved YYYY-MM-DD)

## Approach
<!-- A short paragraph: how, and which BLUEPRINT sections / ADRs / shared files apply.
     Name any new ADR this change needs. -->

## Tasks
<!-- Small enough to review in a few minutes each. Every task says how it's checked.
     Worker: `local` (the local model may do it, see /plan's rules) or `claude`.
     For `local` tasks the Check is ONE exact command, run from the app folder, that
     fails on the current code and passes once the task is done.
     Status: todo / done / blocked. -->

| # | Task | Files | Check | Worker | Status |
|---|------|-------|-------|--------|--------|
| 1 | … | … | e.g. `make lint typecheck`, `test_…` passes | claude | todo |

<!-- One brief per `local` task. It is the ONLY text the local worker receives (plus the
     named files), so it must stand alone: what to change, where, which tests to write,
     what to keep as it is. Delete this section if no task is `local`. -->
## Worker briefs

### Task N
…

## Risks
<!-- What could go wrong (data, deploy, other apps) and how the plan guards against it. -->

---
Approved by: — · Date: —
