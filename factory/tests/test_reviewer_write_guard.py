import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

import reviewer_write_guard as guard


def write_call(file_path: str, cwd: str = "/somewhere") -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": file_path}, "cwd": cwd}


@pytest.mark.parametrize(
    "relative",
    [
        "Famiglia/docs/work/008-week-colours/review.md",
        "Famiglia/docs/work/008-week-colours/plan.md",
        "Chatbot/docs/work/001-backend-v2/spec.md",
        "factory/BACKLOG.md",
    ],
)
def test_work_record_files_and_backlog_are_allowed(tmp_path, relative):
    payload = write_call(str(tmp_path / relative))

    reason = guard.refusal_reason(payload, apps_root=tmp_path)

    assert reason is None


@pytest.mark.parametrize(
    "relative",
    [
        "Famiglia/backend/services/services.py",  # code
        "Famiglia/backend/tests/unit/test_services.py",  # tests
        "Famiglia/docs/work/008-week-colours/notes.md",  # other file in the record
        "Famiglia/docs/adr/011-something.md",  # docs outside the record
        "Famiglia/docs/work/review.md",  # not inside a NNN-slug folder
        "Famiglia/docs/work/8-short/review.md",  # number not three digits
        "shared/backend/domain/errors.py",  # canonical code
        "factory/README.md",  # the factory itself
        ".claude/agents/reviewer.md",  # its own definition
        "BLUEPRINT.md",
    ],
)
def test_everything_else_inside_apps_is_refused(tmp_path, relative):
    payload = write_call(str(tmp_path / relative))

    reason = guard.refusal_reason(payload, apps_root=tmp_path)

    assert reason == guard.REFUSAL


def test_paths_outside_apps_are_refused(tmp_path):
    payload = write_call("/etc/hosts")

    reason = guard.refusal_reason(payload, apps_root=tmp_path)

    assert reason == guard.REFUSAL


def test_dot_dot_cannot_escape_from_an_allowed_folder(tmp_path):
    sneaky = tmp_path / "Famiglia/docs/work/008-x/../../../backend/services.py"

    reason = guard.refusal_reason(write_call(str(sneaky)), apps_root=tmp_path)

    assert reason == guard.REFUSAL


def test_symlink_to_code_inside_a_work_record_is_refused(tmp_path):
    code = tmp_path / "Famiglia/backend/services.py"
    code.parent.mkdir(parents=True)
    code.write_text("x = 1\n")
    record = tmp_path / "Famiglia/docs/work/008-x"
    record.mkdir(parents=True)
    (record / "review.md").symlink_to(code)

    reason = guard.refusal_reason(write_call(str(record / "review.md")), apps_root=tmp_path)

    assert reason == guard.REFUSAL


def test_relative_paths_are_resolved_against_cwd(tmp_path):
    allowed = write_call("docs/work/008-x/review.md", cwd=str(tmp_path / "Famiglia"))
    refused = write_call("backend/services.py", cwd=str(tmp_path / "Famiglia"))

    assert guard.refusal_reason(allowed, apps_root=tmp_path) is None
    assert guard.refusal_reason(refused, apps_root=tmp_path) == guard.REFUSAL


def test_notebook_path_is_checked_too(tmp_path):
    payload = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(tmp_path / "Famiglia/analysis.ipynb")},
        "cwd": str(tmp_path),
    }

    reason = guard.refusal_reason(payload, apps_root=tmp_path)

    assert reason == guard.REFUSAL


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"tool_input": "not a dict"},
        {"tool_input": {}},
        {"tool_input": {"file_path": ""}},
        {"tool_input": {"file_path": "relative/review.md"}},  # relative, no cwd
    ],
)
def test_input_it_cannot_understand_is_refused(tmp_path, payload):
    reason = guard.refusal_reason(payload, apps_root=tmp_path)

    assert reason is not None


def test_main_allows_with_exit_0_and_no_output(monkeypatch, capsys):
    allowed = str(guard.APPS_ROOT / "factory/BACKLOG.md")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(write_call(allowed))))

    code = guard.main()

    assert code == 0
    assert capsys.readouterr().err == ""


def test_main_refuses_with_exit_2_and_reason_on_stderr(monkeypatch, capsys):
    code_file = str(guard.APPS_ROOT / "Famiglia/backend/services/services.py")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(write_call(code_file))))

    code = guard.main()

    assert code == 2
    assert "reviewer write guard" in capsys.readouterr().err


def test_main_fails_closed_on_invalid_json(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))

    code = guard.main()

    assert code == 2
    assert "could not check the write" in capsys.readouterr().err
