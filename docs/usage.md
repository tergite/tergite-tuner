# Using the tuner

The entry points, all importable from `tergite_tuner`:

| Function | Does |
| --- | --- |
| `tune_device` | calibrates every node up to the target node that is not already in spec |
| `run_node` | runs one node |
| `reanalyse` | reruns a node's analysis on data already recorded |
| `read_result` | reads what a session's nodes found, as `CalibrationResults` |
| `generate_calib_seed_file` | writes those results as the calibration seed tergite-backend reads |

All but `read_result`, which takes a session, take `env_file=` and any `SessionContext` field
as a keyword argument; see [configuration.md](configuration.md). `tune_device`, `run_node` and
`reanalyse` return the session and its results.

## Tune up the device

```python
from tergite_tuner import NodeEnum, tune_device

# configured by the .env file alone
_, results = tune_device(env_file=".env")

# or with fields overridden in code
session, results = tune_device(
    env_file=".env",
    target_node=NodeEnum.RABI_OSCILLATIONS,
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
)
```

`tune_device` walks the node graph up to `target_node` and calibrates each node that is not
yet in spec. To tune up from scratch rather than recalibrate, pass `is_recalibration=False`
and `ignore_spec=False`.

## Keep a session across calls

A session keeps its device state across the calls you pass it to. Pass
`refresh_session=False` to reuse it as is, then read everything it found at once:

```python
from tergite_tuner import read_result

tune_device(session=session, refresh_session=False)
results = read_result(session)
```

You can also build a session yourself with `SessionContext.from_env()`.

**Nothing carries over between sessions** unless you pass it in: a session starts from
`device_config.toml`. To start from an earlier run, give its results as `calibration`, as
`tune_device` returns them or as the `results.json` each run writes in its folder.

`keep_data_files=False` deletes the run's data folder when it is done.

## Run one node

```python
from tergite_tuner import NodeEnum, run_node

session, results = run_node(env_file=".env", node=NodeEnum.QUBIT_01_SPECTROSCOPY)

# on chosen qubits
_, results = run_node(
    env_file=".env",
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
    node=NodeEnum.QUBIT_01_SPECTROSCOPY,
)

# in an existing session
run_node(node=NodeEnum.QUBIT_01_SPECTROSCOPY, session=session, refresh_session=False)
```

## Reanalyse recorded data

```python
from pathlib import Path

from tergite_tuner import reanalyse

_, results = reanalyse(
    env_file=".env",
    data_dir=Path("out/<run>/<node folder>"),  # the folder holding dataset_<node>.hdf5
)
```

## Write a calibration seed for tergite-backend

```python
from tergite_tuner import generate_calib_seed_file, tune_device

# from a session's results, to calibration.seed.toml by default
session, _ = tune_device(env_file=".env")
generate_calib_seed_file(session=session)

# or from earlier results, with the qubits and couplers of the .env file
generate_calib_seed_file(env_file=".env", calibration=results, path="/path/to/seed.toml")
```

## Customise the nodes

A node is a `NodeSpec`: its schedule, sweeps, analysis, and the device-state fields it sets.

- **Replace or add a node** by passing your own specs as `node_specs`.
- **Skip nodes** with `ignored_nodes`.
- **Change the order** with `node_dag_edges`, a tuple of `(parent, child)` pairs.

```python
import dataclasses

from tergite_tuner import NodeEnum, tune_device
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS


def analyse_my_way(s21, session):
    ...


_, results = tune_device(
    node_specs={
        NodeEnum.QUBIT_01_SPECTROSCOPY: dataclasses.replace(
            DEFAULT_NODE_SPECS[NodeEnum.QUBIT_01_SPECTROSCOPY], analyse=analyse_my_way
        ),
    },
    node_dag_edges=(
        (NodeEnum.PUNCHOUT, NodeEnum.TOF),
        (NodeEnum.QUBIT_01_SPECTROSCOPY, NodeEnum.COUPLER_ANTICROSSING),
    ),
    ignored_nodes=(NodeEnum.PUNCHOUT,),
)
```

More complete scripts are in [examples/](../examples).
