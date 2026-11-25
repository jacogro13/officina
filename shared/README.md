# shared/ — canonical cross-app code

Code that every app needs and that must behave the same everywhere (Blueprint v2,
decision D5). **Nothing here is installed or imported by apps.** Each app keeps its
own copy of each file, and `tools/check_drift.py` tracks those copies.

## What's here

| Canonical file | Copy into the app as | Decision |
|---|---|---|
| `backend/domain/errors.py` | `domain/errors.py` | D2 — `DomainError` + `NotFound` / `Conflict` / `InvalidInput` / `Unauthorized` / `Forbidden` / `PayloadTooLarge` |
| `backend/domain/validated.py` | `domain/validated.py` | D1 — `Validated` mixin, `NonBlankStr`, `HexColor` |
| `backend/entrypoints/error_handlers.py` | `entrypoints/error_handlers.py` | D2 — one handler, one `{code, message, field}` body |
| `backend/entrypoints/logging_setup.py` | `entrypoints/logging_setup.py` | D6 — readable lines + request ids |
| `backend/settings_base.py` | `settings_base.py` (rich form: next to `dependencies.py`) | D4 — `AppSettings` (pydantic-settings) |
| `backend/adapters/security/bcrypt/bcrypt_password_hasher.py` | `adapters/security/bcrypt/bcrypt_password_hasher.py` | D7 — `BcryptPasswordHasher`: worker thread, 72-byte cut, malformed hash = failed login |
| `backend/adapters/security/fake/fake_password_hasher.py` | `adapters/security/fake/fake_password_hasher.py` | D7 — `FakePasswordHasher`, instant, tests only (never wired) |
| `backend/adapters/security/jwt/pyjwt_token_service.py` | `adapters/security/jwt/pyjwt_token_service.py` | D7 — `PyJwtTokenService`: `sub` + claims + `exp`; `TokenExpired` vs `InvalidToken` |
| `frontend/src/api/client.ts` | `frontend/src/api/client.ts` | F1 — typed `openapi-fetch` client, `ApiError` |
| `frontend/src/api/messages.ts` | `frontend/src/api/messages.ts` | F3 — `makeMessageFor`, code → Italian |

Paths are for the simple form. In the rich form the same files go under
`backend/src/<app>/…`; only the import lines change, and the drift check ignores
import lines for exactly that reason.

Not canonical (test scaffolding only): `frontend/src/api/schema.d.ts`, `tests/`,
`*.test.ts`, and the reference auth ports `backend/domain/ports/password_hasher.py`,
`backend/domain/ports/token_service.py` and `backend/domain/auth_errors.py`. The auth
adapters subclass them only so they can be tested here. **Ports are never shared**
(D5, §15): each app writes its own `PasswordHasher` / `TokenService` and token errors
in the same shape, and points the adapters' import lines at them. Chatbot is the
reference (`domain/user/ports/`, errors in `domain/user/model.py`).

Planned, added when the first app that needs them is migrated: UoW base, LLM
transport (per `../docs/plans/LLM_ADAPTER_SHARING.md`).

## Rules

1. **Copy verbatim, keep the header.** The first line names the source and version:
   `# canonical: backend/domain/errors.py v1`. Fix import lines to the app's layout;
   change nothing else.
2. **Need a local change?** Label it in the header, so the drift check reports it
   as intended instead of failing:
   `# canonical: backend/domain/errors.py v1 + local: Famiglia adds a photo-size rule`
3. **Changing a canonical file** = edit it here, bump its version (`v1` → `v2`), run
   `make test`, then propagate to apps as a factory job (one app at a time,
   each app's own tests as the gate).
4. **Upgrading an app's copy: diff before overwriting.** The drift check can't see
   unlabelled edits in an *outdated* copy (it only knows the current version), so
   an upgrade could silently erase them. Compare the app's copy with the version it
   claims (`git log` of `shared/`) before replacing it; turn any real edit into a
   `+ local:` label or a change to `shared/`.

## Commands

```bash
make install        # uv sync + npm ci
make test           # ruff + pyright + pytest + tsc + vitest — the gate for any change here
make drift          # report for all apps (exit 1 on unlabelled edits or unknown versions)
make drift APP=Famiglia
```

Drift statuses: `current` · `local` (labelled) · `outdated` (older version: upgrade
job) · **`modified`** (unlabelled edit: FAIL) · **`ahead`** (newer than shared or
unknown source: FAIL) · plus a `not adopted` list per app.
