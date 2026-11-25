"""Local-LLM worker for the factory (step 4d): run aider + Qwen on ONE plan task.

    python3 factory/worker/run.py --repo <app folder> --task-file <task.md> \\
        --check "<command>" --file <path> [--file <path> …] [--ref <path> …]

What it does, in order:
1. **Model loaded?** Asks the LLM server which model is loaded; only `qwen-code` will do.
2. **Clean tree?** The repo must have no uncommitted changes (so anything that changes
   afterwards was made by the worker).
3. **Runs aider** (pinned version, via uvx — nothing installed) with the settings chosen in
   the bake-off (`factory/bakeoff-2026-11.md`): only the named files are editable, refs are
   read-only, the check runs after each edit and failures are fed back.
4. **Scope check:** if any file outside `--file` changed, ALL changes are reverted and the
   result is `scope_violation`.
5. **Runs the check once more** itself and reports.

Prints one JSON object (status, seconds, tokens, changed files, check output) and exits:
0 passed · 1 check_failed · 2 scope_violation · 3 worker_unavailable · 4 refused
(dirty tree or bad arguments). It never commits: /build reads the diff and commits.

Network: only the factory's LLM endpoint (user's exception) — `/v1/models` here, and
`/v1/chat/completions` through aider.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

# The llama.cpp server running the coding model (set FACTORY_LLM_BASE, see .env.example).
LLM_BASE = os.environ.get("FACTORY_LLM_BASE", "http://localhost:8080").rstrip("/")
MODEL_ID = "qwen-code"
AIDER_VERSION = "0.86.2"  # the version tested in the bake-off
HERE = Path(__file__).resolve().parent
LOG_DIR = HERE / "logs"
CONVENTIONS = HERE / "conventions.md"

EXIT = {"passed": 0, "check_failed": 1, "scope_violation": 2, "worker_unavailable": 3, "refused": 4}


@dataclass
class Result:
    status: str
    detail: str = ""
    seconds: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    changed_files: list[str] = field(default_factory=list)
    check_output: str = ""
    aider_version: str = AIDER_VERSION


# ── Model server ──────────────────────────────────────────────────────────────


def loaded_model_ids(payload: dict) -> set[str]:
    """Model ids from llama-server's /v1/models (it answers in two formats at once)."""
    ids = {m.get("id") for m in payload.get("data", []) if isinstance(m, dict)}
    ids |= {m.get("name") for m in payload.get("models", []) if isinstance(m, dict)}
    return {i for i in ids if i}


def fetch_models(base: str = LLM_BASE) -> dict:
    with urllib.request.urlopen(f"{base}/v1/models", timeout=10) as r:
        return json.load(r)


# ── Git ───────────────────────────────────────────────────────────────────────


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


_ARTIFACT = re.compile(
    r"(^|/)(__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache|node_modules|dist|build|coverage)/"
    r"|\.(pyc|tsbuildinfo)$"
)


def is_artifact(path: str) -> bool:
    """Files that running tools produce (caches, builds) — never counted as edits."""
    return bool(_ARTIFACT.search(path))


def changed_paths(repo: Path) -> list[str]:
    """Modified, deleted and new files (relative paths), from git status, minus artifacts."""
    out = git(repo, "status", "--porcelain", "--untracked-files=all")
    paths = (line[3:].strip().strip('"') for line in out.splitlines() if line.strip())
    return sorted(p for p in paths if not is_artifact(p))


def revert_all(repo: Path) -> None:
    """Undo every change since the clean start: restore tracked files, delete new ones."""
    git(repo, "checkout", "--", ".")
    git(repo, "clean", "-fd")


# ── aider ─────────────────────────────────────────────────────────────────────


def aiderignore_text(files: list[str]) -> str:
    """An .aiderignore that hides every repo file except the task's own.

    aider offers to add any file the brief mentions by name, and --yes-always accepts:
    in the Learn_German pilot that pulled in a 1900-line uv.lock (~150k tokens) and blew
    the 16k context. Tested: this list alone did NOT stop it (mention detection ignores
    .aiderignore); running aider with --no-git did. The list stays as a second guard.
    """

    return "\n".join(["*", "!*/", *(f"!/{f}" for f in files)]) + "\n"


def aider_command(
    task_file: Path,
    check: str,
    files: list[str],
    refs: list[str],
    history_dir: Path,
    repo: Path,
) -> list[str]:
    ignore = history_dir / "aiderignore"
    ignore.write_text(aiderignore_text(files))
    cmd = [
        "uvx",
        "--from",
        f"aider-chat=={AIDER_VERSION}",
        "aider",
        "--model",
        f"openai/{MODEL_ID}",
        "--openai-api-base",
        f"{LLM_BASE}/v1",
        "--openai-api-key",
        "none",
        "--model-settings-file",
        str(HERE / "aider-model-settings.yml"),
        "--model-metadata-file",
        str(HERE / "aider-model-metadata.json"),
        "--map-tokens",
        "0",
        "--no-auto-commits",
        "--yes-always",
        "--no-check-update",
        "--analytics-disable",
        "--no-gitignore",
        "--no-show-model-warnings",
        "--no-pretty",
        "--no-stream",
        # keep aider's own history files out of the repo
        "--aiderignore",
        str(ignore),
        "--no-git",  # aider auto-adds files the brief mentions, found via git; without git it can't
        "--chat-history-file",
        str(history_dir / "chat.md"),
        "--input-history-file",
        str(history_dir / "input.txt"),
        # Without git, aider works from the files' folder, not the repo root: make the
        # check start in the repo root wherever aider runs it from.
        "--test-cmd",
        f"cd {shlex.quote(str(repo))} && {check}",
        "--auto-test",
        "--message-file",
        str(task_file),
    ]
    for ref in [str(CONVENTIONS), *refs]:  # the conventions go with every task
        cmd += ["--read", ref]
    return cmd + files


_TOKENS = re.compile(r"Tokens: ([\d.]+)(k?) sent, ([\d.]+)(k?) received")


def parse_tokens(log: str) -> tuple[int, int]:
    """Sum aider's 'Tokens: 4.2k sent, 583 received.' lines."""
    sent = received = 0
    for m in _TOKENS.finditer(log):
        sent += round(float(m[1]) * (1000 if m[2] else 1))
        received += round(float(m[3]) * (1000 if m[4] else 1))
    return sent, received


def run_aider(cmd: list[str], repo: Path) -> str:
    proc = subprocess.run(cmd, check=False, cwd=repo, capture_output=True, text=True, timeout=1800)
    return proc.stdout + proc.stderr


def run_check(check: str, repo: Path) -> tuple[bool, str]:
    proc = subprocess.run(check, check=False, shell=True, cwd=repo, capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr)[-3000:]


# ── The worker ────────────────────────────────────────────────────────────────


def work(
    repo: Path,
    task_file: Path,
    check: str,
    files: list[str],
    refs: list[str],
    *,
    models: Callable[[], dict] = fetch_models,
    aider: Callable[[list[str], Path], str] = run_aider,
    checker: Callable[[str, Path], tuple[bool, str]] = run_check,
    log_dir: Path = LOG_DIR,
) -> Result:
    start = time.time()

    try:
        ids = loaded_model_ids(models())
    except Exception as exc:  # noqa: BLE001 — any failure means: no worker
        return Result("worker_unavailable", f"LLM server not reachable: {exc!r}")
    if MODEL_ID not in ids:
        return Result("worker_unavailable", f"loaded model is {sorted(ids)}, not {MODEL_ID}")

    if changed_paths(repo):
        return Result("refused", "the repo has uncommitted changes; the worker needs a clean tree")

    # A check that already passes on the unchanged code can't prove the task was done.
    ok_before, out_before = checker(check, repo)
    if ok_before:
        return Result(
            "refused", "the check already passes on the unchanged code", check_output=out_before
        )
    noise = set(changed_paths(repo))  # anything the check itself left behind
    if noise:
        revert_all(repo)

    log_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=log_dir) as history:
        log = aider(aider_command(task_file, check, files, refs, Path(history), repo), repo)
    (log_dir / f"{repo.name}-{int(start)}.log").write_text(log)
    tokens_in, tokens_out = parse_tokens(log)

    changed = [p for p in changed_paths(repo) if p not in noise]
    outside = [p for p in changed if p not in files]
    if outside:
        revert_all(repo)
        return Result(
            "scope_violation",
            f"changed files outside the task, all changes reverted: {outside}",
            round(time.time() - start, 1),
            tokens_in,
            tokens_out,
            changed,
        )

    ok, output = checker(check, repo)
    return Result(
        "passed" if ok else "check_failed",
        "" if ok else "the check still fails after aider's attempts",
        round(time.time() - start, 1),
        tokens_in,
        tokens_out,
        changed,
        output,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--check", required=True)
    parser.add_argument("--file", dest="files", action="append", required=True)
    parser.add_argument("--ref", dest="refs", action="append", default=[])
    args = parser.parse_args(argv)

    repo, task_file = args.repo.resolve(), args.task_file.resolve()
    if not (repo / ".git").exists() or not task_file.is_file():
        result = Result("refused", "--repo must be a git repo and --task-file an existing file")
    else:
        result = work(repo, task_file, args.check, args.files, args.refs)
    print(json.dumps(asdict(result), indent=2))
    return EXIT[result.status]


if __name__ == "__main__":
    sys.exit(main())
