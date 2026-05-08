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

- Python ≥ 3.12 but < 3.13 (a fresh `conda` or `venv` environment is fine).
- A reachable redis server. The default URL is
  `redis://127.0.0.1:6379/0`; override via the `REDIS_URL` env var or
  the `redis_url` keyword argument when calling the public API.

```shell
redis-server
```

### Installation

```shell
git clone git@github.com:tergite/tergite-tuner.git
cd tergite-tuner
python -m venv .venv && source .venv/bin/activate     # or use conda
pip install -e .
```

Copy the example environment file and edit it as needed:

```shell
cp .example.env .env
```

The `.env` file controls the cluster IP, redis URL, target node,
qubits/couplers under calibration, and so on. Every field
on `SessionContext` (see `tergite_tuner/config/session.py`)
can be set here, or passed as a keyword argument to the public API.


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

### Public API

The library exposes three entry points from
`tergite_tuner.__init__`:

```python
from tergite_tuner import (
    tune_device,
    reanalyse,
    extract_bcc_params,
)
```

#### Run the full calibration pipeline

```python
from tergite_tuner import tune_device
from tergite_tuner.lib.nodes import NodeEnum

# Use a .env file as the only source of configuration
tune_device(env_file=".env")

# Or override individual SessionContext fields inline
tune_device(
    env_file=".env",
    target_node=NodeEnum.RABI_OSCILLATIONS,
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
)
```

`tune_device` constructs a `SessionContext`, walks the dependency
DAG up to `target_node`, and calibrates any nodes that are not yet
in spec.

#### Re-run analysis on already-recorded data

```python
from tergite_tuner import reanalyse

reanalyse(
    env_file=".env",
    log_dir="path/to/run/folder",
)
```

#### Export a BCC calibration seed

```python
from tergite_tuner import extract_bcc_params

# Reads qubits / couplers / redis_url from the .env file. Returns a
# dict by default; pass ``format="json"`` or ``format="toml"`` to get
# a serialised string.
bcc_params_1 = extract_bcc_params(env_file=".env")

# Or override individual SessionContext fields inline:
bcc_params_2 = extract_bcc_params(
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
    redis_url="redis://127.0.0.1:6379/0",
)

# Or write straight to disk:
extract_bcc_params(
    env_file=".env",
    format="toml",
    output="calibration_seed.toml",
)
```

## ToDos

- [ ] Remove logging to a directory. Let logs log to the default logger but maybe with a unique format
- [ ] Reduce the number of logs or change the level of logging
- [x] Allow the input of the node_graph via an argument in the entry point functions, with a good default
- [x] Move the example configs to the root of the project
- [x] Move the default location of configs to the root of the project, not a folder
- [x] Remove the config meta
- [x] Enable configs to be passed as python objects in the args of the entry point functions, as opposed to files
- [ ] Add a return value to all entry point functions, e.g. the output of the export to bcc can be the return of tune_device
- [x] Fix MotzoiParameter measurement for recalibration vs bringup
- [x] Improve typing intellisense for the entry functions

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
 