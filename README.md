# Tergite Automatic Calibration

![CI](https://github.com/tergite/tergite-autocalibration/actions/workflows/ci.yml/badge.svg)

A Python library that calibrates the WACQT quantum computers automatically.

This project contains a calibration runner, a collection of calibration
schedules, and a collection of post-processing and analysis routines.
It is developed and tested on the WACQT Quantum Computer at Chalmers
University of Technology.

**This project is developed by a core group of collaborators.**
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

Note: The Tergite stack is developed on a separate version control system and mirrored on GitHub.
If you are reading this on GitHub, then you are looking at a mirror.


## Quick Start

### Requirements

- Python ≥ 3.12 (a fresh `conda` or `venv` environment is fine).
- A reachable redis server. The default URL is
  `redis://127.0.0.1:6379/0`; override via the `REDIS_URL` env var or
  the `redis_url` keyword argument when calling the public API.

```shell
redis-server
```

### Installation

```shell
git clone git@github.com:tergite/tergite-autocalibration-lite.git
cd tergite-autocalibration-lite
python -m venv .venv && source .venv/bin/activate     # or use conda
pip install -e .
```

Copy the example environment file and edit it as needed:

```shell
cp .example.env .env
```

The `.env` file controls the cluster IP, redis URL, target node,
qubits/couplers under calibration, log levels, and so on. Every field
on `SessionContext` (see `tergite_autocalibration/config/session.py`)
can be set here, or passed as a keyword argument to the public API.

### Public API

The library exposes three entry points from
`tergite_autocalibration.__init__`:

```python
from tergite_autocalibration import (
    calibrate_device,
    rerun_analysis,
    generate_bcc_calibration_seed,
)
```

#### Run the full calibration pipeline

```python
from tergite_autocalibration import calibrate_device

# Use a .env file as the only source of configuration
calibrate_device(env_file=".env")

# Or override individual SessionContext fields inline
calibrate_device(
    env_file=".env",
    target_node="rabi_oscillations",
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
)
```

`calibrate_device` constructs a `SessionContext`, walks the dependency
DAG up to `target_node`, and calibrates any nodes that are not yet
in spec.

#### Re-run analysis on already-recorded data

```python
from tergite_autocalibration import rerun_analysis

rerun_analysis(
    env_file=".env",
    cluster_mode="re_analyse",
    log_dir="path/to/run/folder",
)
```

#### Export a BCC calibration seed

```python
from tergite_autocalibration import generate_bcc_calibration_seed

# Reads qubits / couplers / redis_url from the .env file. Returns a
# dict by default; pass ``format="json"`` or ``format="toml"`` to get
# a serialised string.
seed = generate_bcc_calibration_seed(env_file=".env")

# Or override individual SessionContext fields inline:
seed = generate_bcc_calibration_seed(
    qubits=["q00", "q01"],
    couplers=["q00_q01"],
    redis_url="redis://127.0.0.1:6379/0",
)

# Or write straight to disk:
generate_bcc_calibration_seed(
    env_file=".env",
    format="toml",
    output="calibration_seed.toml",
)
```

### Documentation

The documentation is maintained using [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). Everytime there is a release, you can find the
documentation from the release
on [https://tergite.github.io/tergite-autocalibration](https://tergite.github.io/tergite-autocalibration).

To preview the documentation for the branch you're currently working on you first need to install the project with documentation dependencies (only needed once):

```bash
pip install -e '.[docs]'
```
Then start the live preview server of the documentation from the root of the repository:

```bash
mkdocs serve
```

and open the URL shown in the terminal (typically [http://localhost:8000/](http://localhost:8000/)) in your browser.

If you are interested to edit the documentation, please check out the documentation section in
the [contribution guidelines](CONTRIBUTING.md#documentation). There is also a page in the documentation to help you
with [writing better documentation](./docs/developer-guide/writing_documentation.html).

## Contributing to the project

If you would like to contribute to tergite-autocalibration, please have a look at our
[contribution guidelines](./CONTRIBUTING.md).

### Authors

This project is a work of
[many contributors](https://github.com/tergite/tergite-autocalibration/graphs/contributors).

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
 