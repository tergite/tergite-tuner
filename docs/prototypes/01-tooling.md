# Step 1 sign-off: tooling, lint and the style guide

## 1. Install from the lock

```bash
uv sync --locked --all-groups
```

It installs the 168 locked packages with no resolution. After a dependency change in `pyproject.toml` without `uv lock`, it fails instead.

## 2. Every check CI runs

```bash
uv run black --check tergite_tuner dev conftest.py
uv run python -m dev.lint.baseline ruff
uv run python -m dev.lint.baseline pylint
uv run python -m dev.lint.baseline vulture
uv run pytest tergite_tuner -q
```

All pass; pytest reports `388 passed, 5 skipped`.

## 3. The checks catch what they should

- Add `x = 1  ` (trailing spaces) to `tergite_tuner/exc.py`. `dev.lint.baseline ruff` fails with `W291 Trailing whitespace`. Revert it.
- Delete any one line of `dev/lint/ruff_baseline.txt`. The check fails and lists that line as a new finding. Restore it.
- Add `def job_status(active: bool) -> None: ...` to `tergite_tuner/exc.py`. `pytest tergite_tuner/tests/test_styleguide.py` fails `test_functions_are_named_with_a_verb` and `test_booleans_start_with_is_or_should`. Revert it.
- Push a branch and open a merge request: GitLab runs the job above and passes.

## 4. Read

- [DESIGN.md](../../DESIGN.md) describes the code as it is.
- [CONTRIBUTING.md](../../CONTRIBUTING.md) sets up with `uv sync`.
