# Step 9 sign-off: long functions and the rest

No function has 60 lines or more: each long analysis, plotter and schedule is a composition of named steps, with unit tests for the pure ones. The CZ analyses share their sine-phase fit, the readout amplitude analyses their shot classification, and the entry points set up logging. Purity benchmarking and AllXY run, and the bugs below were fixed. Python went from 20,535 to 20,285 lines, tests included (14,804 to 14,091 without them). The baselines shrank:

| Baseline | Before | After |
| --- | --- | --- |
| ruff | 252 | 242 |
| pylint | 30 | 15 |
| vulture | 21 | 18 |
| style guide | 269 | 246 |

## 1. The compiled programs are unchanged

```bash
uv run pytest tergite_tuner -n 4 -q
uv run python -m dev.lint.baseline ruff && uv run python -m dev.lint.baseline pylint && uv run python -m dev.lint.baseline vulture
git diff 2a2d590b -- tergite_tuner/tests/fixtures/goldens
```

`425 passed, 2 skipped`; the baselines pass. The golden diff is one program: resonator spectroscopy at |2> now prepares it with the calibrated ef motzoi. Where a split could not be checked against a golden, old and new were compared outside the suite: readout amplitude's two-state analysis gives the same fits, shots and limits on the stored dataset, and either crossing finder's grouping was run against both coupler spectroscopy nodes' tests.

## 2. Performance is no worse

```bash
dev/perf/record.sh /tmp/perf-step9
uv run python -m dev.perf.compare dev/perf/baselines/macos-arm64 /tmp/perf-step9
```

No measure is worse than the baseline. Import time is 5.2 s, against 5.6 s at step 8, and the dummy tune-up peaked at 705 MB, against 719 MB at step 8 and 841 MB in the baseline.

## 3. The changes users can see

The fixes are in the changelog's `[Unreleased]` section:
- Purity benchmarking runs, and AllXY has an analysis, storing `all_xy_error`.
- Qubit spectroscopy vs current stores its results under its own name.
- Resonator spectroscopy prepares |2> with the ef motzoi.
- The T2 and CZ RB fits fail on data they cannot fit, instead of raising.
- CZ chevron's durations round correctly, and an uncalibrated CZ phase correction shifts no phase.
- The tuner no longer sets up logging on import. Each run logs to the console and to `tergite_tuner.log` in its folder.

A few analysis methods changed name: readout amplitude's `run_initial_fitting` and `three_state_classification` are now one `classify_amplitudes`, and the coupler spectroscopy analyses' `_find_crossing_currents` is the module's `find_crossing_currents`.

## 4. Check on real hardware

Run resonator spectroscopy at |2>, qubit 01 spectroscopy with the example node config, purity benchmarking and AllXY: each should complete and store its values. Then run coupler anticrossing and resonator spectroscopy vs current, and check that their crossings match a run from before the step.
