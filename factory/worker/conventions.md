# Conventions for every task (read-only reference)

These rules apply to every change you make, in addition to your task's brief.

## Code
- Match the style of the file you're editing: naming, quotes, semicolons, line length,
  docstrings and comments. Don't add docstrings or comments where the file has none, and
  don't remove the ones that are there.
- No unused imports, variables or parameters. Put new imports with the existing ones,
  in the same order style.
- Change only what the brief asks for. Don't reformat, rename or "improve" other code.
- "Copy X verbatim" means byte for byte: same docstrings, comments, blank lines and calls
  (e.g. keep `super().__init__()`). Never paraphrase a file you were told to copy.

## Tests
- Keep every existing test and test case. Never delete, skip or weaken a test, and never
  loosen an assertion, to make new behaviour fit.
- Test names say the behaviour: `test_missing_file_is_an_error`, `it('returns … when …')`.
- One idea per test. Separate **setup**, **action** and **check** with a blank line:

      def test_unknown_member_is_not_found():
          repo = FakeRepository()

          result = find(repo, "nobody")

          assert result is None

- Python: use small hand-written fake classes, not mocks; tests never hit the network;
  `pytest.mark.parametrize` for variations of the same value; pytest's built-in fixtures
  (`tmp_path`, `capsys`, `monkeypatch`).
- A rule with exceptions gets tests for both sides: rejected, and allowed when the
  exception applies.
- A test must be able to fail: never compare a function's result with the same function
  called again.
