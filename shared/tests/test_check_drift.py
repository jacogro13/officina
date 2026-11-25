from pathlib import Path

import pytest

from check_drift import comparable_lines, main

SOURCE = """\
# canonical: backend/domain/errors.py v2
\"\"\"Errors.\"\"\"

from typing import Any


class DomainError(Exception):
    code = "domain_error"
"""


@pytest.fixture
def apps_root(tmp_path: Path) -> Path:
    """Apps/ with shared/ holding one canonical file at v2, and one app."""
    source = tmp_path / "shared" / "backend" / "domain" / "errors.py"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE)
    (tmp_path / "Famiglia" / "backend" / "domain").mkdir(parents=True)
    return tmp_path


def write_copy(apps_root: Path, text: str, rel: str = "backend/domain/errors.py") -> None:
    target = apps_root / "Famiglia" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def run(apps_root: Path, capsys) -> tuple[int, str]:
    code = main(["--shared", str(apps_root / "shared")])
    return code, capsys.readouterr().out


def test_identical_copy_is_current(apps_root, capsys):
    write_copy(apps_root, SOURCE)

    code, out = run(apps_root, capsys)

    assert code == 0
    assert "current" in out


def test_layout_specific_imports_and_blank_lines_are_ignored(apps_root, capsys):
    rich_form = SOURCE.replace(
        "from typing import Any\n",
        "from __future__ import annotations\nfrom typing import (\n    Any,\n)\n\n\n",
    )
    write_copy(apps_root, rich_form, "backend/src/famiglia/domain/errors.py")

    code, out = run(apps_root, capsys)

    assert code == 0
    assert "current" in out


def test_unlabelled_change_fails(apps_root, capsys):
    write_copy(apps_root, SOURCE.replace('"domain_error"', '"oops"'))

    code, out = run(apps_root, capsys)

    assert code == 1
    assert "FAIL modified" in out


def test_labelled_local_change_is_allowed_and_reported(apps_root, capsys):
    labelled = SOURCE.replace("v2", "v2 + local: Famiglia needs a photo error").replace(
        '"domain_error"', '"oops"'
    )
    write_copy(apps_root, labelled)

    code, out = run(apps_root, capsys)

    assert code == 0
    assert "local" in out
    assert "Famiglia needs a photo error" in out


def test_older_version_is_reported_as_outdated_without_failing(apps_root, capsys):
    write_copy(apps_root, SOURCE.replace("v2", "v1").replace('"domain_error"', '"old"'))

    code, out = run(apps_root, capsys)

    assert code == 0
    assert "outdated" in out
    assert "v1 → v2" in out


@pytest.mark.parametrize(
    "header",
    ["# canonical: backend/domain/errors.py v3", "# canonical: backend/domain/nope.py v1"],
)
def test_newer_version_or_unknown_source_fails(apps_root, capsys, header):
    write_copy(apps_root, SOURCE.replace("# canonical: backend/domain/errors.py v2", header))

    code, out = run(apps_root, capsys)

    assert code == 1
    assert "FAIL ahead" in out


def test_files_without_a_header_are_ignored_and_source_listed_as_not_adopted(apps_root, capsys):
    write_copy(apps_root, "class DomainError(Exception): ...\n")

    code, out = run(apps_root, capsys)

    assert code == 0
    assert "not adopted: backend/domain/errors.py" in out


def test_copies_inside_dependency_folders_are_ignored(apps_root, capsys):
    write_copy(apps_root, SOURCE.replace('"domain_error"', '"oops"'), "frontend/node_modules/x.py")

    code, out = run(apps_root, capsys)

    assert code == 0
    assert "node_modules" not in out


def test_typescript_multiline_imports_are_ignored():
    text = (
        "// canonical: frontend/src/api/client.ts v1\n"
        "import {\n  a,\n  b,\n} from './x'\n"
        "export const c = 1\n"
    )

    assert comparable_lines(text) == ["export const c = 1"]
