# Change log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project follows versions of format `{year}.{month}.{patch_number}`.

## [Unreleased]

### Added

- Added the `delete_many()` and `prune_fields()` methods on the `RedisStore`

### Changed

- Removed setting QOI's of nodes to nan and 0 before calibration runs

## [2026.06.0-rc.1] - 2026-05-15

### Changed

- [BREAKING] Changed the output of `read_results` to return a stronger-typed `CalibrationResults` 
  pydantic model instance
- [BREAKING] Renamed `read_session_results` to `read_results`
- [BREAKING] Renamed `extract_bcc_params` to `generate_calib_seed_file`
- [BREAKING] Changed `extract_bcc_params` (i.e. `generate_calib_seed_file`) to return no value
  and only work with writing to a toml file. If one wants the results in dict or json form,
  they can use the output of `read_results` and call `model_dumps` and `model_dumps_json` on it.
- Added a `session_only` parameter on `read_results` to allow getting all results in redis regardless
  of session if `session_only=True`

### Fixed

- Removed the hard-coded fixes for CZ local phases for reverse phase qubits

## [2026.05.1] - 2026-05-12

### Fixed

- Fixed wrong structure of data in redis 'cs' collection on post-processing the node

### Changed

- Updated dependencies to match those in tergite-backend e.g. "quantify-scheduler~=0.22.2"
- Removed the `LOG_DIR` option on SessionContext so that all that is needed is the `DATA_DIR`
- Changed the `FIXED_DURATION_QUBITS` SessionContext option to `FIXED_DURATION_COUPLERS` since it is the couplers
  that would have the fixed duration, not the qubits.

## [2026.05.0] - 2026-05-09

### Added

- Added the `read_session_results` function to the entry point
- Added `keep_data_files` and `refresh_session` params to the entry point
  functions of `tune_device`, `reanalyse` and `run_node`
- Added the `is_recalibration` (`IS_RECALIBRATION`) SessionContext flag 
  to disable certain operations that would be destructive in a recalibration
- Added `run_node` function for running only a single calibration node.
- Public API exported from `tergite_tuner.__init__`:
  `tune_device`, `reanalyse`, `run_node` and
  `extract_bcc_params`. The first two replace the old
  `CalibrationSupervisor` class and accept an env-file path plus
  arbitrary `SessionContext` field overrides as kwargs.
- `SessionContext` (`config/session.py`): a single per-process pydantic
  model that carries every value driving a calibration run — env
  config, target node, qubits/couplers, redis connection, loaded
  configuration package — and is threaded through every Node and
  analysis Go-context style. `SessionContext.from_env(file, **kwargs)`
  merges values from a `.env` file with `os.environ` and explicit
  overrides.
- `Configuration`, `MetaConfigFile`, `DeviceConfigFile`,
  `NodeConfig`, `SpiConfig`, `ClusterConfig` pydantic models
  for typed loading and validation of every config file in a
  configuration package.
- `__NODE_ENUM_CLS_MAP__` and `__NODE_STR_CLS_MAP__` static lookup
  tables (`lib/nodes/__init__.py`) plus `__NODE_DEPENDENCIES__` —
  replace the dynamic-reflection `NodeFactory` and the module-level
  `GRAPH_DEPENDENCIES` / `CALIBRATION_GRAPH` globals.
- `loaded_redis(redis_connection, path)` context manager — replaces
  the `@with_redis` decorator.
- `extract_bcc_params(...)` accepts `format="dict" | "json"
  | "toml"` and an optional `output` path. The seed shape is now a
  pydantic model (`CalibrationSeed`) with the static unit labels as
  field defaults.
- Added `examples` folder
- Added `FIXED_DURATION_QUBITS` env variable for setting qubits with
  fixed duration working points for CZ calibration
- Added back the `Rx_12` gate in the `extended_gates` module

### Changed

- Changed the storage to use `RedisStore`, a wrapper around redis
  which puts the data persistence code in one layer
- Enabled passing the node_dag_edges, ignored_nodes and node_cls_map 
  as arguments in the entry point functions, defaulting to the 
  constants `DEFAULT_IGNORED_NODES`, `DEFAULT_NODE_CLS_MAP`,
  and `DEFAULT_NODE_DAG_EDGES,` in the nodes package.
- Moved example config files to the root of the project
- Enabled loading of the config as either objects, dicts, or files (file paths)
- Renamed to project fork to tergite-tuner
- Stripped away all code that is not relevant for running this app as
  a library; the calibration entry points are now plain functions
  rather than a `CalibrationSupervisor` class.
- Removed the dynamic-reflection `NodeFactory` in favour of the
  static `__NODE_ENUM_CLS_MAP__`. `NodeManager` now accepts
  `node_enum_cls_map`, `ignore_nodes`, and `node_dependencies`
  constructor kwargs (defaulting to the canonical maps) and builds
  its `nx.DiGraph` itself.
- `NodeEnum` is now a `str, Enum` keyed by the lowercase canonical
  node name; redis hash fields, log lines, and exported payloads use
  that string consistently.
- Removed all chart/plot code from the calibration pipeline. The
  library is now headless-safe: no `colorama` ANSI escapes, no
  matplotlib backend setup, no `plotter()` methods on analyses, no
  `figures_dictionary` plumbing, and no `plotting` field on
  `SessionContext`.
- Replaced the dynamic global state (`SESSION`, `REDIS_CONNECTION`,
  `CONFIG`) with explicit dependency injection via `SessionContext`.
- `REDIS_PORT` env var replaced with `REDIS_URL`.
- `lib/utils/graph.py`'s topological-order helpers are now generic
  over a `_T` TypeVar and require `exclude_nodes` to be an explicit
  iterable; module-level `GRAPH_DEPENDENCIES` / `CALIBRATION_GRAPH` /
  `EXCLUDED_NODES` / `filtered_topological_order` deleted.
- `conftest.py` moved to the repository root so it is no longer
  shipped with the built wheel.
- Made `session: SessionContext` arg on Analysis classes mandatory
- Removed the `data` folder in the lib directory
- Moved data files of nodes to their individual folders
- Moved redis to the `storage` pacakge
- Renamed `io` utils to `fs` and moved it to the storage package

### Removed

- `scripts/` folder (`calibration_supervisor.py`, `export_to_bcc.py`,
  `migrate_qblox_hardware_configuration.py`,
  `calibration_seed_template.toml`).
- `lib/utils/node_factory.py`, `utils/misc/reflections.py`,
  `lib/base/utils/figure_utils.py`.
- The `calibration_seed_template.toml` that used to ship with the
  package — the seed shape is now expressed as a pydantic model.
- Stale fixture data: `default_device_under_test_copy/`,
  `21-39-55_cz_rb-SUCCESS/`, per-node `tests/data*` and
  `tests/results` directories that were no longer referenced, and
  ~30 stray fixture files (~22 MB).
- `process_tomography` from the canonical class map until the missing
  `Rxy_12` extended-gate import is restored; its `NodeEnum` member
  remains but no class is registered.
- Removed `decorators` and `helpers` that are no longer used in the actual code (vs in tests)

## [2026.03.0] - 2026-03-06

- No Change

## [2025.12.0] - 2026-03-16

### Added

- Backup functions for redis storage
- Motzoi parameter for DRAG pulse in tergite SDK
- CLI endpoint for automatic mixer calibration

### Changed

- Removed development folder (can still be accessed in the git history)
- Replaced MSS update script with BCC calibration seed script
- Refactored CZ Parametrization node
- Added CZ Chevron node
- Added CZ local phases node
- Removed quickstart endpoint
- Moved scripts that handle SPI operations to the CLI
- Cleanup of the BaseNode
- Interface for measurement types
- Wizard for the hardware configuration

### Fixed

- Fixes in the n_rabi_12_oscillations
- Improvements in how coupler data is loaded from redis
- Cleanup unused scripts and modules

## [2025.09.0] - 2025-09-16

### Added

- Datasets from IQT Nordics

### Changed

- Data browser uses plotly instead of PyQT and integrates better with CLI
- Run single calibration node in re-analysis
- Migrated documentation from Quarto to MkDocs Material.

### Fixed

- Simplify GitLab pipeline

## [2025.06.0] - 2025-06-16

### Added

- Better labelling for the analysis output plots

### Added

- Analysis for the punchout node

### Changed

- Upgrade Python to version 3.12
- Migration from poetry to setuptools
- Make external samplespace multidimensional

### Fixed

- Reduced the packaged library size to below pypi's limit by using a `MANIFEST.in` file

## [2025.03.0] - 2025-05-16

### Added

- Advanced logging
- Debugging endpoint
- Quickstart endpoint to generate templates semi-automatically

### Changed

- Rename all node class names to camel case
- Re-analysis is more user-friendly
- Make pipeline more modular
- Improved node documentation

### Fixed

## [2024.12.0] - 2024-12-12

### Added

- Dataset browser
- ScheduleNode and ExternalParameterSweepNode as subclasses of BaseNode
- DeviceManager class
- Configuration packages
- Advanced decorators for pytest

### Changed

- Migrated cli from click to typer
- Switch to quantify-scheduler version 0.21.2
- Switch to qblox-instruments version 0.14.1 (qblox-firmware should be 9.0.1)
- Upgrade to Python version 3.10

## [2024.09.0] - 2024-09-16

### Added

- superconducting_qubit_tools as conditional dependency
- Calibration node for purity benchmarking
- Redis storage manager
- GitLab CI/CD

### Changed

- Refactoring of the node classes to allow hierarchical class structures

### Fixed

## [2024.04.0] - 2024-05-29

This is part of the tergite release v2024.04 that updates the full pipeline for state discrimination hardware
calibration

### Added

- All research-related features regarding the calibration of a CZ gate
- Updater to push calibration values as a backend to MSS/database

### Changed

- Improved command line interface
- Renamed from tergite-acl to tergite-tuner
- Updated the contribution guidelines and government model statements

### Fixed

## [2024.02.0] - 2024-03-19

This is part of the tergite release v2024.02 which introduces authentication, authorization and accounting to the
tergite stack.

No major change except for the versions.

### Added

### Changed

### Fixed

## [2023.12.0] - 2024-03-14

This is part of the tergite release v2023.12.0 that is the last to
support [Labber](https://www.keysight.com/us/en/products/software/application-sw/labber-software.html).
Labber is being deprecated.

### Added

- Initial release of the automatic calibrator

### Changed

### Fixed

### Contributors

- Eleftherios Moschandreou
- Stefan Hill
- Liangyu Chen
- Tong Liu
- Martin Ahindura
- Michele Faucci Giannelli