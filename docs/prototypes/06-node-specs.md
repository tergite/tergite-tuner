# Step 6 sign-off: a node is data

Every node is a `NodeSpec` in `DEFAULT_NODE_SPECS`, run by `lib/run.py`, and the node classes, measurement types and analysis base classes are gone. The package went from 26,280 to 22,954 lines of Python, tests included (18,408 to 16,571 without them). The baselines shrank:

| Baseline | Before | After |
| --- | --- | --- |
| ruff | 472 | 356 |
| pylint | 54 | 38 |
| vulture | 24 | 24 |
| style guide | 626 | 342 |

## 1. Behaviour is unchanged

```bash
uv run pytest tergite_tuner -n auto -q
uv run python -m dev.lint.baseline ruff && uv run python -m dev.lint.baseline pylint && uv run python -m dev.lint.baseline vulture
git diff f83e7c26 -- tergite_tuner/tests/fixtures/goldens
```

`422 passed, 2 skipped, 3 xfailed`; the baselines pass; the golden diff is empty. The dummy tune-up runs every node, with AllXY, purity benchmarking and qubit 01 spectroscopy still the expected failures that REFACTOR.md lists.

## 2. Performance is no worse

```bash
dev/perf/record.sh /tmp/perf-step6
uv run python -m dev.perf.compare dev/perf/baselines/macos-arm64 /tmp/perf-step6
```

No measure more than 15% worse.

## 3. The changes users can see

- `node_cls_map` is gone, with `BaseNode`, `QubitNode`, `CouplerNode` and the node classes. A custom node is a spec in `node_specs`, as the README shows, usually `dataclasses.replace` of a default one.
- A node with no calibration status in Redis raises `MissingCalibrationStatusError`, a `ValueError`.
- Dummy mode no longer pauses between T1 and T2 repetitions, and every node has a dummy model of its own.
- A failed analysis is still plotted.

## 4. Check on real hardware

Run a tune-up through CZ calibration, with `save_plot`: every node's plots should look as before, and each coupler node's figures appear under the same names.
