"""Drift check for canonical files (Blueprint v2, D5).

Canonical sources live in Apps/shared/ and start with a header line:

    # canonical: backend/domain/errors.py v1          (Python)
    // canonical: frontend/src/api/client.ts v1       (TypeScript)

Apps copy a file and keep the header. This script finds every copy in every app
and compares it with its source:

    current    same version, same content                          ok
    local      header says "+ local: <reason>"                     ok, reported
    outdated   older version than shared/                          ok, reported (upgrade job)
    modified   same version, different content, no local label     FAIL
    ahead      newer version than shared/ (or unknown source)      FAIL

Content comparison ignores the header, import lines (they differ between simple
and rich layouts) and blank lines.

    uv run python tools/check_drift.py              # all apps next to shared/
    uv run python tools/check_drift.py Famiglia     # one app
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HEADER = re.compile(
    r"^\s*(?:#|//)\s*canonical:\s*(?P<source>\S+)\s+v(?P<version>\d+)"
    r"(?:\s*\+\s*local:\s*(?P<reason>.+?))?\s*$"
)
SUFFIXES = {".py", ".ts", ".tsx"}
SKIP_DIRS = {"node_modules", ".venv", "dist", "site", "__pycache__", ".git", "build"}
FAILING = {"modified", "ahead"}


@dataclass(frozen=True)
class Header:
    source: str
    version: int
    reason: str | None


@dataclass(frozen=True)
class Finding:
    app: str
    path: Path
    source: str
    status: str
    detail: str = ""


def read_header(path: Path) -> Header | None:
    """The canonical header, if one of the first three lines carries it."""
    try:
        with path.open(encoding="utf-8") as handle:
            for _ in range(3):
                match = HEADER.match(handle.readline())
                if match:
                    return Header(match["source"], int(match["version"]), match["reason"])
    except (OSError, UnicodeDecodeError):
        return None
    return None


def comparable_lines(text: str) -> list[str]:
    """Lines that must match: no header, no imports, no blank lines, no trailing spaces."""
    lines: list[str] = []
    skipping_import = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if skipping_import:
            if ")" in stripped or re.search(r"\bfrom\s+['\"]", stripped):
                skipping_import = False
            continue
        if not stripped or HEADER.match(line):
            continue
        if re.match(r"(from\s+\S+\s+)?import\b", line):
            python_open_paren = line.endswith("(")
            ts_unfinished = line.startswith("import") and not re.search(
                r"\bfrom\s+['\"]|^import\s+['\"]", line
            )
            if python_open_paren or (ts_unfinished and line.endswith("{")):
                skipping_import = True
            continue
        lines.append(line)
    return lines


def canonical_sources(shared: Path) -> dict[str, tuple[int, Path]]:
    sources: dict[str, tuple[int, Path]] = {}
    for path in iter_code_files(shared):
        header = read_header(path)
        if header and path.relative_to(shared).as_posix() == header.source:
            sources[header.source] = (header.version, path)
    return sources


def iter_code_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.suffix in SUFFIXES and path.is_file() and not SKIP_DIRS & set(path.parts):
            yield path


def check_app(app_dir: Path, sources: dict[str, tuple[int, Path]]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_code_files(app_dir):
        header = read_header(path)
        if header is None:
            continue
        rel = path.relative_to(app_dir)
        if header.source not in sources:
            findings.append(Finding(app_dir.name, rel, header.source, "ahead", "unknown source"))
            continue
        version, source_path = sources[header.source]
        if header.reason:
            status, detail = "local", header.reason
        elif header.version < version:
            status, detail = "outdated", f"v{header.version} → v{version}"
        elif header.version > version:
            status, detail = "ahead", f"v{header.version} > shared v{version}"
        elif comparable_lines(path.read_text(encoding="utf-8")) != comparable_lines(
            source_path.read_text(encoding="utf-8")
        ):
            status, detail = "modified", "differs from shared without a local label"
        else:
            status, detail = "current", ""
        findings.append(Finding(app_dir.name, rel, header.source, status, detail))
    return findings


def find_apps(apps_root: Path, shared: Path) -> list[Path]:
    return [
        d
        for d in sorted(apps_root.iterdir())
        if d.is_dir() and d != shared and ((d / "backend").is_dir() or (d / "frontend").is_dir())
    ]


def report(findings: list[Finding], sources: dict[str, tuple[int, Path]], apps: list[Path]) -> str:
    out: list[str] = []
    for app in apps:
        mine = [f for f in findings if f.app == app.name]
        adopted = {f.source for f in mine}
        missing = sorted(set(sources) - adopted)
        out.append(f"{app.name}:")
        for f in mine:
            mark = "FAIL" if f.status in FAILING else "ok  "
            detail = f"  ({f.detail})" if f.detail else ""
            out.append(f"  {mark} {f.status:<9} {f.path}  ← {f.source}{detail}")
        if missing:
            out.append(f"  not adopted: {', '.join(missing)}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("apps", nargs="*", help="app folder names (default: all)")
    parser.add_argument(
        "--shared", type=Path, default=Path(__file__).resolve().parent.parent, help="shared/ folder"
    )
    args = parser.parse_args(argv)

    shared: Path = args.shared.resolve()
    sources = canonical_sources(shared)
    apps = find_apps(shared.parent, shared)
    if args.apps:
        apps = [a for a in apps if a.name in args.apps]
        unknown = set(args.apps) - {a.name for a in apps}
        if unknown:
            print(f"Unknown app(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2

    findings = [f for app in apps for f in check_app(app, sources)]
    print(report(findings, sources, apps))
    return 1 if any(f.status in FAILING for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
