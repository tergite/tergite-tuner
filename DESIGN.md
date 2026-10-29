# Tergite Tuner — Design

This document describes the architecture of `tergite-tuner`, a library that calibrates the WACQT quantum computers: how a calibration run flows from an entry point to the hardware and back to Redis, where each kind of code lives, how it is configured and tested, and the conventions a contributor is expected to follow. [REFACTOR.md](REFACTOR.md) is the plan that is moving the code towards these conventions; where the two differ, the code is mid-refactor and this document describes what is there.

## 1. What this repo is

A Python library (3.13+) that a program imports to tune up a chip: tergite-backend, a notebook, or a script. It is a stripped-down fork of [tergite-autocalibration](https://github.com/tergite/tergite-autocalibration), without its CLI, GUI or dataset browser.

| Part | Path | Role |
| --- | --- | --- |
| Entry points | `tergite_tuner/tuner.py`, `export.py` | `tune_device`, `run_node`, `reanalyse`, `read_result`, `generate_calib_seed_file` |
| Configuration | `tergite_tuner/config/` | `SessionContext` and the four config files' models |
| Nodes | `tergite_tuner/lib/nodes/` | one package per calibration experiment |
| Node machinery | `tergite_tuner/lib/base/`, `lib/nodes/{schedule_node,external_parameter_node}.py` | what every node inherits: measure, configure the dataset, analyse, store |
| Storage | `tergite_tuner/storage/` | `redis/` holds the device's parameters; `fs/` writes each node's dataset |
| Hardware | `tergite_tuner/utils/hardware/spi.py`, `tuner.py`'s `HardwareManager` | the Qblox cluster, through quantify-scheduler, and the SPI rack's current sources |
| Device model | `tergite_tuner/utils/types/extended_*.py` | quantify-scheduler's transmon and edge, extended with our gates and parameters |

It depends on quantify-scheduler 0.22 and qblox-instruments 0.14, as tergite-backend does. The move to qblox-scheduler is step 11 of the refactor.

## 2. A calibration run

```mermaid
flowchart TD
    E["tune_device / run_node / reanalyse"] --> S["SessionContext<br/>(.env + kwargs + config files)"]
    S --> H["HardwareManager<br/>Cluster, InstrumentCoordinator, attenuations"]
    S --> M["NodeManager<br/>the node DAG, populate_initial_parameters"]
    M --> I["inspect_node, for each node up to target_node"]
    I -->|in spec| R["skip"]
    I -->|out of spec| N["node = node_cls(qubits, couplers, session)"]
    N --> T["measurement_type_cls: ScheduleNode, OuterScheduleNode or ExternalParameterNode"]
    T --> C["precompile: Measurement.schedule_function → compile_schedule"]
    C --> X["execute_schedule on the InstrumentCoordinator<br/>(or generate_dummy_dataset in dummy mode)"]
    X --> D["configure_dataset → save_dataset (data_dir/&lt;timestamp&gt;-&lt;node&gt;/)"]
    D --> A["analysis_cls: per-qubit or per-coupler fits → QOIs"]
    A --> Q["post_process: QOIs → Redis transmons / couplers, cs = calibrated"]
```

1. **The session.** `SessionContext.from_env` reads the `.env` file, then the environment variables that name a field, then the keyword arguments, and loads `device_config`, `node_config`, `spi_config` and `cluster_config` from their paths. It carries the Redis connection and `RedisStore` with it.
2. **The graph.** `DEFAULT_NODE_DAG_EDGES` in `lib/nodes/__init__.py` lists `(parent, child)` edges, and `node_cls_map` maps each `NodeEnum` to its class. `NodeManager.topo_order` walks the ancestors of `target_node` in topological order, leaving out `ignored_nodes`.
3. **Each node.** `inspect_node` reads the node's status in `cs:<element>`. A node in spec is skipped. Otherwise it is built, its `node_config` section is written to Redis, and it is measured, saved and analysed. After that, the node-config values are reverted to the device config's (unless `is_recalibration`).
4. **Measuring.**
   - `ScheduleNode` compiles one schedule.
   - `OuterScheduleNode` compiles one per point of `outer_schedule_samplespace`, for sweeps too large for the instrument's memory.
   - `ExternalParameterNode` compiles once and re-runs it per point of `external_samplespace`, calling the node's `initial_operation`, `pre_measurement_operation` and `final_operation` around it (to set an SPI current, or to wait).
5. **Analysing.**
   - `BaseAllQubitsAnalysis` and `BaseAllCouplersAnalysis` split the dataset by element, run the node's single-element analysis on each, and plot when `save_plot` is set.
   - Each analysis returns a `QOI` per element, holding `{field: {"value", "error"}}` and whether it succeeded.
   - `post_process` writes the successful ones to Redis and marks the element `calibrated` for that node.

**Modes.** `cluster_mode` is `real`, `dummy` (a dummy cluster, and each node's `generate_dummy_dataset` in place of acquisitions) or `re_analyse` (no hardware; `reanalyse` runs the target node's analysis on `data_dir`). `spi_mode` is `real` or `dummy`.

## 3. Layout

```
tergite_tuner/
├── __init__.py            the public API
├── tuner.py               tune_device, run_node, reanalyse; HardwareManager, NodeManager
├── export.py              read_result, generate_calib_seed_file, CalibrationResults
├── exc.py                 TunerError and its subclasses
├── config/
│   ├── session.py         SessionContext, SessionOptions
│   └── types/             DeviceConfig, NodeConfig, SpiConfig, ClusterConfig
├── lib/
│   ├── base/              BaseNode, QubitNode, CouplerNode; the analysis base classes
│   ├── nodes/             readout/, qubit_control/, characterization/, coupler/: one package per node
│   │   └── <group>/<node>/   node.py, measurement.py, analysis.py, tests/
│   └── utils/             schedule compiling and execution, device building, fit models, the DAG
├── storage/
│   ├── redis/             RedisStore, populate/revert node parameters
│   └── fs/                datasets and node data folders
├── utils/                 logging, enums, NodeEnum, the extended device types, the SPI rack
└── tests/                 cross-cutting tests; utils/ holds the shared test helpers
conftest.py                the session_context, redis_connection and seeded_redis fixtures
```

## 4. Data

Redis holds the device as the tuner knows it, one hash per element, and fakeredis stands in for it in the tests.

| Key | Holds |
| --- | --- |
| `transmons:<qubit>` | the transmon's parameters, nested paths joined by `:` (`rxy:amp180`, `clock_freqs:f01`), each QOI beside its `_error` |
| `couplers:<coupler>` | the coupler's parameters (`parking_current`, `cz_pulse_amplitude`, …) |
| `cs:<element>` | the calibration status per node: `calibrated` or `not_calibrated` |

`RedisStore` serialises each value with its type, so it reads back as written. `populate_initial_parameters` seeds the hashes from `device_config` at the start of a run. `read_result` returns what the session touched, or everything, as `CalibrationResults`. `generate_calib_seed_file` turns that into the TOML seed tergite-backend reads.

Each measured node writes a folder under `data_dir`: the dataset (`dataset_<node>.hdf5`), the device's serialised elements (`<node>.json`), and its plots.

## 5. Configuration

| Source | Holds |
| --- | --- |
| `.env` / `SessionContext` fields | cluster IP and mode, SPI port and mode, Redis URL, qubits, couplers, target node, flags, the paths below. See [.example.env](.example.env) |
| `device_config.toml` | the chip: initial qubit, resonator and coupler values, under `all` or per element |
| `node_config.toml` | per-node overrides written to Redis while the node runs, under `all` or per qubit |
| `spi_config.toml` | which SPI module and DAC drives each coupler |
| `cluster_config.json` | quantify-scheduler's hardware compilation config |

Each can also be passed as an object. The README shows both.

## 6. Testing

`pytest tergite_tuner`, with fakeredis, so no Redis server is needed. `conftest.py` at the repository root builds the session from the test configs in `tergite_tuner/tests/fixtures/`.

- Each node's tests live in its `tests/` folder, beside the recorded datasets they analyse (`tests/data/`).
- Shared helpers live in `tergite_tuner/tests/utils/`, grouped by what they do: `fixtures.py`, `redis.py`, `pytest.py`.
- `tests/test_precompile.py` compiles every default node against the test cluster config.
- `tests/test_reanalysis_goldens.py` reruns 19 nodes' analyses on recorded datasets and compares the QOIs with `tests/fixtures/goldens/`. A change that moves a value on purpose rewrites its golden with `UPDATE_GOLDENS=1`, and its commit says why.
- `tests/test_tune_up.py` runs every default node in dummy mode, end to end, on a calibrated device from `standard_redis_mock.json`. It takes about five minutes, so it is marked `slow`: run `pytest -m 'not slow'` while working, and the whole suite before pushing, as CI does.

A test that changes module state resets it: call `ExtendedTransmon.close_all()` before building a device, and restore a matplotlib backend you change.

## 7. CI

GitLab CI ([.gitlab-ci.yml](.gitlab-ci.yml)) and GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) run the same job on Python 3.13, on every merge request, on `main` and on tags: `uv sync --locked`, which fails on a stale `uv.lock`; `black --check`; the ruff, pylint and vulture baselines; then pytest with coverage, which includes the style-guide test. A `v*` tag on GitHub also builds and publishes the package. GitLab is the source of truth; GitHub is a mirror.

## 8. Working on this repo

### Versioning and releases

`{year}.{month}.{patch}`, e.g. `2026.06.0`. A release sets the version in `pyproject.toml` and dates the `[Unreleased]` section of [CHANGELOG.md](CHANGELOG.md).

### Changelog entries

One or two sentences: what changed, and what a user would have hit before. Always under `[Unreleased]`, under `Added` / `Changed` / `Fixed`. The reasoning belongs in the commit body.

### Commits

One logical change per commit, decided before editing. Never add assistant attribution to commit messages or merge request bodies.

### Slow commands

Redirect a test run to a file and read the file, rather than re-running it:

```bash
pytest tergite_tuner > "$LOG" 2>&1; echo "exit=$?" >> "$LOG"
```

Record the exit status beside it: a pipe reports its own status, so `pytest | tail` reads as green when the suite failed.

### Code structure

The conventions are tergite-frontend's, so the two read alike. Code reads like an article: the overview first, the detail below it.

1. **A function is a composition of functions.** A public function's body is a short sequence of calls, each to a function that does one thing and is named for it. Do not extract a step that would be a one-line function.
2. **Callees sit below their callers.** A file runs: constants, public functions in the order a caller uses them, then private helpers in the order they are first called.
3. **A comment that labels a phase is a missing function.**
4. **Data is a struct; state gets a class.** A node definition, a sweep, a QOI or a config is a Pydantic model or frozen dataclass. The Cluster connection, the SPI rack and the Redis connection are classes. A class that holds only what its single method needs is a function.
5. **Stateless behaviour is a module-level function**, taking explicit arguments. No inheritance used only to share behaviour, no ABC with one implementation.
6. **Dependencies arrive as arguments.** Only the entry points turn configuration into instances. A function is given the store, the cluster or the value it needs, not the whole session.
7. **A library never takes over its host.** No `quit()`, no `matplotlib.use()`, no write to another package's globals that outlives the call, no write into the installed package. Errors are `TunerError`s from `exc.py`.
8. **One home per kind of thing.** The scheduler is imported in one package (from refactor step 5), Redis only through `RedisStore`, tooling in `dev/`, shared test helpers in `tests/utils/`.
9. **Physics constants are named once**, at the top of the module that owns them.
10. **A reputable library beats our own code.** Write our own only where no library does the job, or where getting the behaviour would mean fighting it; the commit says which.
11. **A name says what the thing is.** Variables are nouns, functions verbs, booleans `is_`/`should_`. No `build_*`: a constructed thing is a class's constructor, anything else is a `get_*`.
12. **Obvious beats clever.** An `if`/`else` that returns each whole literal; no comprehension that assembles operators, no helper that returns two things to be pulled apart.
13. **A value that is only defined stays where it is used.** A function that only returns a literal makes the reader jump for nothing.

### Lint

`black` formats. `ruff check` lints, with the isort rules (no separate isort); `pylint` checks duplicate code and function size; `vulture` finds unused definitions. Each has a baseline of the findings that predate it in `dev/lint/`:

```bash
uv run python -m dev.lint.baseline ruff      # or pylint, vulture
uv run python -m dev.lint.baseline ruff --update
```

The check fails on a finding the baseline lacks, and on an entry it no longer finds. A commit that fixes a finding runs `--update` and commits the shorter baseline; no commit adds to it.

`tergite_tuner/tests/test_styleguide.py` checks the rules below that a parser can see and the linters cannot: verbs, booleans, file order, banners, the licence header, `__all__`, type hints, the import layers (`utils` < `storage`, `config` < `lib` < `tuner`, `export`), quantify-scheduler and Redis each imported in one package only, and no host takeover. Its baseline is `tests/fixtures/styleguide_baseline.txt`, which only shrinks. A new verb is added to its `VERBS` in review, never to the baseline.

### Python style

- **Comments and docstrings earn their place**: the constraint, the gotcha, the why the code cannot say. One line where one line does. Never narrate the history of a fix.
- **Constants at the top** of the file, after imports, except one built from a function or class defined in the same file. **Module-private helpers at the bottom.**
- **No banner comments** at any indent.
- **Tests**: the name says what is tested; a comment only when the why is not obvious.
- **License header** on every file: copy the block from a neighbouring module, and add a copyright line per contributing party.
- **Type hints** on every public function.

### Adding a node

| Task | Where |
| --- | --- |
| A new calibration node | a package under `lib/nodes/<group>/<node>/` with `node.py` (the class: name, `measurement_cls`, `analysis_cls`, `measurement_type_cls`, `qubit_qois` or `coupler_qois`, the samplespace), `measurement.py` (`schedule_function`), `analysis.py`, and `tests/` with a recorded dataset |
| Run it in the default graph | a `NodeEnum` member, an entry in `DEFAULT_NODE_CLS_MAP`, and its edges in `DEFAULT_NODE_DAG_EDGES` |
| A new device parameter | the extended transmon or edge in `utils/types/`, and its initial value in `device_config.example.toml` |
| A new session option | a `SessionContext` field, `SessionOptions`, and `.example.env` |
