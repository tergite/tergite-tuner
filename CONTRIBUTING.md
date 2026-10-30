# Contributing to tergite-tuner

**This project is currently not accepting pull requests from the general public yet.**

**It is currently being developed by the core developers only.**

[Chalmers Next Labs AB (CNL)](https://chalmersnextlabs.se) manages and maintains this project on behalf of all
contributors.

## General information about contributions

Tergite is developed on a separate version control system and mirrored on GitHub.
If you are reading this on GitHub, then you are looking at a mirror.

The following subsections are only relevant for people that are onboarded on the internal version control system.

### Contribute by using merge requests

Merge requests are the best way to propose changes to the codebase. We use a pattern similar to the
[GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow) and actively welcome your merge
requests.

1. Clone the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation. Read the section below on documentation.
4. Ensure the test suite passes. Run: `pytest tergite_tuner`
5. Make sure your code lints. This can be done by running: `black tergite_tuner --check`
6. Create the merge request!

### Issues and bug reports

Good bug reports can make it way easier for a developer to solve the issue.
A good bug report tends to contain:

- A quick summary and/or background
- Provide steps to reproduce the error
    - Be specific!
    - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

Here is [one example](http://stackoverflow.com/q/12488905/180626)
and [another example](http://www.openradar.me/11905408) on how to write a good bug report.

### Versioning

When versioning we follow the format `{year}.{month}.{patch_number}` e.g. `2023.12.0`.
Please find out more about versioning in the [change log](./CHANGELOG.md).

### Contact information

Since the GitHub repositories are only mirrors, no GitHub pull requests or GitHub issue/bug reports
are looked at. Please get in touch via
email [contact@quantum.chalmersnextlabs.se](mailto://contact@quantum.chalmersnextlabs.se) instead.

## How to develop

Make sure you have [conda](https://docs.anaconda.com/free/miniconda/index.html) installed.
Alternatively, you could also simply have [Python 3.12](https://www.python.org/downloads/) installed.
Clone the repo and enter its root folder:

```bash
git clone git@github.com:tergite/tergite-tuner.git
cd tergite-tuner
```

Create the conda environment

```bash
conda create -n tac python=3.12 -y
```

Install dependencies with development and test dependencies

```bash
conda activate tac
pip install -e ".[test,dev]"
```

A couple of configuration files are required in one folder whose path you can set via the `CONFIG_DIR` env var. (See [`.example.env` file](./.example.env) for more details)

- [`configuration.meta.toml`](./tergite_tuner/config/templatesconfiguration.meta.toml): 
  It holds metadata about the other files
- [`configs/cluster_config.json`](./tergite_tuner/config/templates/fc8a/configs/cluster_config.json): 
  It is the [`quantify-scheduler`](https://quantify-os.org/docs/quantify-scheduler/v0.27.1/tutorials/Compiling%20to%20Hardware.html#hardware-compilation-configuration) configuration json file
- [`configs/device_config.toml`](./tergite_tuner/config/templates/fc8a/configs/device_config.toml): 
  It contains details about the quantum chip
- [`configs/node_config.toml`](./tergite_tuner/config/templates/fc8a/configs/node_config.toml): 
  It contains details about the calibration nodes to run
- [`configs/spi_config.toml`](./tergite_tuner/config/templates/fc8a/configs/spi_config.toml): 
  It contains details about the SPI instrument for driving the couplers


### Testing

Tests require a redis instance running on port 6378.

```bash
redis-server --port 6378 {--daemonize yes}
```

Optionally, add `--daemonize yes` to run the redis instance in the background.
If it does not run on your user, try running it again with `sudo` rights.

Run the pytests for the whole application.

```bash
pytest tergite_tuner
```

You can find more information about unit tests in the documentation.

### Calibration Pipeline

Each calibration node goes through the following phases in order:

- compilation
- execution
- post-processing
- redis updating

## License

When you submit code changes, your submissions are understood to be under the
same [Apache 2.0 License](./LICENSE.txt) that covers the project. Feel free to contact the maintainers if that's a
concern.

### Contributor License Agreement

Before you can submit any code, all contributors must sign a
contributor license agreement (CLA). By signing a CLA, you're attesting
that you are the author of the contribution, and that you're freely
contributing it under the terms of the Apache-2.0 license.

The [individual CLA](https://tergite.github.io/contributing/icla.pdf) document is available for review as a PDF.

Please note that if your contribution is part of your employment or
your contribution is the property of your employer,
you will also most likely need to sign a [corporate CLA](https://tergite.github.io/contributing/ccla.pdf).

All signed CLAs are send by email
to [contact@quantum.chalmersnextlabs.se](mailto://contact@quantum.chalmersnextlabs.se).

## References

This document was adapted from [a gist by Brian A. Danielak](https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62) which
was originally adapted from the open-source contribution guidelines
for [Facebook's Draft](https://github.com/facebook/draft-js/blob/a9316a723f9e918afde44dea68b5f9f39b7d9b00/CONTRIBUTING.md)

