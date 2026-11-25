# Bake-off: which tool drives the local coding model (factory step 4c)

2026-11-20. Decides the tool for the factory's local-LLM worker (step 4). All runs were on
throwaway worktrees, deleted afterwards; nothing shipped.

## Setup

- **Model:** Qwen3.6-35B-A3B, `unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ3_XXS` (13.2 GB), served by
  `Infrastructure/llm/llama-qwen.service` on the mini-PC's port 8080 (manual swap with Gemma), 16k
  context, **thinking off** (`chat_template_kwargs.enable_thinking=false`), temperature 0.2.
- **Speed measured:** ~31 tokens/s generating; ~360 tokens/s reading a realistic 5k-token
  prompt. A typical small task (5k in, 100 out) takes under 20 s per model call. Thinking on
  was 6× slower for similar quality on a small task.
- **Memory:** with Qwen loaded (and `llama-ocr` stopped) 11 GB used, 15 GB available —
  better than with Gemma (21 / 5).
- **Tasks** (written like `/plan` tasks: files, intended change, check — nothing else):
  - **T1** — `shared/frontend/src/api/client.ts`: non-JSON 502/503/504 → `network_error`,
    with tests (TypeScript logic + tests; check: type check + vitest + header bumped).
  - **T2** — Registro_Spese: "today" used the UTC date; new `localDateISO()` in
    `utils/dates.ts`, used in two components, with tests (check: no old pattern, eslint on
    the touched files, `tsc -b`, vitest).
  - **T3** — Diario CI: `ubuntu-24.04`, no QEMU/arm64, `type=sha` tags, with Chatbot's
    workflow as a read-only reference (check: YAML parses + rules).
- **Candidates:** aider 0.86.2 (via `uvx --from aider-chat`, `--edit-format diff`,
  `--map-tokens 0`, `--auto-test` with the check); a ~150-line custom loop (send task +
  files, apply SEARCH/REPLACE blocks to the allowed files only, run the check, feed failures
  back at most twice). Claude Code pointed at Qwen was the reserve; not needed.

## Results

| Task | aider | custom loop |
|---|---|---|
| T1 | ✅ 1st attempt, 39 s, 4.2k/0.6k tokens · **good** | ✅ 2nd attempt, 49 s *(loop fixed once first)* · **changes needed**: deleted the existing `404 → unknown` test case; narrowed "not JSON" to `Content-Type: text/html`; duplicated `throw` |
| T2 | ✅ edits correct 1st time, 148 s (one extra round caused by an unfair check, see below) · **good**; weak "defaults to today" test | ✅ 1st attempt, 60 s *(loop fixed again first)* · **good**; the same weak test |
| T3 | ✅ 1st attempt, 79 s, 5.8k/1.1k tokens · **good**; removed `provenance: false` (not asked, but matches the reference) | ❌ failed after 3 attempts, 217 s: its parser misread the model's replies |

## Decision: aider

3/3 with correct edits on the first attempt, ~40–80 s per task, best quality on the
hardest task. The custom loop's failures were almost all in **its own reply parsing**
(empty SEARCH applied to an existing file, a placeholder copied as SEARCH text, a
closing marker read as a file name) — the fiddly part aider already solves. Writing our
own would mean rebuilding aider.

aider's settings for the worker: `factory/worker/aider-model-settings.yml` and
`factory/worker/aider-model-metadata.json`.

## Lessons for step 4d

1. **The reviewer stays essential.** Qwen wrote good code but, in T1 via the loop, deleted
   an existing test case to make the new behaviour fit — exactly a "weakened check" — and
   both tools wrote a near-tautological test in T2. Checks passing is not enough.
2. **Every worker check must be shown to fail on the unchanged code before it is
   trusted.** Two of the three checks were wrong at first: a `… | tail` hid the test
   runner's exit code (failing tests would have passed), and T2's lint step covered the
   whole frontend, which already fails lint on files the task doesn't touch.
3. **Give the worker only the files the task names**, plus read-only references; aider's
   `--map-tokens 0` keeps the prompt within the 16k context.
4. **Thinking off** by default; worth re-testing thinking on for harder tasks.

## Side findings (to the backlog)

- Registro_Spese's frontend already fails `eslint .`: `useState` called conditionally in
  `MonthlyCharts.tsx` (a real React bug) and a non-component export in `App.tsx`.
- Famiglia's CI still sets `provenance: false` with a QEMU comment, though it no longer
  builds with QEMU.

## After the pilots (2026-11-20)

- **Pasti 001** (before tuning): 1 of 3 local tasks unaided; the other two needed small
  fixes for conventions the worker never saw (test layout, unused import) and a file it
  paraphrased instead of copying. → `worker/conventions.md` goes with every task; plain
  copies are never `local`; raw worker diffs are kept for the reviewer.
- **Learn_German 001** (after tuning): 2 of 3 unaided, raw diffs identical to the
  commits, no slips found in review. The third failed on tooling: aider auto-added a file
  the brief only *mentioned* (`uv.lock`, ~150k tokens) and blew the context. → the worker
  now runs aider with `--no-git` (mention detection needs git; an `.aiderignore` alone
  did not stop it) and makes the check start in the repo root, since without git aider
  works from the files' folder. Reproduced and verified with a 485 KB lock file.
