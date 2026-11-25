# String annotations on purpose: proves Validated resolves them (get_type_hints).
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import ClassVar

import pytest
from sqlalchemy import Column, MetaData, String, Table, Uuid, create_engine
from sqlalchemy.orm import registry, sessionmaker

from domain.errors import InvalidInput
from domain.validated import HexColor, NonBlankStr, Validated


@dataclass
class Member(Validated):
    name: NonBlankStr
    color: HexColor
    member_id: uuid.UUID = field(default_factory=uuid.uuid4)
    kind: ClassVar[str] = "member"


def test_valid_values_are_accepted_and_cleaned():
    member = Member(name="  Anna ", color="#b0503a")

    assert member.name == "Anna"
    assert member.color == "#b0503a"


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("name", {"name": "   ", "color": "#fff"}),
        ("name", {"name": "", "color": "#fff"}),
        ("color", {"name": "Anna", "color": "red"}),
        ("color", {"name": "Anna", "color": "#12345"}),
    ],
)
def test_invalid_value_at_creation_is_rejected_naming_the_field(field_name, kwargs):
    with pytest.raises(InvalidInput) as caught:
        Member(**kwargs)

    assert caught.value.field == field_name


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [("name", "   "), ("color", "red")],
)
def test_invalid_value_on_assignment_is_rejected(field_name, bad_value):
    # The Famiglia bug: updates used to skip the checks done at creation.
    member = Member(name="Anna", color="#fff")

    with pytest.raises(InvalidInput) as caught:
        setattr(member, field_name, bad_value)

    assert caught.value.field == field_name


def test_rejected_assignment_keeps_the_previous_value():
    member = Member(name="Anna", color="#fff")

    with pytest.raises(InvalidInput):
        member.name = ""

    assert member.name == "Anna"


def test_private_attributes_are_not_validated():
    member = Member(name="Anna", color="#fff")

    marker = object()

    member._cache = marker  # pyright: ignore[reportAttributeAccessIssue]

    assert member._cache is marker  # pyright: ignore[reportAttributeAccessIssue]


@pytest.fixture
def mapped_session():
    """Member mapped imperatively, like every app's adapters/orm.py."""
    metadata = MetaData()
    mapper_registry = registry()
    table = Table(
        "members",
        metadata,
        Column("member_id", Uuid, primary_key=True),
        Column("name", String),
        Column("color", String),
    )
    mapper_registry.map_imperatively(Member, table)
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    mapper_registry.dispose()


def test_works_with_sqlalchemy_imperative_mapping(mapped_session):
    with mapped_session() as session:
        member = Member(name="Anna", color="#fff")
        session.add(member)
        session.commit()
        member_id = member.member_id

    with mapped_session() as session:
        loaded = session.get(Member, member_id)
        assert loaded is not None
        loaded.name = "  Bea "
        session.commit()

    with mapped_session() as session:
        reloaded = session.get(Member, member_id)
        assert reloaded is not None
        assert reloaded.name == "Bea"


def test_loaded_entities_still_validate_assignments(mapped_session):
    with mapped_session() as session:
        member = Member(name="Anna", color="#fff")
        session.add(member)
        session.commit()
        member_id = member.member_id

    with mapped_session() as session:
        loaded = session.get(Member, member_id)
        assert loaded is not None
        with pytest.raises(InvalidInput):
            loaded.name = "   "
