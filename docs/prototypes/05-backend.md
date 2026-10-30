# Step 5 sign-off: one backend for the scheduler

All package code reaches quantify-scheduler and qblox-instruments through `tergite_tuner/backend/`, and the measurements build their schedules from shared blocks in `lib/utils/schedules.py`. The compiled programs did not change. The baselines shrank:

| Baseline | Before | After |
| --- | --- | --- |
| ruff | 488 | 472 |
| pylint | 70 | 54 |
| vulture | 26 | 24 |
| style guide | 747 | 626 |

## 1. Behaviour is unchanged

```bash
uv run pytest tergite_tuner -n auto -q
uv run python -m dev.lint.baseline ruff && uv run python -m dev.lint.baseline pylint && uv run python -m dev.lint.baseline vulture
```

`458 passed, 5 skipped, 3 xfailed`, and the baselines pass. The compiled-program digests in `tests/fixtures/goldens/schedules.json` did not move: `git diff b45dae36 -- tergite_tuner/tests/fixtures/goldens` is empty.

## 2. Only backend/ imports the scheduler

```bash
grep -rlE "^\s*(from|import) (quantify_scheduler|qblox_instruments)" tergite_tuner --include=*.py | grep -v "/backend/\|/tests/"
```

Prints nothing. The style guide enforces it from now on.

## 3. Performance is no worse

```bash
dev/perf/record.sh /tmp/perf-step5
uv run python -m dev.perf.compare dev/perf/baselines/macos-arm64 /tmp/perf-step5
```

No measure more than 15% worse.

## 4. The changes users can see

- The device types and helpers moved from `tergite_tuner.utils.types.extended_*` and `tergite_tuner.lib.utils.device` to `tergite_tuner.backend`.
- `tergite_tuner.tuner.HardwareManager` became `tergite_tuner.backend.Hardware`, and a node's `lab_instr_coordinator` and `spi_manager` became `node.hardware`. tergite-backend uses none of them.
- The dummy cluster has the modules in the cluster config's `hardware_description`, not a fixed 15 QCM-RF and 2 QRM-RF.
- A schedule's run waits for its estimated duration plus `cluster_timeout`, not an hour, and has no progress bar.

## 5. Check on real hardware

The wait is the one change the dummy cluster cannot exercise. On a real cluster, run punchout, whose schedule is the longest at about 264 s, and a CZ calibration with its real `loop_repetitions`: neither should raise a timeout.
