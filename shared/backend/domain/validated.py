# canonical: backend/domain/validated.py v1
"""Validated domain dataclasses (Blueprint v2, D1).

Mix `Validated` into a stdlib `@dataclass` and type its fields with Pydantic
constraint types. Every field is then validated on construction AND on every
later assignment; a bad value raises `InvalidInput` naming the field.

    @dataclass
    class FamilyMember(Validated):
        name: NonBlankStr
        color: HexColor

Works with SQLAlchemy *imperative* mapping (Pydantic `BaseModel` and Pydantic
dataclasses do not — see BLUEPRINT_V2_DECISIONS.md, D1).

Limits, by design:
- Only assignment is checked. In-place mutation (`m.tags.append(x)`) is not.
- Rows loaded by SQLAlchemy skip validation (they bypass `__setattr__`); the
  database is trusted to hold values that were valid when written.
- Rules spanning several fields belong in entity methods that change those
  fields together and then check the rule once.
- Attributes starting with "_" (e.g. SQLAlchemy's `_sa_instance_state`) and
  `ClassVar`s are never validated.
"""

from typing import Annotated, Any, ClassVar, get_origin, get_type_hints

from pydantic import StringConstraints, TypeAdapter, ValidationError

from domain.errors import InvalidInput

# ── Reusable constrained types ────────────────────────────────────────────────

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
"""Text that must contain something; surrounding whitespace is stripped."""

HexColor = Annotated[str, StringConstraints(pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$")]
"""CSS hex colour: `#rgb` or `#rrggbb`."""


# ── The mixin ─────────────────────────────────────────────────────────────────

_ADAPTERS: dict[type, dict[str, TypeAdapter[Any]]] = {}


def _adapters_for(cls: type) -> dict[str, TypeAdapter[Any]]:
    adapters = _ADAPTERS.get(cls)
    if adapters is None:
        hints = get_type_hints(cls, include_extras=True)
        adapters = {
            name: TypeAdapter(hint)
            for name, hint in hints.items()
            if not name.startswith("_") and get_origin(hint) is not ClassVar
        }
        _ADAPTERS[cls] = adapters
    return adapters


class Validated:
    """Validates annotated fields on every assignment (including `__init__`)."""

    def __setattr__(self, name: str, value: Any) -> None:
        adapter = _adapters_for(type(self)).get(name)
        if adapter is not None:
            try:
                value = adapter.validate_python(value)
            except ValidationError as exc:
                reason = exc.errors()[0]["msg"]
                raise InvalidInput(f"{type(self).__name__}.{name}: {reason}", field=name) from exc
        super().__setattr__(name, value)
