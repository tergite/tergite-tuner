# Step 0 sign-off: the bug fixes

Branch `feature/refactor`, on the quantify-scheduler line (`0746b7ec` + Python 3.13).

## 1. Tests

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e . --group test --group dev
.venv/bin/pytest tergite_tuner -q
```

Expect `375 passed, 5 skipped`. Before step 0 it was `320 passed, 6 skipped`.

## 2. Dummy datasets

```bash
.venv/bin/pytest tergite_tuner/lib/base/tests/test_node.py -q
```

Every node in the default map builds a dummy dataset that `configure_dataset` accepts (34 nodes). Before step 0, nine of them raised `AttributeError: ... has no attribute 'generate_dummy_dataset'`.

A standalone `run_node` in dummy mode still needs the device values that earlier nodes write (f01 and others) and qubits that the configs define. So a dummy tune-up of the whole graph is step 2.1's test, not this sign-off.

## 3. On the testbed

On the testbed, with `CLUSTER_MODE='real'`, check these. Each one exercises a fix that a dummy run cannot:

| Fix | Run | Expected |
| --- | --- | --- |
| 0.1 | Point `CLUSTER_IP` at an address with no cluster, run any node | `ClusterUnreachableError`, and the Python session survives (before: the process exited) |
| 0.2 | Run with `SAVE_PLOT=True` over SSH with no display | Plots are saved; no Tk error |
| 0.14 | Rabi oscillations, and three-state readout amplitude optimization, on two qubits whose `rxy.duration` / `r12.ef_duration` differ | Each qubit's pulse in the saved device JSON and the compiled program has its own duration |
| 0.15 | Qubit spectroscopy vs amplitude with `spec.spec_duration = 8e-6` in `node_config.toml` | Compiles and runs (before: `UnboundLocalError`) |
| 0.16, 0.19 | Resonator spectroscopy 1, then punchout | `Ql_1` in Redis is a quality factor (about 10⁴), not a frequency; punchout's plot has amplitude on x |
| 0.22 | CZ parametrization on two couplers with disjoint qubits | Each coupler's qubits are excited only in their own shots |
| 0.23 | Two-qubit RB on one coupler | Same fidelity as on `main`; on two couplers it raises `ValueError` |
| 0.3 | Punchout | Compiles; afterwards `quantify_scheduler.backends.qblox.constants.GRID_TIME_TOLERANCE_TIME` is back to `0.0011` |

The values for the testbed decisions in `REFACTOR.md` step 0 (peak detection, Rabi uncertainty, the 1–2 durations, the CZ phase) are best recorded from this same session, to decide them.
