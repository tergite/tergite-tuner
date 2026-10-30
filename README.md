# Tergite Tuner

![CI](https://github.com/tergite/tergite-tuner/actions/workflows/ci.yml/badge.svg)

A Python library that tunes up the WACQT quantum computers.

This is a stripped down fork of the [tergite-autocalibration](https://github.com/tergite/tergite-autocalibration)
project that was developed jointly by Chalmers Next Labs (CNL) and the Quantum Technology department
of Chalmers University of Technology. 

**It is meant to be used as a library that one can install in their project** while tergite-autocalibration
is meant to be used more interactively with CLI, GUI to browse datasets, and charts for more manual
oversight of the tuneup.

It contains a calibration runner, a collection of calibration
schedules, and a collection of post-processing and analysis routines.
It is developed and tested on the WACQT quantum computers at 
Chalmers Next Labs quantum testbed and Chalmers University of Technology.

**This project is developed by a core group of collaborators.**
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

Note: The Tergite stack is developed on a separate version control system and mirrored on GitHub.
If you are reading this on GitHub, then you are looking at a mirror.

**This project owes its very existence to the tireless work of the authors and contributors of 
[tergite-autocalibration](https://github.com/tergite/tergite-autocalibration).**

## Quick Start

### Requirements

- Python ≥ 3.13 (a fresh `conda` or `venv` environment is fine).

### Installation

```shell
pip install tergite-tuner
```

Copy the [example environment file](./.example.env) and edit it as needed.  

The `.env` file controls the cluster IP, target node,
qubits/couplers under calibration, and so on.   

Every field on `SessionContext` can be set in the `.env` or as an environment variable
(in upper case), or passed as a keyword argument to the public API of the entry point functions.
A keyword argument wins over an environment variable, which wins over the `.env` file.

`IS_RECALIBRATION` and `IGNORE_SPEC` default to `True`: a run recalibrates the nodes,
whatever their calibration status, without resetting the cluster or setting the couplers'
currents. Set both to `False` to tune up the device from the device config.


On top of having a `.env` file, more configuration files maybe required. 
(See [`.example.env` file](./.example.env) for more details)

- [`cluster_config.json`](./cluster_config.example.json): 
  It is the [`quantify-scheduler`](https://quantify-os.org/docs/quantify-scheduler/v0.27.1/tutorials/Compiling%20to%20Hardware.html#hardware-compilation-configuration) configuration json file
- [`device_config.toml`](./device_config.example.toml): 
  It contains details about the quantum chip, including initial values of params of the chip.
- [`node_config.toml`](./node_config.example.toml): 
  It contains details about the calibration nodes to run, including initial values for each node
- __Optional:__ [`spi_config.toml`](./spi_config.example.toml): 
  It contains details about the SPI instrument for driving the couplers. 

The contents of each of these files can as well be passed to the entry functions
as python objects e.g.

```python
from tergite_tuner import tune_device
from tergite_tuner.config.types import (
    DeviceConfig, 
    ClusterConfig, 
    SpiConfig, 
    NodeConfig,
)

_, results = tune_device(
    device_config=DeviceConfig(
        name = "matthias",
        resonator={
            "all": {"attenuation": 10},
            "q01": { "VNA_frequency": 6433000000.0 },
            "q02":{ "VNA_frequency": 6290000000.0 },
        },
        # ...
    ), 
    node_config=NodeConfig.model_validate(
        {
            "qubit_spectroscopy_vs_current": {
                "all": {
                    "spec.spec_duration": 6e-6,
                    "reset.duration": 200e-6,
                },
            }
        }
    ), 
    spi_config=SpiConfig.model_validate({
        "q11_q12": {
            "spi_module_number": 1,
            "dac_name": "dac0",
            "edge_group": 1,
        },        
        "q12_q13": {
            "spi_module_number": 2,
            "dac_name": "dac1",
            "edge_group": 2,
        }
    }),                
    cluster_config=ClusterConfig.model_validate({
      "config_type": "quantify_scheduler.backends.qblox_backend.QbloxHardwareCompilationConfig",
      "hardware_description": {
        "clusterA": {
          "instrument_type": "Cluster",
          "ref": "internal",
          "modules": {
            "1": {
              "instrument_type": "QCM_RF"
            },
          }
        }
      },
      # ...
    })
)
```

#### Customization of Nodes

A node is a `NodeSpec`: its schedule, sweeps, analysis and the device state's fields it sets.
You can pass in your own specs, to replace a default node or add one, with `node_specs`.

You can also change the order in which the nodes run or even choose to skip some of them
by supplying your own `ignored_nodes: tuple[NodeEnum, ...] = ...` and 
`node_dag_edges: tuple[tuple[NodeEnum, NodeEnum], ...]` as args to the entry point functions.

```python

import dataclasses

from tergite_tuner import tune_device, NodeEnum
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
        (NodeEnum.PUNCHOUT, NodeEnum.TOF,),
        (NodeEnum.QUBIT_01_SPECTROSCOPY, NodeEnum.COUPLER_ANTICROSSING),
    ),
    ignored_nodes=(NodeEnum.PUNCHOUT,)
)
```

### Public API

The library exposes the following entry points from
`tergite_tuner.__init__`:

```python
from tergite_tuner import (
    tune_device,
    reanalyse,
    generate_calib_seed_file,
    run_node,
    read_result,
    NodeEnum,
    SessionContext,
    CalibrationResults,
)
```

#### Run the full calibration pipeline

```python
from tergite_tuner import tune_device, read_result
from tergite_tuner.lib.nodes import NodeEnum

# Use a .env file as the only source of configuration
_, results = tune_device(env_file=".env")

# Or override individual SessionContext fields inline
session, results = tune_device(
    env_file=".env",
    target_node=NodeEnum.RABI_OSCILLATIONS,
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
)

# you can even pass a session from before or construct it yourself with 
# SessionContext.from_env()
tune_device(session=session, refresh_session=False)

# if you disabled session-refresh, you can read all results on 
# that session at once
results = read_result(session)
```

`tune_device` constructs a `SessionContext`, walks the dependency
DAG up to `target_node`, and calibrates any nodes that are not yet
in spec.

#### Recalibrate the device

A session's device state starts from `device_config.toml`, and nothing carries over from an earlier run
unless you pass it in: give an earlier calibration's results as `calibration`, as `tune_device` returns them
or as the `results.json` each run writes in its folder.
A session keeps its state across the calls you pass it to.

```python
from tergite_tuner import tune_device, NodeEnum

# Use a .env file as the only source of configuration
_, results = tune_device(env_file=".env")

# Or override individual SessionContext fields inline
session, results = tune_device(
    env_file=".env",
    target_node=NodeEnum.RABI_OSCILLATIONS,
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
    is_recalibration=False,
    ignore_spec=False,
)

# you can even pass a session from before or construct it yourself with 
# SessionContext.from_env()
_, results = tune_device(session=session, refresh_session=False)

# you could clear up all the data files after the run
_, results = tune_device(
    session=session, refresh_session=False, keep_data_files=False)
```

#### Run one node

```python
from tergite_tuner import run_node, NodeEnum, read_result

# Use a .env file as the only source of configuration
session, results = run_node(
    env_file=".env", node=NodeEnum.QUBIT_01_SPECTROSCOPY)

# Or override individual SessionContext fields inline
_, results = run_node(
    env_file=".env",
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
    node=NodeEnum.QUBIT_01_SPECTROSCOPY
)

# you can even pass a session from before or construct it yourself with 
# SessionContext.from_env()
run_node(
    node=NodeEnum.QUBIT_01_SPECTROSCOPY, session=session, refresh_session=False)

# if you disabled session-refresh, you can read all results on 
# that session at once
results = read_result(session)

# you could clear up all the data files after the run
_, results = run_node(
    node=NodeEnum.QUBIT_01_SPECTROSCOPY,
    session=session,
    refresh_session=False,
    keep_data_files=False,
)
```

#### Re-run analysis on already-recorded data

```python
from pathlib import Path
from tergite_tuner import reanalyse

_, results = reanalyse(
    env_file=".env",
    data_dir=Path("out/<run>/<node folder>"),  # the folder holding dataset_<node>.hdf5
)
```

#### Generate a BCC calibration seed

```python
from tergite_tuner import generate_calib_seed_file, tune_device

# From a session a run calibrated, as 'calibration.seed.toml' by default
session, _ = tune_device(env_file=".env")
generate_calib_seed_file(session=session)

# Or from earlier results, with the qubits and couplers from the .env file
generate_calib_seed_file(
    env_file=".env", calibration=results, path="/path/to/destination/toml/file"
)
```

### Samples

You can find a few examples in the [`./examples`](./examples) folder

### ToDo

- [ ] Update export to BCC to be more generic to allow any BaseModel class to be output

## Contributing to the project

If you would like to contribute to tergite-tuner, please have a look at our
[contribution guidelines](./CONTRIBUTING.md).

### Authors

This project is a work of
[many contributors](https://github.com/tergite/tergite-tuner/graphs/contributors).

Special credit goes to the authors of this project as seen in the [CREDITS](./CREDITS.md) file.

### Change log

To view the changelog for each version, have a look at
the [CHANGELOG.md](./CHANGELOG.md) file.

### License

When you submit code changes, your submissions are understood to be under the
same [Apache 2.0 License](./LICENSE.txt) that covers the project.

## Acknowledgements

This project was sponsored by:

- [Knut and Alice Wallenberg Foundation](https://kaw.wallenberg.org/en) under
  the [Wallenberg Center for Quantum Technology (WACQT)](https://www.chalmers.se/en/centres/wacqt/) project
  at [Chalmers University of Technology](https://www.chalmers.se)
-   [Nordic e-Infrastructure Collaboration (NeIC)](https://neic.no) and [NordForsk](https://www.nordforsk.org/sv) under the [NordIQuEst](https://neic.no/nordiquest/) project
-   [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQ](https://cordis.europa.eu/project/id/820363) project
-   [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQPlus](https://opensuperqplus.eu/) project
 