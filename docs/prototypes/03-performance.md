# Step 3 sign-off: performance baselines

## 1. Record and compare

On an Apple-silicon Mac, with as little else running as you can manage:

```bash
dev/perf/record.sh /tmp/perf-step3
uv run python -m dev.perf.compare dev/perf/baselines/macos-arm64 /tmp/perf-step3
```

The recording takes about 20 minutes. The comparison prints nothing and exits 0. The baseline's fast-suite time (181 s) predates the `slow` marker on `test_precompile.py`, so today's recording is far below it; only a measure that got worse is reported.

## 2. The comparison catches a regression

Copy `/tmp/perf-step3` to `/tmp/perf-worse`, and multiply one `seconds` in its `nodes.json` by 1.5. The comparison against `/tmp/perf-worse` lists that measure under "Worse than the baseline" and exits 1.

## 3. Where a run's time goes

```bash
uv run pytest tergite_tuner/tests/test_public_api.py -q -k logs
```

Passes. In a real run's log, each node shows `Compiled <node> in … s`, `Measured <node> in … s` and `Analysed <node> in … s`.

## 4. The suite is faster

```bash
uv run pytest tergite_tuner -n auto -m "not slow" -q
uv run pytest tergite_tuner -n auto -q
```

About 35 s and 1 m 30 s on a 12-core Mac (`412 passed, 4 skipped`; `474 passed, 5 skipped, 4 xfailed`). Before step 3, about 3 min and 8 min.

## 5. In CI

On `main`, run the GitLab job `performance`; its `perf-recording/` artifact is the CI baseline to commit as `dev/perf/baselines/ci/`.
