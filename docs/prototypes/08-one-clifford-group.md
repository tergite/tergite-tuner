# Step 8 sign-off: one Clifford implementation

Single-qubit RB, purity benchmarking and two-qubit RB all draw and decompose their Cliffords with the PycQED-derived group in `lib/utils/cliffords/`. The hash-table implementation and the single-qubit table in `utils/cliffords.py` are gone. Python went from 22,291 to 21,295 lines, tests included (15,806 to 14,804 without them), and the 128 KB of hash tables went with it. The baselines shrank:

| Baseline | Before | After |
| --- | --- | --- |
| ruff | 275 | 252 |
| pylint | 38 | 30 |
| vulture | 21 | 21 |
| style guide | 315 | 269 |

## 1. The compiled programs are unchanged

```bash
uv run pytest tergite_tuner -n auto -q
uv run python -m dev.lint.baseline ruff && uv run python -m dev.lint.baseline pylint && uv run python -m dev.lint.baseline vulture
git diff 673c85ab -- tergite_tuner/tests/fixtures/goldens
```

`349 passed, 2 skipped, 3 xfailed`; the baselines pass; the golden diff is empty. Before each swap, the old and new implementations were compared outside the suite: the two two-qubit groups decompose all 11,520 elements alike, and the old single-qubit table is the group's Epstein decomposition, so for 200 seeds the old and new RB sequences, interleaved or not and recovery included, are the same.

## 2. Performance is no worse

```bash
dev/perf/record.sh /tmp/perf-step8
uv run python -m dev.perf.compare dev/perf/baselines/macos-arm64 /tmp/perf-step8
```

No measure is worse than the baseline, and import time did not move (5.6 s). The dummy tune-up peaked at 719 MB, against 610 MB at step 7 and 841 MB in the baseline: the two-qubit group's table is now built in memory rather than read from hash files.

## 3. The changes users can see

None beyond the modules: `tergite_tuner.utils.cliffords` and `tqg_randomized_benchmarking.utils` are gone, and the group lives in `tergite_tuner.lib.utils.cliffords`.

## 4. Check on real hardware

Run single-qubit RB, interleaved with X90, and CZ RB: their fidelities should match a run from before the step.
