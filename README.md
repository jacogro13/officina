# officina: a gated workflow for changing apps with Claude Code

## What it is

A fixed process I use to change my private web apps (FastAPI, React, PostgreSQL) with
[Claude Code](https://claude.com/claude-code). Every change goes through a spec, a plan,
the implementation and an independent review, and leaves documents that are committed
with the code in the app's repo. I approve at three points; nothing reaches `main`, which
deploys straight to production in my setup, without me. Small, fully specified tasks can
be done by a local language model; Claude checks its result.

This repo holds the factory (`factory/`, `.claude/`), the architecture rules it checks
against (`BLUEPRINT.md`, `BLUEPRINT_V2_DECISIONS.md`) and the code shared by all apps
(`shared/`). The example app is [Brio](https://github.com/jacogro13/brio) (separate repo; called
`Chatbot` in the code and the work records).

## Status

Work in progress. In use since November 2026: 20 changes across five of my apps, 18 of
them shipped. What's next:

- **Coding models:** so far one model in one configuration (Qwen3.6-35B-A3B, smallest
  quantisation, 16k context, thinking off). Still to test: a larger quantisation with a
  32k context, thinking on for harder tasks, and newer local coding models as they come
  out, each on the same kind of small tasks so the results stay comparable.
- **Process:** adjusted after each pilot (see the end of
  [`factory/bakeoff-2026-11.md`](factory/bakeoff-2026-11.md)). Open: handing the generic
  bug hunt to Claude Code's `/code-review`, and a project contract so other projects can
  use the commands without editing them.

## Local models

Both the factory and Brio use models I host myself, on one machine: a GMKtec NucBox
EVO-X1 (AMD Ryzen AI 9 HX 370 with Radeon 890M iGPU, 32 GB LPDDR5-7500: 4 GiB reserved
for the iGPU, the rest system RAM, of which the iGPU can borrow up to 24 GiB).
llama.cpp's `llama-server` (build 9780, Vulkan, all layers on the integrated GPU) runs as
systemd services on the host, not in Docker, and offers an OpenAI-compatible API.

| Port | Model | Used by |
|---|---|---|
| 8080 | Gemma 4 26B-A4B (GGUF `UD-Q4_K_XL`), 32k context, text only | Brio's chat, my other apps |
| 8080, swapped in | Qwen3.6-35B-A3B (GGUF `UD-IQ3_XXS`, 13.2 GB), 16k context | the factory's local worker |
| 8081–8083 | Gemma 4 E4B (vision), Qwen3-Embedding-0.6B, GLM-OCR | my other apps (image import, RAG, OCR) |

The two large models don't fit in memory together, so systemd swaps them with one
command (`Conflicts=`); while Qwen is loaded, the apps get Qwen's answers. App
containers reach the host's server through their Docker network's gateway. Measured
with Qwen: about 31 tokens/s generating, about 360 tokens/s reading the prompt.
The systemd units, the reasons for each flag and what went wrong along the way are in
[`llm/`](llm/README.md).

## How it works

```
idea / BACKLOG.md → /spec → spec.md ─(approve)→ /plan → plan.md ─(approve)→
  /build (task by task, checks after each) → /review → review.md ─(approve)→ /release
```

- **`/spec`** asks about the *what* and *why* (at most three questions at a time) and
  writes `spec.md` with checkable acceptance checks.
- **`/plan`** cuts an approved spec into small tasks, each with its files and one check,
  and decides whether Claude or the local model does each one.
- **`/build`** works on its own branch, one commit per task, and stops when something is
  unclear or a check fails twice.
- **`/review`** starts a **reviewer subagent** in a fresh context that receives only
  `<App> <number>`. It runs lint, type checks, unit and integration tests (e2e when the
  app needs no external services), reads the whole diff, checks every acceptance check
  and writes a verdict.
- **`/release`** checks the preconditions, lists what has to happen on the server before
  and after the push, and pushes only on my explicit word.

Approvals are lines (`Approved by: … · Date: …`) that only I fill in.
Details: [`factory/README.md`](factory/README.md).

## Technical details

- **Built on Claude Code's extension points:** five skills (`.claude/skills/`), a subagent
  with restricted tools (`.claude/agents/reviewer.md`) and a `PreToolUse` hook.
- **Write guard for the reviewer** (`factory/hooks/reviewer_write_guard.py`): allows only
  `review.md`, `plan.md`, `spec.md` in the work record and the backlog; any error means
  refusal (fail closed).
- **Local worker** (`factory/worker/run.py`): checks that the model is loaded, the working
  tree is clean and the task's check fails *before* the change, runs
  [aider](https://aider.chat) 0.86.2 on the named files only, reverts everything if other
  files changed, and reports time and tokens as JSON.
- **Worker model settings** (from the bake-off): thinking off, temperature 0.2, aider's
  `diff` edit format, no repo map, so a task fits in the 16k context.
- **Shared code with a drift check:** apps copy files from `shared/`;
  `shared/tools/check_drift.py` reports copies that are outdated or changed without a label.

## Quality assurance

- Tests for the hook and the worker: `make -C factory test` (Ruff, 66 test cases, no
  network). `shared/`: `make -C shared test` (Ruff, Pyright, pytest, Vitest).
- The worker only gets tasks whose check fails beforehand, with at most three files and
  no migrations, auth, deployment or canonical files.
- Claude reads every worker diff; the raw diff is kept, and the reviewer compares it with
  the commit.

## Examples

Brio contains eight complete runs under `docs/work/001…008/`, e.g.
`004-auth-ports` (ports and adapters for authentication) and `008-hosting-adr-pi-cleanup`
(one task done by the local model: 1 run, 20 s, 3.4k/0.15k tokens, diff committed
unchanged). Why aider was chosen is documented in
[`factory/bakeoff-2026-11.md`](factory/bakeoff-2026-11.md).

## Setup

1. Requirements: Claude Code, git, make, Python ≥ 3.12, [uv](https://docs.astral.sh/uv/);
   for the app also Docker and Node 20; for `/release` the GitHub CLI.
2. Clone this repo, then clone the app into it under its code name:
   `git clone https://github.com/jacogro13/brio Chatbot` (the work records and commands
   call it `Chatbot`; it stays a separate repo and is excluded here via `.gitignore`).
3. Start Claude Code **in the repo root**; that's where it finds the commands.
   The instructions call this folder `Apps/`.
4. Optional, local worker: start `llama-server` with a coding model under the alias
   `qwen-code` (e.g. `-c 16384 -fa on -ctk q8_0 -ctv q8_0 --jinja --alias qwen-code`) and
   set `FACTORY_LLM_BASE` (see `factory/.env.example`). Without a worker, Claude does all
   tasks.

## What a project needs

The process itself is generic; what it checks against is not. Three layers:

- **Contract** (needed for the commands to run): each app is a folder in the repo root
  with its own git repo; make targets `lint`, `typecheck`, `unit`, `integration` and `e2e`;
  a `CLAUDE.md` per app, including a line `E2E self-contained: yes|no` (whether `make e2e`
  may run without outside services); ADRs in `docs/adr/`. Work records go to
  `docs/work/`; the commands create them.
- **Rules** (what the reviewer enforces): the hard rules in [`CLAUDE.md`](CLAUDE.md) and
  "Rules at a glance" in [`BLUEPRINT.md`](BLUEPRINT.md), plus the drift check for
  `shared/`. These are my rules for a FastAPI/React/PostgreSQL stack (hexagonal layers,
  imperative ORM mapping, Unit of Work, Italian UI text…); replace them with your own.
  BLUEPRINT also names apps and an infrastructure repo that stay private.
- **Deployment** (`/release` only): written for my setup, where a push to `main` builds
  images in CI and the server updates itself. Other setups need their own pre- and
  post-push steps in `.claude/skills/release/SKILL.md`.

The test style the commands ask for (fakes instead of mocks, behaviour-named tests) is
written down in [`factory/worker/conventions.md`](factory/worker/conventions.md); `/plan`
and `/build` also refer to the user's global `~/.claude/CLAUDE.md`, where I keep the same
rules. Without that file, put them in the project's `CLAUDE.md`.

## Limits and lessons learned

- **Tied to my conventions:** used with other projects, the rules and `/release` need
  adapting (see *What a project needs*); so far it has only run on my own apps.
- **Only partly enforced:** the write guard covers the editing tools, not the shell.
  Approval lines and stop rules live in the instructions; the skills themselves have no
  automated tests.
- **Little data on the local model:** three pilot changes, 4 of 7 tasks done without
  rework. 16k-token context; the model server runs on the local network without
  authentication.
- **Overlap with Claude Code:** the reviewer's generic bug hunt resembles the built-in
  `/code-review`, and spec and plan resemble plan mode. Whether the bug hunt can be
  delegated there is still open.
- **Lessons:** the model wrote good code, but in one comparison run it deleted an existing
  test so the new behaviour would fit: passing checks are not enough, the review stays
  necessary. Two of three checks in the bake-off were wrong at first (one hid the test
  runner's exit code, one failed regardless of the task); so every check must be shown
  to fail first. A custom replacement for aider failed mostly at parsing the model's
  replies.

## License

[MIT](LICENSE)
