# Claude Code — project rules

These are the rules for **my** apps; the factory's reviewer checks every change against
them (and against `BLUEPRINT.md` "Rules at a glance"). To use the factory with other
projects, replace them with your own: the factory enforces whatever rules this file and
the blueprint declare. See *What a project needs* in `README.md`.

Source of truth: **`BLUEPRINT.md`** in this directory. Read it before creating, modifying, or scaffolding any app.

## Creating a new app
1. Read `BLUEPRINT.md` in full first.
2. Follow the checklist in **§13**. Default to simple form (§3a); graduate to rich form (§3b) only when §3b's "When to graduate" triggers hit.
3. §13 copies scaffolding from a reference app that is private in this repo's origin; `Chatbot/` (Brio) follows the same blueprint and can serve instead. Code patterns (validation, errors, settings, logging, frontend API layer) come from the canonical files in `shared/` (§15).

## Hard rules (non-negotiable)

- **Never** set `container_name` on dev compose services.
- **Never** let outer layers import inner layers — hexagonal discipline is strict.
- Files with a `# canonical:` / `// canonical:` header are copies from `shared/`. **Never** edit them in an app without adding `+ local: <reason>` to the header; to change one for everyone, edit `shared/`, bump its version, run `make -C shared test`.
- Routes never `try/except` domain errors; components never inspect status codes or error text (BLUEPRINT §3c, §4b).
- ORM mapping is always **imperative**, never declarative.
- Every app has a **Unit of Work** as the transactional boundary.
- Migrations run automatically via `entrypoint.sh` — never instruct the user to run them manually on the remote.
- All API calls from the frontend use the `/api` prefix. Nginx proxies to `http://api:80/`.
- `e2e/` is top-level, not under `frontend/`. Specs are black-box: no imports of frontend types or backend models.
- The e2e stack always runs under a separate compose project (`-p <app>_e2e`).
- Env vars in Makefile are loaded with `set -a && . ./.env && set +a` — never `export`.

## Database — dev vs production

- In **local dev and e2e**, each app starts its own isolated `db` container — no shared Postgres.
- In **production**, all apps connect to one shared Postgres on a shared Docker network, managed by a separate infrastructure repo (private). Each app connects as its **own least-privilege role** (`<app>_app`) that owns only its own database — never the `postgres` superuser. Alembic creates the tables; the role and database are created by that repo's init script.
