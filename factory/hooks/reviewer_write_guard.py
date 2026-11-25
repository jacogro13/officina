"""Write guard for the factory's reviewer subagent (factory step 3b).

Runs as a PreToolUse hook on the reviewer's file-writing tools (Write, Edit, MultiEdit,
NotebookEdit). Claude Code passes the tool call as JSON on stdin; this script allows it
(exit 0, no output) or refuses it (exit 2, reason on stderr — what the reviewer sees).

The reviewer may write only:
    <App>/docs/work/NNN-slug/review.md
    <App>/docs/work/NNN-slug/plan.md       (to append "Fixes from review")
    <App>/docs/work/NNN-slug/spec.md       (its Status: line)
    factory/BACKLOG.md
all inside the Apps/ folder this script lives in. *Which part* of plan.md and spec.md
it changes is left to its instructions; this guard only checks *which files*.

It fails closed: anything it can't read or understand is refused. (Exit code 1 would
NOT block the write, so every error path must end in exit 2.)
"""

import json
import re
import sys
from pathlib import Path

APPS_ROOT = Path(__file__).resolve().parents[2]

_WORK_FILE = re.compile(r"^[A-Za-z0-9_-]+/docs/work/\d{3}-[a-z0-9-]+/(review|plan|spec)\.md$")
_BACKLOG = "factory/BACKLOG.md"

REFUSAL = (
    "Refused by the reviewer write guard: the reviewer may only write review.md, plan.md "
    "or spec.md in a work record (<App>/docs/work/NNN-slug/) and factory/BACKLOG.md. "
    "Report anything else as a finding in review.md instead of changing it."
)


def refusal_reason(payload: object, apps_root: Path = APPS_ROOT) -> str | None:
    """None if the write is allowed, otherwise the reason it's refused."""
    if not isinstance(payload, dict):
        return "Refused by the reviewer write guard: unreadable hook input."
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return "Refused by the reviewer write guard: no tool input."
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw:
        return "Refused by the reviewer write guard: no file path to check."

    path = Path(raw)
    if not path.is_absolute():
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            return "Refused by the reviewer write guard: relative path without a cwd."
        path = Path(cwd) / path

    resolved = path.resolve()  # also collapses "..", and follows symlinks
    try:
        relative = resolved.relative_to(apps_root.resolve()).as_posix()
    except ValueError:
        return REFUSAL
    if relative == _BACKLOG or _WORK_FILE.match(relative):
        return None
    return REFUSAL


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        reason = refusal_reason(payload)
    except Exception as exc:  # noqa: BLE001 — fail closed on anything unexpected
        reason = f"Refused by the reviewer write guard: could not check the write ({exc!r})."
    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
