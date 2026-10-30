# Step 10 sign-off: tests in the right place

Each node's tests sit in its `tests/` folder, the tuner's own in `tergite_tuner/tests/`, and the shared helpers in `tergite_tuner/tests/utils/`. The earlier steps had done most of this. This step deleted T1's empty test folder, since T2's decay test already fits T1's dummy decay, and folded `tests-readme.md` into DESIGN.md's testing section. No package code changed.

## 1. The suite and CI pass

```bash
uv run black --check tergite_tuner dev conftest.py
uv run python -m dev.lint.baseline ruff && uv run python -m dev.lint.baseline pylint && uv run python -m dev.lint.baseline vulture
uv run pytest tergite_tuner -n 4 -q
```

Black leaves every file unchanged, the baselines pass, and the suite gives `425 passed, 2 skipped`.

## 2. Performance is no worse

```bash
dev/perf/record.sh /tmp/perf-step10
uv run python -m dev.perf.compare dev/perf/baselines/macos-arm64 /tmp/perf-step10
```

Every measure but one is within the baseline. The dummy tune-up peaked at 701 MB (705 MB at step 9). The exception is the import, at 5.85 s against the baseline's 5.08 s.

No package code changed since step 9, which measured 5.2 s. Timed alternately on the same machine, step 9's code and this step's both import in 5.9 to 6.3 s, so the difference is the machine's state, not the code. Rerun the recording on an idle machine to see it compare clean.

## 3. The changes users can see

None.

## 4. Check on real hardware

None needed: no compiled program or analysis changed.
