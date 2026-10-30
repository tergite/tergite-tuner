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

Read [DESIGN.md](./DESIGN.md) first: the architecture, the conventions and where to start for a new node.

Install [uv](https://docs.astral.sh/uv/), then clone the repo and install it with its development and test dependencies, exactly as `uv.lock` pins them:

```bash
git clone git@github.com:tergite/tergite-tuner.git
cd tergite-tuner
uv sync --all-groups
```

The configuration files a run needs are described in the [README](./README.md#installation), with an example of each at the repository root.

### Testing

```bash
uv run pytest tergite_tuner -n 4
```

After changing a dependency in `pyproject.toml`, run `uv lock` and commit `uv.lock` with it; CI installs with `--locked` and fails on a stale lock.

### Calibration Pipeline

Each calibration node goes through the following phases in order:

- compilation
- execution
- post-processing
- storing its values in the session's device state

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

