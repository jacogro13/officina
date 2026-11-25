# Blueprint v2 — decisions

Running log of decisions for the next version of `BLUEPRINT.md`. Each entry: the
decision, why, and the evidence behind it.

**Status (2026-11-16):** all decisions are folded into `BLUEPRINT.md` v2, and their
canonical code is in `shared/` (tested). This file is now the rationale behind the
v2 rules. Refinements made while building are marked *Refined*.

Pilot app for v2: **Famiglia** (small CRUD). Next: **Chatbot**.

---

## D1 — Validated domain types (Pydantic types, plain dataclasses)

**Decision.** Domain entities stay stdlib `@dataclass`es, but their fields are typed
with Pydantic `Annotated` constraint types, and a small shared base class validates
every field **on creation and on every assignment** via a cached `TypeAdapter`.
Reusable constrained types (e.g. `HexColor`, `NonBlankStr`, `Avatar` as a `Literal`)
live in the domain and are **reused by the API schemas** — no weaker re-declarations.
Rules that span several fields are enforced by entity methods that change those
fields together and then check the invariant once (e.g. `activity.reschedule(...)`),
not by bare attribute assignment.

**Why.** Today validation only runs in `__post_init__`, so updates skip it.
Reproduced in Famiglia: `services.update_member(uow, id, name="   ", color="red")`
saved and committed both values, while creating a member with them is rejected.
Validation is also duplicated between domain and `schemas.py`, with the API side
weaker (`recurrence: str`, `color: str`).

**Trade-off accepted.** The domain now depends on Pydantic (the old "zero framework
deps" rule is relaxed to "Pydantic types only — no FastAPI, no SQLAlchemy").

**Evidence (spike, 2026-11-16, pydantic 2.13.4 + SQLAlchemy 2.0.49, imperative mapping):**

| Approach | Result |
|---|---|
| Pydantic `BaseModel` entity | ✗ `UnmappedInstanceError` — SQLAlchemy can't instrument it |
| Pydantic `@dataclass(validate_assignment=True)` | ✗ assignment validator collides with SQLAlchemy attribute descriptors |
| stdlib `@dataclass` + `Validated` base (below) | ✓ rejects blank at init and on assignment, strips whitespace, round-trips through the DB |

Sketch of the base (to be hardened: use `typing.get_type_hints` so it works with
`from __future__ import annotations`; skip SQLAlchemy-internal attributes):

**Requirement found later (F4 comparison):** validation errors must carry the
**field name** (e.g. convert to `InvalidInput(field=<attr>)`). A bare `TypeAdapter`
error has an empty location, so D2 can only say "invalid input", never "name is required".

```python
class Validated:
    _adapters: dict = {}
    def __setattr__(self, k, v):
        hints = type(self).__annotations__
        if k in hints:
            key = (type(self), k)
            ad = Validated._adapters.get(key) or Validated._adapters.setdefault(key, TypeAdapter(hints[k]))
            v = ad.validate_python(v)
        super().__setattr__(k, v)

@dataclass
class FamilyMember(Validated):
    name: NonBlankStr
    color: HexColor
```

---

## D2 — Error model: one hierarchy, one handler, one response shape

**Decision.**
- `domain/errors.py` defines `DomainError` (with a stable `code`) and the base kinds
  `NotFound`, `Conflict`, `InvalidInput`. Specific errors subclass them with their own
  code (e.g. `MemberInUse(Conflict)`, `code = "member_in_use"`).
- Services and domain raise only these (plus Pydantic `ValidationError` from D1).
- **One** exception-handler module in `entrypoints/` maps them:
  `NotFound → 404`, `Conflict → 409`, `InvalidInput` / `ValidationError` /
  `RequestValidationError → 422`, anything else → **500, logged with traceback,
  generic message**.
- Every error response has the same body: `{"code": str, "message": str, "field": str | null}`.
- Routes contain **no** `try/except` for domain errors.
- The frontend maps `code` → Italian text; `message` is for logs/debugging only.

**Why.** Famiglia's routes repeat `except ValueError → 400 / NotFound → 404` in every
handler; any stray `ValueError` (including bugs) becomes a 400 that leaks raw English
text; errors come back in two shapes (`detail: str` vs `detail: [...]`); the frontend
collapses everything into `Error("op failed (400): …")` and can't distinguish kinds.
Chatbot defines error classes ad hoc in the first use-case file that needed them.

*Refined (while building `shared/`):* the `Validated` base (D1) converts Pydantic
failures into `InvalidInput(field=…)` itself, so the domain never lets a raw
`ValidationError` escape. A `ValidationError` reaching the handler is therefore a bug
→ **500**, not 422. `HTTPException` (e.g. 413 image too large) also gets the common
body, with code `http_<status>`. The 500 response carries `X-Request-ID` (D6).

**Not chosen.** Full RFC 9457 problem-details format — more formal than needed for
first-party LAN apps; the simple shape can be upgraded later if a third party consumes an API.

---

## D3 — Lint, format and type-check gates: ruff + pyright

**Decision.** Every backend runs `ruff format --check`, `ruff check` and `pyright`
as part of `make test` and CI. Introduced per app as that app is migrated to v2
(not a big-bang across all repos); existing violations are fixed or explicitly
baselined at migration time, never silently ignored.

*Refined (blueprint review):* the frontend joins the same gates. `make lint` adds
`npm run lint` and `make typecheck` adds `npx tsc -b`, because F1's "a renamed field
breaks the build" only helps if the compiler runs in the fast loop. Before this, it
ran only inside the e2e Docker image build.

**Why.** No backend has any of these today. They are the cheapest automatic gate in
the factory, and matter most once code is written by a local LLM. Pyright chosen
over mypy for speed and stricter inference.

---

## D4 — Configuration via `pydantic-settings`

**Decision.** Every app (simple and rich form) reads env vars through one
`pydantic-settings` `BaseSettings` class. Settings are validated at startup: a
missing/invalid variable crashes the container on boot, not on the first request.
Replaces the simple-form `config.py` + `os.environ` pattern; env-var names stay the same.

**Why.** Consistent with D1 (Pydantic validates at the boundaries), and aligns the
simple form with what rich-form apps already do.

---

## D5 — Shared code: canonical copies + drift check

**Decision.** Cross-app plumbing is shared as **canonical copy-verbatim files**, not
as a runtime package. Each app stays its own repo and keeps a real copy.
- Canonical sources live in `Apps/shared/` (backend and frontend), each file
  carrying a version line, e.g. `# canonical: errors.py v2`.
- A drift-check script reports, per app, which copies are current, outdated, or
  edited locally.
- An intentional local change is labelled in the version line
  (`# canonical: errors.py v2 + local: <reason>`) and reported as intended;
  unlabelled differences fail the check.
- Propagating a new canonical version to the apps is a routine, bounded factory job.

**In scope (canonical):** `Validated` base + common constrained types (D1),
`errors.py` + exception handler (D2), settings base (D4), UoW base, LLM transport
(SSE parsing, JSON-slice helper, `enable_thinking` quirk, config — per
`docs/plans/LLM_ADAPTER_SHARING.md`), logging setup, frontend API-client error handling.
**Never shared:** domain models, ports, prompts, use cases.

**Why.** Apps are separate GitHub repos with independent ghcr builds; a shared
package would need private-repo credentials in CI/Docker and a release + N bumps per
fix. Copying itself isn't the problem — *untracked* copying is: today all 9
`unit_of_work.py` files differ and nobody knows. Each app also stays fully readable
on its own (anti-dark-factory). Consistent with the earlier `docs/plans/LLM_ADAPTER_SHARING.md`
analysis.

**Not chosen (for now).** B — private shared package (release friction, invisible
code). C — monorepo with a uv workspace: discussed and deliberately parked; not to
be revisited unless explicitly reopened.

---

## D6 — Logging: one canonical setup, readable lines, request ids

**Decision.** A canonical `logging_setup.py` (shared per D5), applied once at startup:
- stdlib `logging`; level from settings (`LOG_LEVEL`, D4).
- Human-readable single-line format: timestamp, level, logger, request id, message.
  No JSON (logs are read with `docker logs` / `journalctl`, no collector).
- Request-id middleware: an id on every log line, also returned as a response header
  so a UI error can be matched to server lines.
- Every 500 is logged with its traceback (D2's unknown-error path).
- stdout only; the container runtime keeps the logs. No log files, no extra services.

**Why.** Only 4 of 9 apps configure logging at all (Blibiobot, Chatbot, Learn_German,
Posta). In Pasti, Registro_Spese, Famiglia, Diario and Deployer, INFO logs are dropped
and nothing has timestamps or format.

---

## D7 — Auth: per-app login, one canonical pattern

**Decision.** Each app that needs users keeps its **own** users and login, built from
one canonical pattern (Blibiobot's, shared per D5):
- Domain ports `PasswordHasher` and `TokenService`; adapters `bcrypt` and `pyjwt`
  (plus fakes for tests). Services never import `bcrypt`/`jwt` directly.
- Business code only sees a stable `user_id`.
- No single sign-on. If ever wanted, it means replacing the token adapter, not
  rewriting apps.

**Why.** Four apps (Blibiobot, Chatbot, Learn_German, Diario) each implement
bcrypt + JWT themselves, placed differently; Chatbot and Diario import the libraries
straight into the service layer (hexagonal leak). Apps are reached through a local
WireGuard on the server, not a public endpoint, so a central auth service isn't
justified. Tailscale-based identity was considered and dropped: Tailscale isn't in use.

---

## Open — backend

_None — backend decisions D1–D7 complete._

## F4 — Frontend stack: stay on React (+ TypeScript, Vite), one stack for all apps

**Decision.** React remains the only frontend stack. htmx was compared and not adopted;
Svelte was considered and not built.

**Why.** Compared on the same Famiglia screen (a throwaway exploration, deleted 2026-11-17 after the decision). The
control wanted comes from structure (generated types, one error path, data/view
separation), which React supports. htmx is very readable for simple CRUD, but Chatbot
(streaming, markdown, KaTeX) and Famiglia's week grid need client-side code, so it
would mean two stacks, two blueprint variants, and two patterns for agents and reviewers.

---

## F1 — API types and client generated from OpenAPI

**Decision.** `src/api/schema.d.ts` is generated from the backend's OpenAPI by
`openapi-typescript` (a `make types` target) and never edited by hand. All calls go
through one canonical `openapi-fetch` client (D5) with a middleware that turns every
non-2xx response into an `ApiError {status, code, field, message, requestId}` (D2, D6).
Hand-written `types/*.ts` copies of backend schemas and hand-written fetch wrappers go away.

*Refined (factory build, 2026-11-17):* `make types` exports the schema offline from the
FastAPI app object instead of fetching it from a running backend, so `/build` and CI can
run it (verified on Famiglia: export + openapi-typescript 7.13, no server).

**Evidence.** In the comparison, renaming a backend field broke the TypeScript build
at all five places using it; the type-check passed with React 19,
TanStack Query 5.107 and openapi-fetch 0.17.

---

## F2 — Server state via TanStack Query

**Decision.** Data loading, caching and refresh-after-change go through TanStack Query
hooks (`hooks/use<Resource>.ts`). Mutations invalidate the queries they affect.
No `useEffect` + `useState` fetching, no `onChanged` callbacks passed down for refetching.

---

## F3 — Frontend structure rules

**Decision.**
- Layers: `api/` (generated schema, canonical client, error table) → `hooks/` (data) →
  `components/` (render + local form state). Components never call `api` or `fetch`.
- Error codes become Italian text only in `api/errors.ts` (`messageFor`); never inspect
  status codes or message text in components.
- No validation duplicated from the backend; show the backend's error instead.
  (Pure UX hints such as disabling an empty submit button are fine.)
- Component size guideline: split when a component passes ~250 lines or mixes
  unrelated concerns (Famiglia's `WeekGrid.tsx` is 675).

---

## Open — frontend

_None — frontend decisions F1–F4 complete._

---

## Cleanup of pre-existing blueprint content (2026-11-17)

Reviewed the v1 parts against the apps as they are and the decisions above.

- **Removed (obsolete):** `.env.deploy.example` (Pi-era values; `deploy.sh` takes arguments
  from the Deployer); the manual "ssh in and `docker compose up`" deploy flow (replaced by the
  Deployer + systemd and the flat `~/Apps/<App>/` layout); arm64/QEMU CI builds (no Pi hosts
  anything; the mini-PC is x86_64); the claim that parts of Blibiobot run from the laptop
  (target: everything on the mini-PC).
- **Removed (overkill):** MkDocs + mkdocstrings + Kroki container (few diagrams, generated API
  pages unused). Docs are plain Markdown; ADRs required, Mermaid for diagrams.
- **Simplified:** per-app `CLAUDE.md` holds app-specific facts only, with no copies of
  blueprint content (they drift, same reason as D5). E2E keeps the override-file pattern;
  Blibiobot's `.env.test` approach is a documented exception.
- **Aligned with v2:** Diario no longer named as a reference (D7 violation); the testing
  table includes the static checks; §14 reworded so "drift check" isn't ambiguous.
