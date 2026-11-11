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
5. Make sure your code lints. This can be done by running: `ruff format --check tergite_tuner dev conftest.py`
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

### Contact information

Since the GitHub repositories are only mirrors, no GitHub pull requests or GitHub issue/bug reports
are looked at. Please get in touch via
email [contact@quantum.chalmersnextlabs.se](mailto://contact@quantum.chalmersnextlabs.se) instead.

## How to develop

Read [DESIGN.md](./DESIGN.md) first for how the code is laid out.

Install [uv](https://docs.astral.sh/uv/), then clone the repo and install it with its development and test
dependencies, exactly as `uv.lock` pins them:

```bash
git clone git@github.com:tergite/tergite-tuner.git
cd tergite-tuner
uv sync --all-groups
```

After changing a dependency in `pyproject.toml`, run `uv lock` and commit `uv.lock` with it; CI installs with
`--locked` and fails on a stale lock.

### Testing

```bash
uv run pytest tergite_tuner -n 4
```

`-m 'not slow'` leaves out the dummy run of every node: about 35 s, against 1 m 45 s for everything, on a
12-core MacBook. `conftest.py` at the repository root builds the session from the test configs in
`tergite_tuner/tests/fixtures/`.

| Tests | Where |
| --- | --- |
| a node's | its `tests/` folder, beside the recorded datasets they analyse (`tests/data/`) |
| the tuner as a whole | `tergite_tuner/tests/` |
| shared helpers | `tergite_tuner/tests/utils/`, one file per kind: `datasets.py`, `fixtures.py`, `goldens.py`, `runs.py`, `snapshots.py`, `state.py`, … |

- `test_public_api.py` calls the entry points as [docs/usage.md](./docs/usage.md) does; `test_export.py`
  covers `read_result` and the seed file.
- `test_tune_up.py` runs every default node in dummy mode, end to end; it is marked `slow`.
- A test's device state is JSON in the shape of `results.json`.
- A test that changes module state resets it: call `ExtendedTransmon.close_all()` before building a device,
  and restore a matplotlib backend you change.

### Goldens

Three tests pin what the nodes do. A change that alters one on purpose rewrites it with `UPDATE_GOLDENS=1`,
without `-n`, and its commit says why.

| Test | Pins |
| --- | --- |
| `test_schedule_goldens.py` | a digest of every default node's compiled program |
| `test_schedule_snapshots.py` | each node's sweeps, and every pulse, acquisition and loop of its compiled schedules, readably |
| `test_reanalysis_goldens.py` | the values 21 nodes' analyses find in recorded datasets |

Floating point differs between macOS and the CI runner's x86, and emulating x86 does not reproduce it: a
golden whose value sits close to a threshold is verified by a CI pipeline, not locally.

### Lint

`ruff format` formats. `ruff check` lints, with the isort rules (no separate isort); `pylint` checks duplicate code and function size; `vulture` finds unused definitions. Each has a baseline of the findings that predate it in `dev/lint/`:

```bash
uv run python -m dev.lint.baseline ruff      # or pylint, vulture
uv run python -m dev.lint.baseline ruff --update
```

The check fails on a finding the baseline lacks, and on an entry it no longer finds. A commit that fixes a finding runs `--update` and commits the shorter baseline; no commit adds to it.

`tergite_tuner/tests/test_styleguide.py` checks the rules below that a parser can see and the linters cannot: verbs, booleans, file order, banners, the licence header, `__all__`, type hints, the import layers (`utils` < `storage`, `config` < `lib` < `tuner`, `export`), quantify-scheduler and qblox-instruments imported in `backend` only, and no host takeover. Its baseline is `tests/fixtures/styleguide_baseline.txt`, which only shrinks. A new verb is added to its `VERBS` in review, never to the baseline.

### Performance

`dev/perf/record.sh <dir>` records each node's compile, dataset assembly and analysis (time and peak memory),
the dummy run of every node, the fast tests, the import and the install size.
`python -m dev.perf.compare dev/perf/baselines/<machine> <dir>` exits 1 when a measure is more than 15% worse
than that machine's baseline, past a noise floor. Each machine has its own baseline. A change that could
affect performance merges only when its recording compares clean; on a busy machine, record the base commit
too, back to back with the change, and compare the two.

### Before a merge request

- CI's whole job on a clean checkout of the commit, in a `git worktree`, so that untracked or ignored files
  cannot hide a missing fixture;
- the performance check above;
- a change to a schedule, an analysis or the hardware code tried on a real device: resonator spectroscopy,
  Rabi and T1, and the coupler spectroscopy and CZ chain where couplers are wired.

CI (GitLab, mirrored by GitHub Actions) runs on every merge request, on `main` and on tags, on Python 3.13:
`uv sync --locked`, `ruff format --check`, the three lint baselines, then pytest with coverage. A `v*` tag on
GitHub also builds and publishes the package.

### Where to start

| Task | Where |
| --- | --- |
| A new calibration node | a package under `lib/nodes/<group>/<node>/` with `node.py` (its `NodeSpec`: name, element, schedule, sweeps, analysis, QOIs, dummy model), `measurement.py`, `analysis.py`, and `tests/` with a recorded dataset |
| Run it in the default graph | a `NodeEnum` member, its spec in `DEFAULT_NODE_SPECS`, and its edges in `DEFAULT_NODE_DAG_EDGES` |
| A new device parameter | the extended transmon or edge in `backend/transmon.py` or `backend/edge.py`, and its initial value in `device_config.example.toml` |
| A new session option | a `SessionContext` field, `SessionOptions`, and `.example.env` |

### Code structure

The conventions are tergite-frontend's, so the two read alike. Code reads like an article: the overview
first, the detail below it.

1. **A function is a composition of functions.** A public function's body is a short sequence of calls, each to a function that does one thing and is named for it. Do not extract a step that would be a one-line function.
2. **Callees sit below their callers.** A file runs: constants, public functions in the order a caller uses them, then private helpers in the order they are first called.
3. **A comment that labels a phase is a missing function.**
4. **Data is a struct; state gets a class.** A node definition, a sweep, a fit or a config is a Pydantic model, frozen dataclass or named tuple. The Cluster connection, the SPI rack and the device state are classes. A class that holds only what its single method needs is a function.
5. **Stateless behaviour is a module-level function**, taking explicit arguments: a node's schedule, analysis and plot are its `get_schedule`, `analyse_<x>` and `plot_<x>`. No inheritance used only to share behaviour, no ABC with one implementation.
6. **Dependencies arrive as arguments.** Only the entry points turn configuration into instances. A function is given the store, the cluster or the value it needs, not the whole session.
7. **A library never takes over its host.** No `quit()`, no `matplotlib.use()`, no write to another package's globals that outlives the call, no write into the installed package. Errors are `TunerError`s from `exc.py`.
8. **One home per kind of thing.** The scheduler and the hardware drivers are imported in `backend/` only, device values are read from the session's state, tooling in `dev/`, shared test helpers in `tests/utils/`.
9. **Physics constants are named once**, at the top of the module that owns them: the CZ clock's downconvert frequency, the sweeps' widths and counts, the couplers' ±3.1 mA limit.
10. **A reputable library beats our own code.** Write our own only where no library does the job, or where getting the behaviour would mean fighting it; the commit says which.
11. **A name says what the thing is.** Variables are nouns, functions verbs, booleans `is_`/`should_`. No `build_*`: a constructed thing is a class's constructor, anything else is a `get_*`.
12. **Obvious beats clever.** An `if`/`else` that returns each whole literal; no comprehension that assembles operators, no helper that returns two things to be pulled apart.
13. **A value that is only defined stays where it is used.** A function that only returns a literal makes the reader jump for nothing.

### Style

- **Comments and docstrings earn their place**: the constraint, the gotcha, the *why* the code cannot say.
  One line where one line does. Never narrate the history of a fix.
- **Constants at the top** of the file, after imports. **Module-private helpers at the bottom.**
- **No banner comments** at any indent.
- **Tests**: the name says what is tested; a comment only when the why is not obvious.
- **License header** on every file: copy the block from a neighbouring module, and add a copyright line per
  contributing party.
- **Type hints** on every public function.

### Commits and changelog

- One logical change per commit.
- Every change users notice gets a [CHANGELOG.md](./CHANGELOG.md) entry under `[Unreleased]`, in
  `Added`/`Changed`/`Fixed`: one or two sentences on what changed and what a user would have hit before. The
  reasoning goes in the commit body.
- Versions are `{year}.{month}.{patch}`. A release sets the version in `pyproject.toml`, runs `uv lock`, and
  dates the `[Unreleased]` section.

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

