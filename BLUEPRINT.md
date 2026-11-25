# App Blueprint

Canonical structure and conventions for full-stack apps in this folder.

**Version 2** (2026-11-16). The v2 code patterns (validation, errors, settings,
logging, quality gates, frontend data layer) come from **`shared/`** (§15). The
rationale for every v2 rule is in `BLUEPRINT_V2_DECISIONS.md` (D1–D7, F1–F4).

Reference implementations:
- **Project scaffolding** (compose, Makefile, deployment, CI, docs): **`Registro_Spese/`**. When in doubt, mirror it.
- **v2 code patterns**: the canonical files in **`shared/`**. Famiglia is the v2 pilot and becomes the full reference once migrated.
- No app is fully on v2 yet: run `make -C shared drift` to see each app's state (§14).

---

## Rules at a glance

Quick-scan checklist of hard rules. Each rule links to the section with full rationale.

### Structure
- App code lives in exactly three root folders: `backend/`, `frontend/`, `e2e/` — extra UIs are siblings (`frontend-reader/`), never nested. [§1]
- Adapter code for optional services (storage, TTS, …) goes **inside `backend/`**, never as a sibling root dir. [§1]
- Third-party static config files (e.g. the Garage `.toml`) may live at root in a flat, same-named folder — one file, no sub-nesting. [§1]

### Naming
- Service names in compose: `api`, `db`, `frontend` — no variation. [§2]
- Compose network: `<app>_network`. [§2]
- **Never** set `container_name` on dev services — let compose auto-name them. [§2, §6]
- Production containers get explicit names: `<app>_api`, `<app>_ui`. [§2]
- ghcr.io images: `ghcr.io/<owner>/<repo>-api` and `…-frontend`. [§2]

### Backend
- Architecture is hexagonal (ports-and-adapters): outer layers import inner, **never the reverse**. [§3]
- ORM mapping is **imperative** (not declarative). [§3a]
- A **Unit of Work** is always required as the transactional boundary. [§3a, §3b]
- Domain model (`domain/model.py`) depends on nothing but Pydantic *types*: no FastAPI, no SQLAlchemy. Entities are stdlib `@dataclass`es mixing in `Validated`, so every field is checked on creation **and on every assignment**. [§3c, D1]
- Rules spanning several fields live in entity methods that change those fields together, never in bare attribute assignment. [§3c, D1]
- Expected failures are `DomainError` subclasses with a stable `code`. Routes contain no `try/except` for them; one handler maps them to `{code, message, field}`. [§3c, D2]
- Settings come from one `pydantic-settings` class, validated at startup; there are no default passwords. [§3c, D4]
- Logging uses one canonical setup: readable stdout lines with a request id, and every 500 logged with its traceback. [§3c, D6]
- Login (where needed) is per app, behind `PasswordHasher` / `TokenService` ports; services never import `bcrypt`/`jwt`. [§3c, D7]
- Quality gates: `ruff format --check`, `ruff check` and `pyright` are part of `make test-backend` and CI. [§3c, §8, D3]
- ORM mapping is invoked **once** via FastAPI `lifespan`, idempotently. [§3a]
- Migrations run **automatically** on container start via `entrypoint.sh` — never manually on the remote. [§3a, §7]
- Stack: Python 3.12 · FastAPI · Pydantic 2 · pydantic-settings · SQLAlchemy 2 · Alembic · uv · pytest · testcontainers · ruff · pyright. [§3a]
- **Default to simple form** (§3a). Graduate to rich form (§3b) only when: a second adapter kind is added, async I/O is needed on adapter calls, or `services.py` exceeds ~300 lines. [§3b]

### Frontend
- Required files in every frontend: `Dockerfile`, `nginx.conf`, `eslint.config.js`, `tsconfig.json`, `vite.config.ts`, `src/api/{schema.d.ts,client.ts,messages.ts,errors.ts}`, `src/hooks/`, `src/components/`, `App.tsx`, `main.tsx`. [§4]
- Playwright is **not** a frontend dependency — it lives in `e2e/`. [§4, §5]
- Stack: React 19 · TypeScript · Vite · TanStack Query · openapi-fetch · vitest · ESLint. One stack for every app; no htmx or Svelte. [§4, F4]
- All API calls use the `/api` prefix; nginx proxies internally to `http://api:80/`. [§4]
- `src/api/schema.d.ts` is **generated** from the backend's OpenAPI (`make types`) and never edited; all calls go through the canonical `api/client.ts`. No hand-written copies of backend types. [§4b, F1]
- Layers: `api/` → `hooks/` (TanStack Query) → `components/`. Components never call `api` or `fetch`. [§4b, F2, F3]
- Error codes become Italian text only via `messageFor` (`api/errors.ts`). Never inspect status codes or message text in components, and never duplicate backend validation. [§4b, F3]

### Shared code
- Cross-app plumbing is **copied** from `shared/`, never imported as a package. Copies keep their `# canonical: <source> vN` header; a local change must be labelled `+ local: <reason>`. `make -C shared drift` fails on unlabelled edits. [§15, D5]

### E2E
- `e2e/` is top-level, never under `frontend/`. [§5]
- Specs are black-box: they talk over HTTP and the browser only — no imports of frontend types or backend models. [§5]
- The e2e stack runs under a separate compose project (`-p <app>_e2e`) so `down -v` cannot wipe the dev DB. [§6, §9]

### Dev compose
- Each app claims an index; all host ports derive from it via the formulas in §2b. Current assignments live in `README.md`. [§2b, §6]
- Load env vars in Makefile with `set -a && . ./.env && set +a` — never `export` from the shell. [§8]

### Deployment
- First deploy only: the app's least-privilege role + database are created by Infrastructure's `init/01-init.sh` (re-run it idempotently if the stack is already up) — alembic creates tables, not the role/database. [§7]

### Required files
- `CLAUDE.md` at repo root — **app-specific facts only** (what the app is, its deviations, its gotchas); never copies of this blueprint. [§11]
- `Makefile` with the full canonical target set. [§8]

---

## 1. Top-level layout

```
<app-name>/
├── backend/                # FastAPI service (see §3)
├── frontend/               # React + Vite SPA (see §4)
├── e2e/                    # Playwright system tests (see §5)
├── deployment/             # Production stack (see §7)
│   ├── docker-compose.yml
│   ├── deploy.sh
│   └── .env.example
├── docs/                   # Plain Markdown (see §10)
│   ├── adr/                # Architecture Decision Records — required
│   ├── work/               # factory work records: NNN-slug/{spec,plan,review}.md (see ../factory/README.md)
│   └── architecture.md     # (optional) overview, Mermaid diagrams inline
├── scripts/                # One-offs (seed data, dev helpers)
├── .github/workflows/
│   └── ci-cd.yml
├── docker-compose.yml      # Dev stack (see §6)
├── Makefile                # Single dev entrypoint (see §8)
├── README.md
├── CLAUDE.md               # Required (see §11)
├── .env.example            # Dev env (DB_*)
└── .gitignore
```

**Rules**
- The **app folders** at the root are `backend/`, `frontend/`, `e2e/` (plus extra frontends like `frontend-reader/` when an app legitimately ships more than one UI — see §4).
- **Adapter code** for optional services (Garage, TTS, etc.) lives inside `backend/` — not as sibling top-level dirs.
- **Static config files** for third-party-image services (e.g. the Garage `.toml`) that get mounted into compose containers as volumes may live at the root in a same-named folder (e.g. `garage/`). They are infrastructure config, not app code; bundling them at the root keeps the volume mount paths short and matches docker-compose conventions. Keep these folders flat — one file, no nesting.
- Backend layout: see §3. The blueprint describes two valid shapes — a **simple form** (single-aggregate, single adapter kind, sync SQLAlchemy) and a **rich form** (multi-aggregate or multi-adapter-kind, async). Both require a Unit of Work.

---

## 2. Naming conventions

| Concept              | Canonical name              |
|----------------------|-----------------------------|
| Backend service      | `api`                       |
| Database service     | `db`                        |
| Frontend service     | `frontend`                  |
| Compose network      | `<app>_network`             |
| Container (dev)      | auto-named (`<project>-<service>-1`) — do **not** set `container_name` for dev services |
| Container (prod)     | `<app>_api`, `<app>_ui` (explicit `container_name` in `deployment/`) |
| Image (ghcr.io)      | `ghcr.io/<owner>/<repo>-api`, `…-frontend` |
| Compose projects     | dev: `<app>` (default, from dir name); e2e: `<app>_e2e` (passed via `-p`) |
| Compose profiles     | `app` (+ optional `extraction`, `tts`, …) |

---

## 2b. Per-app ports

Every app claims an **index**. All of its host ports derive from that index by formula:

| Role                        | Formula         |
|-----------------------------|-----------------|
| Native API (`make backend`) | `5000 + idx`    |
| Native frontend (vite)      | `5170 + idx`    |
| Docker DB                   | `5430 + idx`    |
| Docker / prod frontend      | `80 + 10 × idx` |

The current index assignments (and the full per-app port table) live in the **root `README.md`**. When scaffolding a new app, claim the next free index there and add your app to both the Development and Production tables before writing any port into a compose/Makefile.

---

## 3. Backend layout

Hexagonal / ports-and-adapters. Outer layers import inner; never the reverse.

The blueprint describes two valid shapes. Most apps start with the **simple form**; an app graduates to the **rich form** when it acquires multiple adapter kinds (storage, extraction, summarization, …), multiple impls per kind (mock + real, openai + anthropic, …), async I/O on adapter calls, or multiple aggregates. Both forms keep the same layering rules and **both require a Unit of Work** as the transactional boundary.

### 3a. Simple form

Reference: `Registro_Spese/` for structure (and Famiglia once migrated to v2). Not Diario: its services import `bcrypt`/`jwt` directly, which D7 forbids.

```
backend/
├── domain/
│   ├── __init__.py
│   ├── model.py            # Entities: @dataclass + Validated; no FastAPI/SQLAlchemy
│   ├── errors.py           # canonical (shared/) — DomainError family; never add app errors here
│   └── validated.py        # canonical (shared/) — Validated mixin, NonBlankStr, HexColor
├── adapters/
│   ├── __init__.py
│   ├── orm.py              # SQLAlchemy *imperative* mapping
│   ├── repository.py       # AbstractRepository + SqlRepository
│   └── unit_of_work.py     # AbstractUnitOfWork + SqlAlchemyUnitOfWork
├── services/
│   ├── __init__.py
│   └── services.py         # Application service layer (business ops)
├── entrypoints/
│   ├── __init__.py
│   ├── main.py             # FastAPI app + routes (no try/except for domain errors)
│   ├── schemas.py          # Pydantic request/response schemas — reuse domain types (NonBlankStr, …)
│   ├── error_handlers.py   # canonical (shared/) — install_error_handlers, ERROR_RESPONSES
│   └── logging_setup.py    # canonical (shared/) — configure_logging, RequestIdMiddleware
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── alembic.ini
├── tests/
│   ├── conftest.py         # map_orm, in_memory_db, session fixtures
│   ├── unit/               # SQLite in-memory
│   └── integration/        # testcontainers Postgres
├── settings_base.py        # canonical (shared/) — AppSettings (pydantic-settings)
├── settings.py             # class Settings(AppSettings) + get_settings() — replaces v1 config.py
├── database.py             # get_session_factory(): engine built lazily from get_settings()
├── Dockerfile
├── entrypoint.sh           # alembic upgrade head; exec "$@"
├── pyproject.toml
├── uv.lock
└── .python-version         # 3.12
```

**Stack**: Python 3.12 · FastAPI · Pydantic 2 · pydantic-settings · SQLAlchemy 2 (imperative mapping) · Alembic · uv · pytest · testcontainers · ruff · pyright.

**Settings pattern** (v2, D4; replaces v1 `config.py` with `os.environ`):
```python
# settings.py
from functools import lru_cache
from settings_base import AppSettings

class Settings(AppSettings):
    pass                      # app-specific fields go here (llm_base_url, …)

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
Same env-var contract as before (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, or `DATABASE_URL`), plus `LOG_LEVEL`. When `DB_HOST=localhost`, use the host-mapped port (e.g. `5433`); inside Docker, override `DB_HOST=db` and `DB_PORT=5432` in compose. `DB_PASSWORD` has no default: if it's missing, the container fails at boot.

**When settings are checked**: at startup, in `lifespan`, not when a module is imported.
`database.py` builds the engine lazily (`@lru_cache get_session_factory()`), and the UoW
resolves it on first use. So unit tests and the OpenAPI export (`make types`) import the
app without any env vars, while a missing variable still stops the app at boot.

**`main.py` wiring** (v2):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()          # validate first: a missing DB_PASSWORD stops startup here
    configure_logging(settings.log_level)
    domain_mapper()
    yield

app = FastAPI(lifespan=lifespan, responses=ERROR_RESPONSES)
app.add_middleware(RequestIdMiddleware)
install_error_handlers(app)
```

**ORM mapping** is invoked once via FastAPI `lifespan` (`domain_mapper()`), and is idempotent.

**Migrations** run automatically via `entrypoint.sh` on container start.

**`pyproject.toml` dependency groups**: `dev` (pytest + testcontainers + ruff + pyright). No `docs` group: docs are plain Markdown (§10).

### 3b. Rich form

Reference: `Blibiobot/`.

The rich form makes three deliberate departures from the simple form. **Everything else** (layering rules, UoW boundary, hexagonal discipline, migrations on container start, pyproject groups) is identical.

1. **`src/` layout**: package lives under `backend/src/<app>/`. Used when the app ships as a published image and wants standard Python packaging semantics. `pyproject.toml` declares `[tool.setuptools.packages.find] where = ["src"]`; Dockerfile does `COPY src ./src`.

2. **Adapters sub-packaged by adapter kind**, with one subfolder per concrete impl:
   ```
   adapters/
   ├── persistence/postgres/
   │   ├── database.py
   │   ├── orm.py
   │   ├── <aggregate>_repository_impl.py
   │   └── unit_of_work.py
   ├── storage/<impl>/<impl>_storage_adapter.py
   ├── extraction/<impl>/<impl>_extractor_adapter.py
   ├── summarization/{mock,openai}/<impl>_summarizer_adapter.py
   └── …
   ```
   Mapping is imperative, exactly as §3a (`orm.py` + `start_mappers()` in `lifespan`).

   This is appropriate when an app has more than ~2 adapter kinds or carries mock + real impls side-by-side. Each adapter kind has a corresponding **port** under `domain/<aggregate>/ports/<port_name>.py` (an ABC). Concrete impls inherit the port.

3. **Services split per use case**, one file per command:
   ```
   services/<aggregate>/
   ├── upload_<aggregate>.py
   ├── delete_<aggregate>.py
   ├── list_<aggregate>s.py
   └── …
   ```
   Each file exports one `<Verb><Aggregate>UseCase` class whose `__init__` takes the dependencies it needs (UoW factory, storage, summarizer, …) and whose `execute(...)` runs the command. No hidden globals, no module-level singletons.

4. **`entrypoints/` gains two pieces**:
   - `dependencies.py` — FastAPI `Depends(...)` providers that wire settings → adapters → use cases. This is the only place that knows which concrete adapter (mock vs. real) is in play; selection is driven by env-var presence on `Settings`.
   - `routers/<aggregate>.py` — one `APIRouter` per aggregate, mounted from `main.py`. `schemas.py` stays flat at the entrypoints root.

**Config**: rich-form apps define `class Settings(AppSettings)` in `dependencies.py` (or next to it), with the canonical `settings_base.py` alongside, and use `sqlalchemy_url(driver="postgresql+asyncpg")`. The env-var contract is the same as the simple form.

**Database**: there is **no** top-level `backend/database.py`. The engine + session factory live next to the repositories at `adapters/persistence/postgres/database.py`. The UoW (`adapters/persistence/postgres/unit_of_work.py`) wraps the session factory.

**Async**: the rich form typically uses async SQLAlchemy (`AsyncSession`, `async_sessionmaker`, asyncpg). The UoW is an async context manager:
```python
class AbstractUnitOfWork(ABC):
    documents: DocumentRepository
    async def __aenter__(self) -> "AbstractUnitOfWork": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...   # commit on success, rollback on error
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

Services take a `uow_factory: Callable[[], AbstractUnitOfWork]` so the same use case is usable both inline-from-a-request and from a background task — each `async with uow_factory() as uow: …` block is its own transaction.

**When to graduate**: don't pre-emptively. Start in the simple form; refactor to the rich form when (a) you add a second adapter kind beyond persistence, (b) you need async I/O on adapter calls, or (c) `services.py` crosses ~300 lines. The migration is mechanical.

### 3c. Cross-cutting backend patterns (v2)

These apply to both forms. Canonical code is in `shared/backend/` (§15); full rationale is in `BLUEPRINT_V2_DECISIONS.md`.

**Validation (D1).** Entities are stdlib `@dataclass`es that mix in `Validated`; fields are typed with Pydantic constraint types:
```python
@dataclass
class FamilyMember(Validated):
    name: NonBlankStr
    color: HexColor
    member_id: uuid.UUID = field(default_factory=uuid.uuid4)
```
Rules that span several fields go in a method that changes those fields together and checks once:
```python
    def reschedule(self, recurrence: Recurrence, date: date | None, weekday: int | None) -> None:
        if recurrence is Recurrence.ONE_OFF and (date is None or weekday is not None):
            raise InvalidInput("one-off needs a date and no weekday", field="date")
        ...
        self.recurrence, self.date, self.weekday = recurrence, date, weekday
```
- Every field is validated on construction **and on every assignment**. A bad value raises `InvalidInput(field=<name>)`.
- Do **not** make entities Pydantic `BaseModel`s or Pydantic dataclasses: both break SQLAlchemy imperative mapping (verified, D1).
- Not covered: in-place mutation (`list.append`), rows *loaded* from the DB (not re-checked on load), and attributes starting with `_`.
- API schemas (`schemas.py`) reuse the domain's constrained types instead of re-declaring weaker ones (`str`).

**Errors (D2).**
- `domain/errors.py` is the canonical family, copied verbatim. App-specific errors live in `domain/model.py` next to the entities that raise them (`class MemberInUse(Conflict): code = "member_in_use"`), moving to `domain/app_errors.py` when model.py gets crowded. Adding them to the canonical file would make the drift check fail.
- A bare `DomainError` is allowed as a fallback (→ 400), but prefer one of the kinds. v2 of the file (Chatbot 002) adds `Unauthorized` (401), `Forbidden` (403) and `PayloadTooLarge` (413).
- Services raise only these. Mapping: `Unauthorized` → 401, `Forbidden` → 403, `NotFound` → 404, `Conflict` → 409, `PayloadTooLarge` → 413, `InvalidInput` and request validation → 422, other `DomainError` → 400, `HTTPException` → its status, anything else → a logged 500 with a generic message.
- The body is always `{"code", "message", "field"}`. `message` is English and for debugging; the frontend shows a translation of `code`.
- Routes don't catch domain errors. `ERROR_RESPONSES` puts `ErrorResponse` into OpenAPI, so the frontend's generated types know the error shape.
- A plain `ValueError` or a stray Pydantic `ValidationError` reaching the handler is a **bug** (500), not user input.

**Logging (D6).**
- `configure_logging(settings.log_level)` runs once; `RequestIdMiddleware` is added to the app.
- Lines look like `2026-11-16 10:42:01 INFO services.services req=7f3a9c01d2e4 Member created`. The logger name is the module name (`getLogger(__name__)`), so it's `services.services` in the simple form and `<app>.services…` in the rich form (§3b).
- The id is returned in the `X-Request-ID` response header, and the frontend's `ApiError.requestId` carries it.
- One access line per request (`app.access`); `/health` is quiet. Use `logging.getLogger(__name__)` everywhere and never `print`.

**Auth (D7), only for apps with users.**
- Each app keeps its own users and login, following Blibiobot's structure: domain ports `PasswordHasher` and `TokenService`, adapters `adapters/security/{bcrypt,jwt,fake}/`, and wiring in `dependencies.py`.
- Services see only a `user_id`. Services and the domain never import `bcrypt` or `jwt`.
- The adapters are canonical (D5): `BcryptPasswordHasher`, `PyJwtTokenService` and `FakePasswordHasher` (tests only, never wired) in `shared/backend/adapters/security/{bcrypt,jwt,fake}/`. bcrypt runs in a worker thread, cuts passwords to 72 bytes and treats a malformed hash as a failed login.
- The ports stay each app's own (§15), in this shape: `PasswordHasher` with async `hash(plain)` / `verify(plain, hashed) -> bool`; `TokenService` with `issue(subject, claims) -> token` and `decode(token) -> subject`. They speak in plain values, not in the app's `User`. `decode` raises `TokenExpired` (code `token_expired`), a subclass of `InvalidToken` (code `invalid_token`); both errors live in the app's domain. Only the adapters' import lines point at the app's ports. Chatbot is the reference (`domain/user/ports/`).
- No single sign-on: apps are reached over the server's local WireGuard.

**Quality gates (D3).** Every backend's `pyproject.toml` carries (copy from `shared/pyproject.toml`):
```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]

[tool.ruff.lint.isort]
known-first-party = ["domain", "adapters", "services", "entrypoints", "settings", "settings_base", "database"]   # simple form

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
```
- Rich form: replace the isort block with `src = ["src"]` under `[tool.ruff]`.
- `ruff` and `pyright` go in the `dev` dependency group.
- Gates are introduced **per app, when that app is migrated to v2**. Existing violations are fixed, or explicitly baselined (`# noqa: <rule> — <reason>`, `# pyright: ignore[<rule>]`), never silenced wholesale.
- Gotcha: ruff respects `.gitignore`. A folder ignored by git, like the old `Apps/` root `*` rule, is silently skipped ("No Python files found").

---

## 4. Frontend layout

```
frontend/
├── src/
│   ├── api/
│   │   ├── schema.d.ts     # GENERATED from backend OpenAPI (`make types`) — never edit
│   │   ├── client.ts       # canonical (shared/) — typed client + ApiError
│   │   ├── messages.ts     # canonical (shared/) — makeMessageFor
│   │   └── errors.ts       # per app: messageFor = makeMessageFor({ code: 'Italian text', … })
│   ├── hooks/              # use<Resource>.ts — TanStack Query queries + mutations
│   ├── components/         # rendering + local form state only
│   ├── utils/              # (optional) pure helpers (dates, images, …)
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css           # (optional) global styles — omit if the app uses inline styles
├── Dockerfile              # Multi-stage Node 20 → nginx
├── nginx.conf              # Serves SPA + proxies /api/ → http://api:80/
├── eslint.config.js
├── index.html
├── package.json
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
└── vite.config.ts
```

**Stack**: React 19 · TypeScript · Vite · TanStack Query 5 · openapi-fetch (+ `openapi-typescript` as dev dep) · vitest · ESLint. TailwindCSS is recommended but optional; apps may choose inline styles instead.
(Playwright is *not* a frontend dependency — see §5.)

**Required vs. optional**:
- **Required** in every frontend: `Dockerfile`, `nginx.conf` (or `nginx.conf.template` if upstream is runtime-configurable), `eslint.config.js` (+ a `lint` script in `package.json`), `tsconfig.json`, `vite.config.ts`, `src/api/{schema.d.ts,client.ts,messages.ts,errors.ts}`, `src/hooks/`, `src/components/`, `App.tsx`, `main.tsx` (wraps `<App />` in `QueryClientProvider`).
- **Optional**, depending on app needs:
  - `src/index.css` — omit if the app uses inline styles (a legitimate choice per Blibiobot/ADR-009). The blueprint does not prescribe styling strategy.
  - `src/utils/` — only when needed.
  - `tsconfig.app.json` + `tsconfig.node.json` — the project-references split is preferred (matches the Vite scaffold and lets `tsc -b` cache builds), but a single flat `tsconfig.json` is acceptable in apps that don't use `tsc -b`.
- **Gone in v2**: `src/types/` with hand-written copies of backend schemas, and hand-written fetch wrappers (`familyService.ts`-style). Use `components['schemas'][…]` from the generated `schema.d.ts`. Frontend-only types (UI state) may live next to the component that uses them.

**`package.json` scripts** (canonical):
```json
{
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run --passWithNoTests",
  "test:watch": "vitest --passWithNoTests"
}
```
Types are generated by `make types` (§8), **offline**: the backend's OpenAPI schema is exported straight from the FastAPI app object (no server, no database connection), then `openapi-typescript` turns that file into `src/api/schema.d.ts`. So it works anywhere, including in the factory's `/build` and in CI:
```make
types:
	@set -a && . ./.env && set +a && tmp=$$(mktemp --suffix=.json) && \
	(cd backend && uv run python -c "import json, sys; from entrypoints.main import app; json.dump(app.openapi(), sys.stdout)") > $$tmp && \
	(cd frontend && npx openapi-typescript $$tmp -o src/api/schema.d.ts) && rm -f $$tmp
```
(Rich form: import `<app>.entrypoints.main`. Importing `main` needs no env vars, because settings are checked in `lifespan`, not at import (D4, §3c); loading `.env` is harmless and covers app settings read at import, if any.)

API calls always use the `/api` prefix; nginx proxies to `http://api:80/`.

### 4b. Data and error rules (v2: F1–F3)

Reference code: `shared/frontend/src/api/`. Full worked example: Famiglia's frontend (`Famiglia/frontend/src/`: `api/errors.ts`, `hooks/useMembers.ts`, `hooks/useWeek.ts`; ADR-009).

- **Types are generated, never copied (F1).** After a backend schema change, run `make types` and commit the regenerated `schema.d.ts` together with the backend change. A renamed field then shows up as a compile error at every use (verified).
- **One client (F1).** All calls go through `api` from `api/client.ts`: `api.GET('/members')`, `api.PATCH('/members/{member_id}', { params, body })`. Every non-2xx response, and every network failure, becomes an `ApiError {status, code, field, message, requestId}`.
- **Data lives in hooks (F2).** Each resource gets `hooks/use<Resource>.ts`, with `useQuery` for reads and `useMutation` for writes. Writes invalidate the queries they affect: `onSuccess: () => qc.invalidateQueries({ queryKey: [...] })`. No `useEffect` + `useState` fetching, and no `onChanged` callbacks passed down just to trigger a refetch.
- **Components render (F3).** Components hold UI and form state only, and never import `api` or call `fetch`. Split a component when it passes ~250 lines or mixes unrelated concerns.
- **Errors are shown, not parsed (F3).** Show errors with `{error && <div>{messageFor(error)}</div>}`. Never inspect `status` or the message text in a component (v1's `msg.includes('409')` is the anti-pattern). Add an app-specific code to `api/errors.ts`; `code:field` keys (e.g. `'invalid_input:name'`) allow field-specific messages.
- **No duplicated validation (F3).** Don't re-implement backend rules in the UI; submit, and show the backend's error. UX hints such as disabling a submit button while the form is empty are fine.

### Multi-frontend apps

An app may legitimately have more than one frontend when the UIs have distinct concerns and audiences (e.g. an admin/management SPA and a separate reader SPA optimised for phones). When that's the case:

- Each frontend lives as a sibling at the repo root: `frontend/`, `frontend-reader/`, etc. Don't nest one inside the other.
- Each has its own `package.json`, Dockerfile, nginx config, and vite config. Routing choices (router vs no-router), styling (Tailwind vs inline), and dependencies stay independent.
- The Makefile gets one target per frontend: `make frontend`, `make frontend-reader`, …
- The `app` profile in `docker-compose.yml` may or may not include every frontend — include only the ones needed for e2e and local full-stack runs. Frontends that exist solely for production can be omitted from dev compose entirely.
- CI publishes one ghcr.io image per shipped frontend (e.g. `ghcr.io/<owner>/<repo>-reader`). Frontends that don't ship don't get an image.
- A frontend that talks to a remote backend (e.g. reader → api running on a different host in prod) configures its `/api` upstream at container start, not at build time, via an env-var-templated nginx config (`/etc/nginx/templates/default.conf.template` with `${API_UPSTREAM}`).
- Each frontend may have its own e2e spec file under the same top-level `e2e/` directory — keep them in one Playwright project rather than splitting; the spec name (`reader.spec.ts`) is enough disambiguation.

Example: Blibiobot has `frontend` (admin) and `frontend-reader`. Like every app, all of its parts are meant to run on the mini-PC (§7). Historically parts of it ran from source on the laptop; aligning that is part of Blibiobot's v2 migration.

---

## 5. E2E layout

Top-level `e2e/` keeps Playwright system tests independent of either app side. Specs treat the running stack (frontend → nginx → api → db) as a black box.

```
e2e/
├── *.spec.ts               # Playwright specs (flat layout — Playwright default)
├── helpers.ts              # shared selectors, fixtures, API helpers
├── playwright.config.ts
├── tsconfig.json
├── package.json
└── package-lock.json
```

**Stack**: Playwright · TypeScript (own `tsconfig`, no React, no Vite).

**`package.json` scripts**:
```json
{
  "test": "playwright test",
  "test:ui": "playwright test --ui",
  "install-browsers": "playwright install chromium"
}
```

**Why top-level, not under `frontend/`**
- E2E tests exercise the whole system, not just the UI. Placement should reflect that.
- Some apps (e.g. Blibiobot) have multiple frontends — the suite must be able to reach any of them.
- Frontend deps (React, Vite, Tailwind) don't belong to a test runner; isolating Playwright keeps both installs lean.
- Cleaner cognitive model: `backend/` exercises Python code, `frontend/` exercises React, `e2e/` exercises the deployed stack.

**Black-box discipline**: E2E specs talk to the system over HTTP and through the browser — they do not import frontend types or backend models. If they need a shape, they declare a minimal local interface. This keeps the suite honest about what an end user can observe and avoids accidental coupling that would let bugs hide.

**Base URL** is supplied via `playwright.config.ts`:
```ts
baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:90'
```
Makefile sets `E2E_BASE_URL` only when targeting non-default environments; locally the default suffices.

---

## 6. Dev `docker-compose.yml` (root) + `docker-compose.e2e.yml` override

### `docker-compose.yml` (the canonical dev stack)

- `db` — `postgres:15-alpine`, healthcheck via `pg_isready`, host-published on the per-app Docker DB port (see §2b). **This service is dev-only.** In production every app connects to the shared Postgres managed by the `Infrastructure/` repo instead (see §7b).
- `api` — builds `./backend`, profile `app`, env_file `.env`, overrides `DB_HOST=db`, healthcheck on `GET /health` (same in `deployment/`). `/health` is liveness only: it returns `{"status": "ok"}` without touching the database, is left out of the OpenAPI schema (`include_in_schema=False`), and writes no access line (the canonical `RequestIdMiddleware` keeps it quiet, §3c).
- `frontend` — builds `./frontend`, profile `app`, host-published on the per-app frontend port (see §2b), depends_on `api: service_healthy`.
- One bridge network: `<app>_network`.
- **No `container_name`** on dev services — let compose auto-name them via the project (`<app>-api-1` etc.) so the e2e project can spin up its own copies without colliding.

Profiles discipline: nothing the user runs day-to-day starts implicitly — `make backend`/`make frontend` activate the right profile.

### E2E isolation

The e2e stack runs in a **separate compose project** (`-p <app>_e2e`) so the e2e teardown's `down -v` cannot wipe the dev db volume.

Host ports are kept from colliding with a still-running dev stack by a **`docker-compose.e2e.yml` override** that unbinds them:

```yaml
services:
  db:
    ports: !reset []
```

`!reset` clears the inherited `ports` list (compose v2 spec). Frontend keeps its host port — Playwright runs on the host and needs to reach the SPA there. If the dockerized dev frontend is up on the same port, e2e fails loudly with a bind error, which is acceptable: rare overlap, obvious failure.

*Exception:* Blibiobot (many services binding host ports) uses a generated `.env.test` with parallel ports in the 5500 band instead; see its Makefile (`make env-test`). Don't copy that into other apps.

---

## 7. `deployment/`

**Everything runs on the mini-PC** (x86_64), from **published ghcr.io images**: every app's backend and frontends, plus `Infrastructure/`. Nothing runs from source in production, on the laptop or elsewhere.

**Deployment is plain commands**: CI publishes the images, the mini-PC pulls them, and anything else is a command you run yourself (below). The files in `deployment/` are each app's contract with the mini-PC:
- `deployment/docker-compose.yml` — references `ghcr.io/<owner>/<repo>-{api,frontend}:${IMAGE_TAG:-latest}`. No `db` (uses the external `shared_postgres` on `shared_network`).
- `deployment/.env.example` — `DB_USER`, `DB_PASSWORD`, `DB_NAME`, optional `IMAGE_TAG`; seeds the remote `.env` the first time.
- `deployment/deploy.sh <user> <host> <remote_path>` — copies the two files above to the mini-PC and creates `.env` from the example if it doesn't exist. Run it from the laptop (`cd <App>/deployment && ./deploy.sh <user> <server> ~/Apps/<App>`); it's the only place that knows which files an app ships.

**Remote layout** (flat, one folder per app):
```
~/Apps/
├── <App>/                 # docker-compose.yml + .env (copied by deploy.sh)
├── Infrastructure/
├── install-services.sh    # installs the systemd units (§7b)
└── backups/
```

**Update flow**: normally automatic — CI publishes a new image on every push to `main`, and the `docker-autoupdate` timer on the mini-PC (installed by Infrastructure) pulls and restarts all stacks every 5 minutes. **A push to `main` is a production deploy.** The timer runs as root, so root must be logged in to GHCR (`sudo docker login ghcr.io -u <github-user>`, a PAT with `read:packages`); otherwise every pull fails with `unauthorized` and nothing deploys (check: `journalctl -u docker-autoupdate.service --since "15 min ago" | grep -E "WARNING|unauthorized"`).

Everything else, on the mini-PC:
```bash
cd ~/Apps/<App>
nano .env                                              # edit settings, then: docker compose up -d
docker compose pull && docker compose up -d            # apply a new image now, without waiting
sudo systemctl start --no-block docker-autoupdate.service   # or: update every app now
# roll back: set IMAGE_TAG=<previous tag> in .env, then
docker compose pull && docker compose up -d
```
Changed `deployment/` files are copied from the laptop with `deploy.sh` (above), then applied with `docker compose up -d`.

### Migrations on the remote

Migrations apply **automatically** on every container start — no manual step on the mini-PC.

- The api Dockerfile bakes `backend/alembic/` + `alembic.ini` into the image via `COPY . .`.
- `backend/entrypoint.sh` runs `alembic upgrade head` before `exec "$@"` (uvicorn).
- The image runs from the venv it built: the Dockerfile sets `ENV PATH="/app/.venv/bin:$PATH"` and `CMD ["uvicorn", "entrypoints.main:app", "--host", "0.0.0.0", "--port", "80"]`. **Never `uv run` in the Dockerfile's `CMD` or in `entrypoint.sh`**: `uv run` first syncs the default groups, `dev` included, so every container start downloads the dev tools. That makes start-up slow and dependent on the network, and the healthcheck gives up (Famiglia 003 deploy; Famiglia ADR-010). uv is for building the image (`uv sync --frozen --no-dev`) and for laptop commands only.
- On every container (re)start, alembic upgrades the schema, then uvicorn starts.

Manual escape hatches (rarely needed):
```bash
# in ~/Apps/<App>/ on the mini-PC
docker compose exec api alembic upgrade head        # against the running container
docker compose run --rm api alembic upgrade head    # one-shot, no live container
```

**First-deploy gotcha**: alembic creates *tables*, not the database or role. The app's least-privilege role + database are created by `Infrastructure/init/01-init.sh` (see §7b). If the infrastructure stack is already running, re-run that idempotent script on the mini-PC:
```bash
docker exec shared_postgres sh /docker-entrypoint-initdb.d/01-init.sh
```
The local Make targets sidestep this because docker-compose's `db` service auto-creates the database from `POSTGRES_DB` (dev connects as the superuser; per-app roles are a production concern).

---

## 7b. Shared production infrastructure — `Infrastructure/`

`Infrastructure/` is a **separate git repo** at the `Apps/` root. It runs the shared services that all apps depend on in production. Deploy it first, before any app.

### What it provides

- `shared_postgres` — a single `postgres:15-alpine` container, named explicitly so app compose files can reference it.
- `shared_garage` — a single [Garage](https://garagehq.deuxfleurs.fr/) S3-compatible object store, named explicitly so apps that need object storage (e.g. Blibiobot) can reference it.
- `shared_network` — a named Docker bridge network. Every app's production `deployment/docker-compose.yml` joins this network instead of running its own `db` or storage service.
- `init/01-init.sh` — executed on first boot (when the volume is empty) to create one **least-privilege role + database per app**, each role owning only its own database (so a compromise of one app can't reach another's data). Idempotent, so it can also be re-run against a live `shared_postgres` to add a new app. One `create_app` line per app, plus a matching `<APP>_DB_PASSWORD` in `.env` (and in the app's `deployment/.env`).
- `garage_init.sh` — idempotent Garage initialisation: assigns node layout, imports the access key, creates the bucket, and grants permissions. Runs as a one-shot container on every `docker compose up -d`.
- Systemd units (`deployment/systemd/`) — auto-start services on boot and depend on `infrastructure-stack` so shared Postgres and Garage are always up before any app.
- `deployment/db_backup.sh` — backs up all databases nightly, retains 7 days.

### Dev vs production database

| Environment | Database | Who starts it |
|-------------|----------|---------------|
| Local dev   | Per-app `db` container in root `docker-compose.yml` | `make backend` / `make db` |
| E2E         | Per-app `db` container in the e2e compose project | `make e2e` |
| Production  | Shared `shared_postgres` in `Infrastructure/` | `Infrastructure/` stack |

There is no shared Postgres in local dev. Each app is fully self-contained during development.

### Adding a new app to Infrastructure

When a new app is deployed for the first time, two steps are required in `Infrastructure/`:

1. **Add the role + database to `init/01-init.sh`** and a matching `<APP>_DB_PASSWORD` to `.env` (and the app's `deployment/.env`):
   ```sh
   create_app <new_app>_app <new_app_db> "${<NEW_APP>_DB_PASSWORD:?...}"
   ```
   This is picked up automatically on the next fresh volume init. If the stack is already running (volume exists), re-run the idempotent script instead, on the mini-PC:
   ```bash
   docker exec shared_postgres sh /docker-entrypoint-initdb.d/01-init.sh
   ```

2. **Add a systemd unit** (`deployment/systemd/<app>-stack.service`) that `After=` and `Requires=infrastructure-stack.service`, then run `install-services.sh` on the remote to register it.

---

## 8. `Makefile` — canonical targets

Every target runnable from the repo root. Required set:

| Target           | Purpose                                                                                                |
|------------------|--------------------------------------------------------------------------------------------------------|
| `env`            | Generate `.env` from `.env.example` + random `DB_PASSWORD`                                             |
| `sync`           | `cd backend && uv sync`                                                                                |
| `db`             | `docker compose up -d --wait db` — used as a prereq by `migration` so dev workflows are self-healing   |
| `migration`      | depends on `db` + `sync`; runs `alembic upgrade head`                                                  |
| `backend`        | depends on `migration`; starts `uvicorn entrypoints.main:app --reload`                                 |
| `frontend`       | `cd frontend && npm run dev`                                                                           |
| `unit`           | `unit-backend` + `unit-frontend`                                                                       |
| `unit-backend`   | `pytest tests/unit` (SQLite in-mem)                                                                    |
| `unit-frontend`  | `npm test` (vitest)                                                                                    |
| `integration`    | `pytest tests/integration` (testcontainers Postgres)                                                   |
| `e2e`            | isolated stack via `docker compose -p $(E2E_PROJECT) -f docker-compose.yml -f docker-compose.e2e.yml --profile app up --wait` + `cd e2e && npm test` |
| `lint`           | backend `uv run ruff format --check . && uv run ruff check .` + frontend `npm run lint` (v2, D3)       |
| `typecheck`      | backend `uv run pyright` + frontend `npx tsc -b` — seconds, so the generated-types check (F1) runs in the fast loop, not only in the e2e image build (v2, D3) |
| `types`          | regenerate `frontend/src/api/schema.d.ts` from the backend's OpenAPI, offline — no running server (§4, v2, F1) |
| `drift`          | `make -C ../shared drift APP=<App>` — this app's canonical copies vs `shared/` (v2, D5)                |
| `test`           | `lint + typecheck + unit + integration + e2e` (full pyramid)                                           |
| `test-backend`   | `lint + typecheck + unit-backend + integration`                                                        |
| `clean`          | `docker compose down -v` for both the dev project and the e2e project                                  |

Discipline: env vars are loaded via `set -a && . ./.env && set +a` — never `export` from the shell.

---

## 9. Testing strategy

The test pyramid spans backend, frontend, and a top-level system suite — one location per layer.

| Layer               | Location                          | Database                                      | Runs with             |
|---------------------|-----------------------------------|-----------------------------------------------|-----------------------|
| Backend unit        | `backend/tests/unit/`             | SQLite in-memory (`conftest.py` fixture)      | `make unit-backend`   |
| Frontend unit       | `frontend/src/**/*.test.tsx`      | n/a                                           | `make unit-frontend`  |
| Backend integration | `backend/tests/integration/`      | Real Postgres via **testcontainers**          | `make integration`    |
| End-to-end          | `e2e/*.spec.ts` (Playwright)      | Real Postgres via `compose --profile app`     | `make e2e`            |
| Static checks (v2)  | whole `backend/` and `frontend/`  | n/a — ruff, pyright, ESLint, `tsc -b`         | `make lint typecheck` |

Static checks run first: they take seconds and catch what tests can't (a renamed field the frontend still uses, an unsorted import, a wrong type).

**Why E2E is top-level** — Playwright specs exercise the whole deployed stack (frontend → nginx → api → db). They don't belong to either side, and isolating them keeps both `frontend/` and `backend/` focused on their own runtimes (see §5 for the full rationale).

The Makefile bridges all three locations and **isolates** the e2e stack from the dev stack:

```make
E2E_PROJECT := <app>_e2e

e2e:
    docker compose -p $(E2E_PROJECT) -f docker-compose.yml -f docker-compose.e2e.yml --profile app up -d --build --wait
    @trap 'docker compose -p $(E2E_PROJECT) --profile app down -v' EXIT INT TERM; \
      ( cd e2e && npm install --silent && npx playwright install chromium >/dev/null && npm test )
```

`-p $(E2E_PROJECT)` puts the e2e containers, network, and volume under a separate compose project, so `down -v` only nukes e2e state. The dev db (and any in-progress `make backend` session) survives untouched.

**Aggregates**

- `make test-backend` = `unit-backend + integration` — no Docker, fast feedback loop.
- `make test` = full pyramid (`unit + integration + e2e`) — quality gate before push.


---

## 10. Docs — plain Markdown in `docs/`

Docs are plain Markdown, read in the editor or on GitHub. No MkDocs, no Kroki container, no generated API reference: the code, its docstrings and the generated OpenAPI (`/docs` on the running API) already cover that.

- **Required: `docs/adr/`.** One Architecture Decision Record per real decision, numbered `001-*.md`, `002-*.md`, …: *Context* (why a decision was needed), *Decision*, *Consequences*. A short `docs/adr/README.md` lists them. ADRs are how you (and the factory's reviewer) know *why* the code looks the way it does.
- **Optional: `docs/architecture.md`** — a one-page overview when the app is more than plain CRUD. Diagrams as Mermaid code blocks inside the Markdown (GitHub and most editors render them); no separate diagram files or renderer.
- The app's `README.md` is the entry point: what the app does, how to run it (`make …`), where the ADRs are.

v1 leftovers to remove when an app is migrated: `mkdocs.yml`, `docs/api-reference/`, the `docs` dependency group, the `kroki` compose service and the `make docs` target. Existing `docs/diagrams/*.puml` may be converted to Mermaid or deleted.

---

## 11. `CLAUDE.md`

Required at the app's repo root, and **short**. Claude Code also loads `Apps/CLAUDE.md` automatically (it reads every `CLAUDE.md` from the working folder up), which points to this blueprint, so an app's `CLAUDE.md` holds only what is **specific to that app**:

1. **What the app is** — two or three sentences, plus its form (simple/rich) and port index.
2. **Its model in brief** — the aggregates/entities and any non-obvious domain rule (e.g. Famiglia's recurrence-by-projection), with links to the relevant ADRs.
3. **Deviations** — anything that differs from this blueprint, and why (extra services, extra make targets, Blibiobot's `.env.test` e2e exception, …).
4. **Gotchas** — things that have bitten you in this app and would bite an agent too.

Do **not** copy blueprint content (standard make targets, the test table, layer descriptions, CI shape): copies drift, the same problem §15 solves for code. If something applies to every app, it belongs here in the blueprint.

---

## 12. CI/CD — `.github/workflows/ci-cd.yml`

Pipeline shape (sequential):

1. **`test`** — uv setup → `ruff format --check` → `ruff check` → `pyright` → `pytest tests/unit` → `pytest tests/integration`, plus frontend `npm ci` → `npm run lint` → `npx tsc -b` → `npm test` (lint/typecheck steps from v2, D3). The drift check is **not** in app CI: `shared/` lives in the `Apps/` root repo, not in the app repo. Run it locally (`make drift`) and in the factory's review step.
2. **`browser-e2e`** — generate throwaway `.env` → `compose --profile app up --build --wait` → `cd e2e && npm ci && npx playwright install --with-deps chromium && npm test` → upload report on failure → tear down.
3. **`build-backend`** & **`build-frontend`** (parallel, depend on `browser-e2e`) — buildx, push **`linux/amd64` only** (the mini-PC is x86_64) to `ghcr.io/<owner>/<repo>-{api,frontend}`. No QEMU and no arm64: those existed for the Raspberry Pi, which no longer hosts anything. Tags: `latest`, `main` and `sha-<7 chars>` (`docker/metadata-action` with `tags: type=ref,event=branch` + `type=sha`); the `sha-…` tag is what `IMAGE_TAG` pins to roll back (§7).

Every job runs on `ubuntu-24.04`, not `ubuntu-latest`: `ubuntu-latest` is Ubuntu 26.04, where Playwright can't install Chromium yet.

---

## 13. Checklist for a new app

Default to **simple form** (§3a) — graduate to rich form (§3b) only when the triggers in §3b's "When to graduate" hit.

- [ ] Claim the next free index in `README.md`'s port tables; add the app to both the Development and Production tables (see §2b).
- [ ] Scaffold the top-level tree from §1.
- [ ] Copy `Registro_Spese/Makefile` → adjust the seed data target if any.
- [ ] Copy `Registro_Spese/docker-compose.yml` → rename network + container prefixes.
- [ ] Copy `Registro_Spese/deployment/` → adjust image names + container prefixes.
- [ ] Copy `Registro_Spese/backend/{Dockerfile,entrypoint.sh,database.py,alembic/}` → keep verbatim, except `database.py` reads `get_settings().sqlalchemy_url()` (no `config.py` in v2). Until Registro_Spese is migrated, its `Dockerfile` and `entrypoint.sh` still start with `uv run`: apply §7's start rules instead (no `uv run`; Famiglia's two files already follow them).
- [ ] Add `GET /health` (liveness only, `include_in_schema=False`) and point the `api` healthcheck at it in both `docker-compose.yml` and `deployment/docker-compose.yml` (§6).
- [ ] Copy `Registro_Spese/frontend/{Dockerfile,nginx.conf,vite.config.ts}` → keep verbatim.
- [ ] Copy `Registro_Spese/e2e/` → keep verbatim (specs will be replaced per app).
- [ ] Copy `Registro_Spese/.github/workflows/ci-cd.yml` → no edits needed (uses `${GITHUB_REPOSITORY}`).
- [ ] Copy the canonical files from `shared/` (table in `shared/README.md`) keeping their headers; adjust only import lines. Write `settings.py`, `api/errors.ts`, and `main.py` wiring per §3a / §4b. Frontend deps: `@tanstack/react-query`, `openapi-fetch` (exact version as in `shared/frontend/package.json`), dev dep `openapi-typescript`.
- [ ] Add the ruff + pyright config (§3c) and the `lint` / `typecheck` / `types` / `drift` Makefile targets (§8).
- [ ] Run `make drift`: every canonical copy must be `current`.
- [ ] Write `domain/model.py` first; let it drive `adapters/orm.py`.
- [ ] Write `CLAUDE.md` (template in §11) before the second commit.
- [ ] Generate the first ADR (`001-ports-and-adapters.md`) by re-using Registro_Spese's.
- [ ] **In `Infrastructure/`**: add the role+db (`create_app …`) to `init/01-init.sh` and a `<APP>_DB_PASSWORD` to `.env`; set `DB_USER=<app>_app` in the app's `deployment/.env.example`; and add a systemd unit under `deployment/systemd/` (see §7b).

---

## 14. Known drift

Where existing apps deviate from this blueprint, recorded so nobody copies the deviation into a new app. (For canonical-file copies specifically, `make -C shared drift` reports the exact state; see §15.)

**v2 migration state (2026-11-16):** every app is still on v1 code patterns; `make -C shared drift` lists all canonical files as "not adopted" everywhere. Migration order: **Famiglia** (pilot) → **Chatbot** → the rest, one app at a time and incrementally (no big-bang rewrite). Known v1 defects that v2 fixes, recorded so they're not lost:
- Famiglia `services.update_member` saves blank names and invalid colours (reproduced 2026-11-16; D1).
- Famiglia routes repeat `except ValueError → 400` and leak raw English messages; the frontend detects "member in use" via `msg.includes('409')` (D2, F3).
- 9 `unit_of_work.py` files, no two identical (D5); Diario imports `bcrypt`/`jwt` in the service layer (D7; Chatbot fixed in its 004).
- 5 of 9 apps never configure logging (D6); no backend has ruff or pyright (D3).
- All CI workflows still build `linux/amd64,linux/arm64` through QEMU; switch to amd64 only (§12). 7 apps still carry the dead `.env.deploy.example` (Pi-era values); delete it.
- Blibiobot maps its entities **declaratively** (`models.py` + `*Model` classes and copy functions); rich form maps imperatively like §3a. Chatbot is the rich-form example for this point (`adapters/persistence/postgres/orm.py`).
- 7 apps carry the MkDocs/Kroki docs stack (`mkdocs.yml`, `docs/api-reference/`, `kroki` service, `make docs`); remove per §10. Per-app `CLAUDE.md` files copy blueprint content (e.g. the §9 table); trim per §11.

---

## 15. Shared canonical code — `shared/` (v2, D5)

`Apps/shared/` holds code every app needs that must behave the same everywhere. It's tracked in the `Apps/` root repo (whitelisted in the root `.gitignore`). Apps **copy** these files; nothing installs or imports `shared/` at runtime, so each app repo still builds on its own.

- **Header.** Each canonical file starts with `# canonical: <path in shared/> vN` (or `//` in TypeScript), and app copies keep it.
- **Imports.** Only import lines may differ, to fit the simple or rich layout. Everything else is verbatim.
- **Local changes** must be labelled: `# canonical: backend/domain/errors.py v1 + local: <reason>`.
- **Changing a canonical file**: edit it in `shared/`, bump `vN`, run `make -C shared test`, then propagate to apps one at a time with each app's tests as the gate. The drift check lists which apps are `outdated`.
- **Upgrading an app's copy: diff before overwriting.** The drift check can't see unlabelled edits in an *outdated* copy, so compare the copy with the version it claims before replacing it, and turn any real edit into a `+ local:` label or a change to `shared/`.
- **Drift check**: `make -C shared drift [APP=<App>]`. Statuses: `current`, `local`, `outdated`, **`modified`** (unlabelled edit → exit 1), **`ahead`** (unknown version or source → exit 1). It also lists what each app hasn't adopted.
- **Never shared**: domain models, ports, prompts, use cases. Those are the app's own.
- **Contents and copy destinations**: see `shared/README.md`.
