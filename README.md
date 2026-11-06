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

## Installation

```shell
pip install tergite-tuner
```

It needs Python 3.13.

## Quick Start

This tunes up one qubit on a dummy cluster, so it needs no hardware. It uses the example configs at the root
of this repository.

- Clone the repo and install it with [uv](https://docs.astral.sh/uv/getting-started/installation/)

```shell
git clone https://github.com/tergite/tergite-tuner.git
cd tergite-tuner
uv sync
```

- Copy the example environment file

```shell
cp .example.env .env
```

- In `.env`, set the cluster to a dummy one, and choose a qubit and the node to stop at

```shell
CLUSTER_MODE='dummy'
QUBITS='q06'
TARGET_NODE='qubit_01_spectroscopy'
```

- Save this as `tune.py`, and run it with `uv run python tune.py`

```python
from tergite_tuner import tune_device

session, results = tune_device(env_file=".env")
print(results.transmons["q06"].clock_freqs)
```

It runs resonator spectroscopy, then qubit spectroscopy, in under a minute, and prints the frequencies it
found. Each run's data and `results.json` are in `out/`.

To tune a real device, set `CLUSTER_MODE='real'` and `CLUSTER_IP`, and describe your chip and cluster in the
config files: see [docs/configuration.md](./docs/configuration.md).

## Documentation

| Document | Read it to |
| --- | --- |
| [docs/configuration.md](./docs/configuration.md) | configure a run: the `.env` file and the config files |
| [docs/usage.md](./docs/usage.md) | tune up, recalibrate, run one node, reanalyse, write a seed for tergite-backend, or customise the nodes |
| [examples/](./examples) | see complete calibration scripts |
| [DESIGN.md](./DESIGN.md) | understand how the tuner is built, before changing it |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | run the tests and follow the code conventions |
| [docs/open_work.md](./docs/open_work.md) | see what is unfinished, and what still needs a real device |

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
 