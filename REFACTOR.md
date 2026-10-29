# Refactor plan

Thirteen steps, 0 to 12, in order. Each numbered item is one commit, verified before the next. Step 8 (Cliffords) can run in parallel with steps 6 and 7.

The audit behind this plan read every module. Line numbers are as of `main` at `9cd6ca6e`. Findings marked *suspect* are reproduced with a test before anything changes.

## Branches

tergite-backend pins `tergite-tuner~=2026.06.0-rc.5`, which is built on quantify-scheduler 0.22 and qblox-instruments 0.14. `main` has since merged the move to qblox-scheduler 1.0.0b8 and qblox-instruments 1.4 (`e280b601`, merged in `9cd6ca6e`, tagged `v2026.10.0-rc.1`). The backend cannot install that alongside its own quantify stack. Both lines need the refactor.

Refactoring both lines would double the work. Instead, refactor once on the quantify line and replay the migration at the end:
- Step 5 puts the scheduler behind `backend/`.
- After that, the migration is a change to one package (step 11) instead of the 63 files `e280b601` touched.

1. **The refactor is based on `0746b7ec`**: `main` just before the migration merge, which is `v2026.06.0` plus the renovate config. Two commits from the migration branch are cherry-picked onto it, as neither depends on the migration:
   - `0c97a77d`, the quantify-core fitting models copied in;
   - `c133bb83`, which requires Python 3.13. tergite-backend runs on 3.13 with the same quantify-scheduler, and pip refused the tuner for its `<3.13` bound.
2. **`main` becomes the quantify line again** through `git revert -m 1 9cd6ca6e`.
   - Use a revert, not a force-push: `main` is mirrored to GitHub and `v2026.10.0-rc.1` is tagged on it.
   - The migration stays on `feature/qblox-scheduler-migration` as the reference for step 11.
   - If rc.1 reached PyPI, the next quantify-based release is versioned above it.
3. **Releases for the backend** are cut from `main` at any step's sign-off, as before.
4. **The bug list below was written against the migrated tree.** On `0746b7ec` the node code differs mostly in its imports, and `quit()` and the `GRID_TIME_TOLERANCE_TIME` write are there too. Each item is relocated when its test is written. Items that exist only after the migration (`_flatten_acquisitions`, the `BinMode` deprecation) move to step 11.

## Conventions

The conventions are tergite-frontend's (`DESIGN.md` §14 "Code structure"), so the two repositories read alike; step 1.1 copies them into this repository's own `DESIGN.md`. Rules 1–4, 9–11 and 14 apply unchanged:
- a function is a composition of functions;
- callees sit below callers;
- a comment that labels a phase is a missing function;
- a reputable library beats our own code;
- a name says what the thing is (no `build_*`);
- obvious beats clever;
- a value that is only defined stays where it is used.

The rest are adapted to a calibration library:

1. **Data is a struct; state gets a class.**
   - A node definition, a sweep, a QOI and a config are Pydantic models or frozen dataclasses.
   - A component that owns state across calls (the Cluster connection, the SPI rack, the Redis connection) is a class.
   - A `*Measurement` class that holds only a dict of transmons, or a `MeasurementType` that holds only the node, is a function.
2. **Stateless behaviour is a module-level function.**
   - A schedule is `get_<x>_schedule(transmons, sweeps, ...) -> Schedule`.
   - An analysis is `analyse_<x>(dataset, ...) -> dict[str, Fit]`.
   - A plot is `plot_<x>(axes, dataset, fit)`.
   - Not allowed: inheritance used only to share behaviour, an ABC with one implementation, an `__init__` that only calls `super().__init__`.
3. **Dependencies arrive as arguments.**
   - No function reads `SessionContext` for one value. It is given the store, the cluster, the SPI rack or the value it needs.
   - Only the entry points in `tuner.py` turn configuration into instances: `tune_device`, `run_node`, `reanalyse`, `generate_calib_seed_file`.
4. **A library never takes over its host.**
   - No `quit()`/`sys.exit`, no `matplotlib.use(...)`.
   - No write to another package's module globals (`GRID_TIME_TOLERANCE_TIME`), and no write into the installed package at import time.
   - Errors are exceptions from `tergite_tuner/exc.py`.
5. **One home per kind of thing.**
   - The scheduler (quantify-scheduler, and qblox-scheduler from step 11) is imported only in `tergite_tuner/backend/`.
   - Redis is touched only through `RedisStore`: nothing calls `session.redis.hget`.
   - Dummy-data generators, the hash-table generator, the benchmarks and other tooling live in `dev/`.
   - Shared test helpers live in `tergite_tuner/tests/utils/`, grouped by what they do.
6. **Physics constants are named once.** This covers the 4.4 GHz downconvert frequency (seven copies today), the sweep widths and sample counts (`lib/utils/samplespace.py`), and the ±3.1 mA DAC limit. Each is a constant at the top of the one module that owns it, or a config field.
7. **Unchanged from the user style guide:**
   - the Apache 2.0 header on every file;
   - constants at the top, private helpers at the bottom;
   - no banner comments;
   - nouns for variables, verbs for functions, `is_`/`should_` for booleans;
   - comments only for what the code cannot say.

`run_node` after step 6 (signatures illustrative):

```python
def run_node(node: NodeEnum, session: SessionContext, hardware: Hardware) -> CalibrationResults:
    spec = session.node_specs[node]
    if is_in_spec(hardware.store, spec, session.elements(spec)):
        return read_result(hardware.store, session)
    dataset = measure(spec, hardware, get_sweeps(spec, session))
    save_run(dataset, hardware.device, session.data_dir)
    fits = analyse(spec, dataset)
    save_qois(hardware.store, spec, fits)
    return read_result(hardware.store, session)
```

**Every commit is verified the same way:** `uv run` the step 1 linters (they also run in CI) and the style-guide test, then `uv run pytest tergite_tuner > "$LOG" 2>&1; echo "exit=$?" >> "$LOG"` against Redis on port 6378. `DESIGN.md` changes in the same commit as any file it names. A commit that fixes a baselined lint or style-guide violation deletes its baseline entry, and no commit adds one.

**Every step ends with a sign-off.** Its last commit adds `docs/prototypes/<NN>-<step>.md`, a short acceptance script:
- the dummy tune-up of step 2.1;
- the reanalysis of step 2.2's recorded datasets;
- the step 3 performance comparison;
- at the end of steps 5, 6, 9 and 11, one real run on the testbed: resonator spectroscopy → Rabi → T1, and the coupler spectroscopy → CZ chain where couplers are wired.

Someone with testbed access runs it and gives the go-ahead before the next step.

## Step 0: fix the bugs

The only behaviour changes in the plan. Each commit adds a test that fails before the fix, and gets a `Fixed` changelog entry. Where a decision is needed, it is marked **Decide** with a recommendation.

**Runner and base**

1. `tuner.py:93`: `quit()` when the Cluster refuses the connection kills the host process. Raise `ClusterUnreachableError`.
2. `lib/base/node.py:60`: every node calls `matplotlib.use("tkagg" if session.save_plot else "agg")`.
   - Saving a plot selects the interactive Tk backend, which fails on a headless server.
   - Switching the backend also changes the caller's own plots.
   - Remove it: plots are saved with `Figure.savefig`, which works under any backend.
3. `lib/base/node.py:317, 531`: `precompile` sets the scheduler's `backends.qblox.constants.GRID_TIME_TOLERANCE_TIME = 5e-2` on every compile.
   - Find what needs the tolerance (likely the ns rounding in CZ durations), and round the durations instead.
   - If it cannot be avoided, set it once in `backend/` with a comment that says why.
4. `lib/base/node.py:76`: `self.samplespace` is computed from two empty dicts before any subclass fills them, so it is always `{}`. `reset_chevron/node.py:40` reads it. Delete the attribute.
5. `lib/base/node.py:141`: `BaseNode` has no `generate_dummy_dataset`.
   - Dummy mode raises `AttributeError` on Punchout, NRabi12, Qubit01SpectroscopyAmplitude, T1, T2, T2Echo, AllXY, Purity and ResonatorSpectroscopyVsCurrent.
   - Step 6.6 moves dummy data out of the nodes. Until then, a generic random-IQ dataset in the base keeps every node runnable.
6. `lib/nodes/schedule_node.py:57`, `external_parameter_node.py:52`: `list(keys())[0]` on an empty samplespace is an `IndexError`. AllXY and Purity reach it. Fixed with item 7.
7. **Nodes in the default DAG that cannot run:**
   - **AllXY:**
     - its outer samplespace is empty;
     - `AllXYAnalysis.__init__(self, dataset)` does not match the call at `base/node.py:158`;
     - `analysis.py:49` calls the missing `rotate_to_probability_axis`;
     - `node.py:30` sets `redis_field` instead of `redis_fields`.
   - **PurityBenchmarking:**
     - it has no external operations, and its external samplespace is empty;
     - it passes `loop_repetitions`, which the measurement does not take;
     - it never passes `seeds`.
   - **Decide:** fix both, or take them out of `DEFAULT_NODE_CLS_MAP` until someone needs them. Recommended: take them out now (one commit each, `Changed` entry) and fix them when needed, since no run has exercised them.
8. `config/session.py:409`: `from_env` lowercases all of `os.environ` into a model with `extra="allow"`.
   - Every environment variable becomes a session attribute and appears in `model_dump()`: `PATH`, `HOME`, tokens.
   - Any variable that shares a field's name overrides it. WSL sets `NAME`, which renames the run.
   - Fix: read only the declared fields. Step 7.1 replaces this with pydantic-settings.
9. `lib/base/analysis.py:271`: `BaseCouplerAnalysis.__init__` takes `**kwargs` and drops them, so the per-coupler `analysis_keywords` that `BaseAllCouplersAnalysis` passes (`:401`) never arrive. Set them as `BaseQubitAnalysis` does, until step 6.4 makes them arguments.
10. `lib/base/analysis.py:363`: coupler plots call `tight_layout` after `savefig`, so the saved file is not laid out. They also save only the 100-dpi preview, where qubit plots save both resolutions.
11. `storage/redis/utils.py:44`: `populate_node_parameters` applies only the `all` section of a node's config to qubits, so a per-qubit section (`[node.q01]`) is silently ignored. `revert_node_parameters` never reverts coupler sections. Make both honour per-element sections.
12. `export.py:63`: `read_result(session_only=True)` keeps a field when its name is a *substring* of a touched field, so `amp180` matches `ef_amp180`. Compare whole field paths.
13. `export.py:132-133` labels `t1_decoherence`/`t2_decoherence` in the seed file as `us`, but the T1 and T2 fits are in seconds.
    - *Suspect*: confirm against a recorded T1 dataset, then fix the unit or the value.
    - The docstring at `:78-94` documents a `format` argument and a return value; neither exists.

**Nodes: readout and qubit control**

14. Every qubit gets the last transmon's pulse duration: `rabi_oscillations/measurement.py:75, 83 → 116`, `ro_amplitude_optimization/measurement.py:59 → 110`. Read the duration per qubit inside the loop.
15. `qubit_control/spectroscopy/measurement.py:207-211`: for `spec_duration > 6.5e-6` the branch is `pass`. `SpectroscopyPulse` is then unbound, or holds the previous qubit's value. Use `long_square_pulse`, which exists for this case.
16. `readout/resonator_spectroscopy/analysis.py`:
    - `:143-145` stores `Ql_1` as a frequency.
    - In `:57-113`, a failed fit is logged, then the `finally` reads an unset attribute.
    - A `return` inside that `finally` swallows any exception, so `analysis_successful` is always true.
    - Fix: return a failed QOI when the fit fails.
17. `readout/ro_amplitude_optimization/`:
    - `analysis.py:411` writes `inv_cm_opt = 0` instead of the `optimal_inv_cm` it computed at `:345`.
    - `utils.py:62-74`'s threshold branch can never be taken, so it always returns `-absolute_threshold`.
18. Success checks that always pass:
    - `qubit_control/spectroscopy/analysis.py:110, 260` set `hasPeak`, then overwrite it with `True`, so noise passes as a peak.
    - `qubit_control/rabi_oscillations/analysis.py:57-60` hard-codes the fit uncertainty to 0, so the success gate always passes and the reported error is always 0.
19. `readout/punchout/analysis.py:122-133`:
    - plots frequency on the amplitude axis;
    - highlights the last subplot when no amplitude matches;
    - stores `None` with success when every frequency is NaN.
20. *Suspect*, all three:
    - `motzoi_parameter/measurement.py:98` and `ramsey_fringes/measurement.py:89` drive the 1–2 transition with the 0–1 `rxy.duration`, where NRabi12 uses `r12.ef_duration`. `test_motzoi_parameter_measurement.py:72` pins the current value.
    - `resonator_spectroscopy/measurement.py:130` passes motzoi 0 where the other readout nodes pass `ef_motzoi`.
    - On reanalysis, `ramsey_fringes/analysis.py:36` and `rabi_oscillations/analysis.py:144` apply their correction to a base value already corrected in Redis.

**Nodes: couplers and characterization**

21. `coupler/cz_calibration/analysis.py`:
    - `:109` computes `|Δφ−180|_min + 180`, which loses the sign, so the stored CZ phase is always ≥ 180°.
    - `:29` bounds the phase to ±360, while `sin_func` works in radians.
    - `:165` subtracts off−on where `:104` subtracts on−off.
22. `coupler/cz_parametrization/measurement.py:83-86` resets and excites `self.qubits` (every qubit) inside each coupler's loop. In a multi-coupler run, that puts X on the other couplers' qubits.
23. `coupler/tqg_randomized_benchmarking/`:
    - `measurement.py:130-139` benchmarks only the first coupler.
    - `:180` sets the interleaving Clifford once and never resets it, so the result depends on the order of `interleave_modes`.
    - `analysis.py:109-119, 225-237` assume interleaving was run.
    - `:286-293` plot the standard data as "interleaved".
    - `node.py:76` reads the key `coupler:` instead of `couplers:`.
    - *Suspect*: Clifford 4368 is CZ followed by six single-qubit gates, which biases `cz_fidelity` low. PycQED uses the bare CZ, 104368.
24. `tqg_randomized_benchmarking/utils/two_qubit_clifford_group.py`:
    - `:222`: the cache is pre-filled with `[]` but checked with `is None`, so `SingleQubitClifford.gate_decomposition` always returns `[]`.
    - `:188`: `__str__` returns a bound method.
    - `:555`: when the hash file is missing, it is written into the installed package.
    - Step 8 deletes the module; until then, one test pins the decomposition.
25. *Suspect*: `cz_calibration/node.py:153` matches fixed-duration couplers by substring, so `q1_q2` also matches `q1_q23`. `base/node.py:221, 267` do the same (`measured_qubit in coupler`). Compare split names.
26. Smaller defects:
    - `coupler/spectroscopy/analysis.py:44, 271` have mutable default arguments.
    - `coupler/spectroscopy/analysis.py:346-351` swaps control and target.
    - `utils/cliffords.py:229-234` raises `UnboundLocalError` when nothing matches.
    - `characterization/purity_benchmarking/measurement.py:91` drops the 128/256/512 lengths.

**Tests that test nothing**

27. Fix each of these so that it fails when the code is wrong:
    - `rabi_oscillations/tests/test_rabi_oscillations_measurement.py:57, 93` define two tests with the same name, so the first never runs.
    - `punchout/tests/test_qubit_analysis.py:32-60` checks `amplitude - x < 0.001` without `abs`.
    - `resonator_spectroscopy/tests/test_resonator_spectroscopy.py:61` uses `approx(rel=1e3)`.
    - `punchout/tests/test_node.py` is skipped, and wrong.

## Step 1: tooling, lint and the style guide in CI

After this step, CI rejects any commit that makes the code less clean than it is today. Every later commit is checked by it.

1. **`DESIGN.md`**, with:
   - the architecture as it is: entry points → `NodeManager` → node → measurement type → scheduler → analysis → Redis;
   - the conventions above;
   - the style guide;
   - "where to start" for a new node.
   `CONTRIBUTING.md` points to it, and drops conda and `pip install -e`.
2. **uv.** The repository is not on uv yet: it has no `uv.lock`, and CI runs `pip install --group test --group dev .`.
   - `pyproject.toml` already declares PEP 735 dependency groups, which uv reads, so the move is small. The remote branch `136-migrate-ci-cd-pipeline-from-pip-to-uv…` has a start.
   - Commit `uv.lock`, and have CI run `uv sync --locked`. A stale lock fails CI.
3. **Linters, each pinned in the dev group and configured in `pyproject.toml`:**
   - **ruff check**, with `F` (pyflakes), `I` (isort; today's `[tool.isort]` lacks `profile = "black"`, so isort and black rewrite each other's imports), `E`/`W`, `B` (bugbear: mutable defaults, unused loop variables), `UP`, `SIM`, `C4`, `RET`, `ARG` (unused arguments) and `T20` (no `print`). It replaces running pyflakes and isort separately.
   - **Today's violations** are stamped once with `ruff check --add-noqa`. Each `# noqa` is that tool's baseline, and a commit that fixes one deletes it.
   - **Formatting:** **Decide** between `black` (pinned, as tergite-frontend uses it) and `ruff format`, its drop-in. Recommended: `ruff format`, so one tool covers lint and formatting.
   - **pylint**, for what ruff lacks:
     - `duplicate-code` (R0801), the copy-paste this repository is full of, with `min-similarity-lines=8`;
     - the design limits (`too-many-statements=50`, `too-many-branches`, `too-many-locals`).
     - Its findings are compared with `dev/lint/pylint_baseline.json` by `dev/lint/check_pylint.py`, which fails on any finding not in the baseline.
   - **vulture**, for dead code, with today's findings in `dev/lint/vulture_whitelist.py` as its baseline. Step 4 empties most of it.
4. **`tergite_tuner/tests/test_styleguide.py`**, ported from tergite-frontend: the rules a parser can see and the linters cannot. They are checked with `ast` over the package:
   - every file carries the licence header;
   - no banner comments;
   - no `build_*`;
   - function names start with a verb;
   - booleans start with `is_`/`should_`;
   - module constants come before the first function;
   - module-private helpers come after the public functions;
   - no `quit`, `exit` or `matplotlib.use`;
   - no `redis` import, and no `.redis.` access, outside `storage/`;
   - no scheduler import outside `backend/` (enforced from step 5);
   - a service-style `__init__.py` only re-exports, with `__all__`;
   - no test helper outside `tests/utils/`.

   Today's violations go in `tests/styleguide_baseline.txt`. The test fails on a violation not in the baseline, and on a baseline line that no longer occurs, so that the baseline only shrinks.
5. **CI runs all of it on every merge request, on `main` and on tags, in GitLab and in the GitHub mirror alike:** `uv sync --locked`, the formatter's check, `ruff check`, the pylint and vulture checks, then pytest with coverage (which includes the style-guide test). The `README.md` badge stays on the GitHub workflow.
6. **`docs/prototypes/`**, with a README saying it holds this refactor's acceptance scripts and is deleted at step 12.

## Step 2: pin behaviour with tests

Tests only. After this step, a refactor commit that changes behaviour fails a test.

1. **A whole tune-up in dummy mode** (the README TODO). `tune_device(cluster_mode="dummy", spi_mode="dummy")` walks the default DAG on two qubits and one coupler against fakeredis, and every node reaches analysis. This test catches a node that cannot run (steps 0.5–0.7).
2. **Golden reanalysis per node.**
   - For every node with a recorded dataset under `tests/data`, reanalyse it and compare the QOIs with a committed JSON, within a tolerance.
   - For nodes without one, record a dummy dataset with a fixed seed.
   - Steps 6 and 8 must keep every value.
3. **Golden schedules.**
   - For each node, compile its schedule against `cluster_config.example.json` with fixed device values.
   - Pin a digest of the compiled program: the sequencer programs, the waveforms and the acquisition metadata.
   - Steps 5 and 6 must keep every digest. Step 11 re-baselines them, as qblox-scheduler compiles differently.
4. **Public API.** `tune_device`, `run_node`, `reanalyse`, `read_result` and `generate_calib_seed_file` are each called the ways the README shows, including a custom node class through `node_cls_map`. The seed file is compared with a committed one.

## Step 3: performance baselines

These are recorded before any refactor commit and rerun at every step's sign-off. A step is not signed off while any measure is worse than its baseline beyond the threshold, until the cause is found.

"Performance" here has two halves:
- the time and memory the tuner spends around the instrument;
- the quality of the calibration it produces.

The refactor must lower neither.

1. **Per-node benchmarks** with `pytest-benchmark`, in `dev/perf/test_nodes.py`, over every node in the default DAG:
   - **schedule:** building and compiling against `cluster_config.example.json`. This is the cost a tune-up pays per node, and per point of an outer sweep;
   - **dataset:** assembling the raw acquisitions into the node's dataset (`configure_dataset`);
   - **analysis:** fitting and plotting the step 2.2 golden datasets;
   - **peak memory** of each of the three, through `tracemalloc`.
2. **Whole runs:**
   - the wall time and peak RSS of the step 2.1 dummy tune-up;
   - `python -X importtime -c "import tergite_tuner"`, which is the cost of importing the scheduler and of everything set up at import time (loggers, the Clifford tables);
   - the installed size and package count of a fresh `uv sync --no-dev` environment. Step 11 is judged on this.
3. **On the testbed**, at the sign-offs that include a real run:
   - **time:** wall time per node, split into compile, instrument and analysis. `run_node` logs the three phases' durations at `INFO`, so a run's log is its measurement.
   - **quality:** readout assignment fidelity, single-qubit RB fidelity, T1 and T2, and CZ fidelity where couplers are wired.
   - **How quality is judged:** these drift from day to day, so they are compared with a same-day run of the baseline tag on the same qubits, not with a fixed number.
4. **`dev/perf/record.sh <dir>`** records items 1 and 2 into a directory; the baselines live in `dev/perf/baselines/`.
   - `dev/perf/compare.py dev/perf/baselines <dir>` exits 1 when any time, memory, import time or install size is more than 10% worse.
   - The 10% is a starting threshold, tuned once the first runs show how noisy each measure is.
   - CI runs `record.sh` and `compare.py` on one fixed runner. It reports without failing until the noise is known, then fails like any other check.
5. **A faster test suite.** The suite takes about 2 minutes for 320 tests, and every commit runs it. Investigate, then make one commit per finding:
   - `pytest --durations=30` shows where the time goes. `test_precompile.py` compiles every node, and quantify-scheduler compilation is the likely cost.
   - Fixtures rebuilt per test that can be session-scoped: the session context, loaded Redis dumps, compiled devices.
   - `pytest-xdist` (`-n auto`), once the tests that share module state (`ExtendedTransmon.close_all()`, the global matplotlib backend) are isolated.
   - A `slow` marker for the compile-everything tests, so the per-commit run can skip them while CI runs all of them.
   - Record the suite's wall time in `dev/perf/baselines/` with the rest, so the refactor does not slow it down.

## Step 4: delete what nothing uses

No behaviour change; the step 2 tests stay green. Each deletion also removes its lines from the step 1 baselines.

1. **Dead nodes:**
   - `coupler/reset_chevron/`: about 980 lines, 239 of them commented out. Its `__init__` cannot run, and nothing references it.
   - `characterization/process_tomography/`: about 544 lines, commented out of the map.
   - `cz_parametrization/utils/no_valid_combination_exception.py`.
   - **Decide:** delete, or move to a branch of their own. Recommended: delete; the history keeps them.
2. **Dead classes and functions:**
   - the analyses `OptimalRO2not2Amplitude*Analysis` (`ro_amplitude_optimization/analysis.py:514-705`) and `QubitSpectroscopyAnalysis` (`spectroscopy/analysis.py:31-134`);
   - `ParabolicFit`, `classify_iq`, `rotated_y_limits`, and the unused `mitigate` in `randomized_benchmarking/analysis.py:29`;
   - `graph.range_dependencies_in_topological_order` and `schedule_execution.display_duration_information`;
   - `SpiDAC.ramp_current_simultaneusly`, `print_currents` and `close_spi_rack` (`Hardware` closes the rack from step 11.3);
   - the unused enums `DataStatus.bad_data`/`undefined`, `CalibrationResultStatus` and `ApplicationStatus`;
   - `utils/reanalysis.py`, used only by its tests.
3. **Dead code inside live functions:**
   - the commented-out blocks;
   - values assigned and then overwritten (`rabi/node.py:51`, `cz_parametrization/node.py:109`, `randomized_benchmarking/node.py:38`, `purity_benchmarking/node.py:35`);
   - the `0 * noise` terms and the `+ 0 * 50e6`;
   - `fit_y`, `motzoi_minima` and `fit_results`;
   - `loops_coord`/`number_of_loops` in about six analyses;
   - `BaseAnalysis.qoi` and `BaseNodeAnalysis.qoi`, properties that only forward `_qoi`.
4. **Dependencies:**
   - Drop `h5py` and `requests`; neither is imported.
   - Keep one of `toml` and `tomlkit`: `tomlkit`, which already writes the seed file, or the standard `tomllib` for reading.
   - Declare what we import but get only transitively: `cf_xarray`, `rich` and `tqdm`.
   - Import `xarray` directly, not through the scheduler's `instrument_coordinator.utility`.
5. **Docstrings and comments**, per convention 7:
   - the numpydoc blocks that restate their parameters, and are wrong (`motzoi:44-66`);
   - the no-op docstring string inside `randomized_benchmarking/measurement.py:39-58`;
   - the phase-label comments, which step 6 turns into function names.

## Step 5: one backend for the scheduler

Everything the scheduler gives us goes behind `tergite_tuner/backend/`:
- The rest of the code is written against our own vocabulary.
- Step 11's migration, and any later change of scheduler, changes one package.
- On this line, `backend/` wraps quantify-scheduler.
- The step 2.3 schedule digests pin this step.

```
tergite_tuner/backend/
├── __init__.py      re-exports, __all__ as strings
├── operations.py    Schedule, ClockResource, the gates and pulses we use, SSBIntegrationComplex, long_square_pulse, our AcquisitionMode
├── device.py        QuantumDevice, ExtendedTransmon, ExtendedCompositeSquareEdge, Measure_RO1/3state, configure_device, save_serial_device
├── compile.py       compile_schedule(schedule, device) -> CompiledSchedule
└── execute.py       Hardware (Cluster, InstrumentCoordinator), run_schedule(hardware, compiled) -> xr.Dataset
```

1. **Move the device types.** `utils/types/extended_*.py` and `lib/utils/device.py` move to `backend/device.py`. Everything outside `backend/` imports from there.
2. **`compile_schedule`** replaces the two copies of `precompile` in `QubitNode` and `CouplerNode` (`base/node.py:316, 530`), which differ only in the edges.
3. **`run_schedule`** replaces `execute_schedule`:
   - It drops the fake progress thread (`schedule_execution.py:37-49`), which only sleeps for the estimated duration. Log the estimate instead, or use the coordinator's real progress if it reports any.
   - The hard-coded 3600 s wait becomes the session's `cluster_timeout`.
4. **`AcquisitionMode`**, our own enum, replaces `BinMode` (22 uses). It is mapped to the scheduler's own setting in one place.
5. **Shared schedule building blocks**, one commit each, moving every measurement onto them:
   - `get_multiplexed_schedule(name, transmons, sweeps, add_point, repetitions)` replaces the skeleton all 10 readout and qubit-control schedules copy: root reset, per-qubit reset, the nested sweep with its `acq_index` arithmetic, measure, reset. It iterates in the order `configure_dataset` reshapes (`order="F"`), so that ordering lives in one place.
   - `prepare_state(schedule, transmon, state)`, `get_drive_clock(qubit, state)`, `get_measure_operation(state)` and `add_12_clocks(schedule, transmons)` replace the 0/1/2-state dispatch copied in 8 measurements. The ef π DRAG pulse alone is built 4 times.
   - From the 5 CZ measurements: `add_cz_clock(schedule, coupler, cz_frequency)` with `DOWNCONVERT_FREQUENCY` defined once, `add_pair_measurement(schedule, control, target, acq_index, ref_op)`, and `get_repeated_schedule(name, shot, loop_repetitions, padding)`.
6. **`Hardware`** replaces `HardwareManager`.
   - It is a class, as it owns the Cluster connection, the instrument coordinator and the SPI rack. The entry point creates it and passes it to the node.
   - `set_output_attenuations` stays a function of `(cluster, connectivity, attenuations)`.
   - The dummy Cluster's modules come from `cluster_config.hardware_description`, not from a hard-coded 15 QCM_RF + 2 QRM_RF (`tuner.py:104`).

## Step 6: a node is data

Today a node is a class hierarchy, `BaseNode → QubitNode/CouplerNode → *Base → Node`. Beside it are a `*Measurement` class, a `MeasurementType` class and three analysis classes.

No node overrides `precompile`, `measure_node`, `post_process` or `configure_dataset`. Each node differs only in:
- its name and its sweeps;
- its schedule and its analysis;
- its QOIs, its state and its loops.

```python
@dataclass(frozen=True)
class NodeSpec:
    name: NodeEnum
    element: Literal["qubit", "coupler"]
    get_schedule: Callable[..., Schedule]
    analyse: Callable[[xr.Dataset], dict[str, Fit]]
    qois: tuple[str, ...]
    sweeps: Mapping[str, SweepFn]                    # parameter -> (element, session) -> ndarray
    outer_sweeps: Mapping[str, SweepFn] = {}         # schedules too large for one run
    external_sweeps: Mapping[str, SweepFn] = {}      # SPI current, waiting time
    state: Literal[0, 1, 2] = 0
    loops: int | None = None
    plot: Callable[[Axes, xr.Dataset, dict[str, Fit]], None] | None = None
```

1. **`measure(spec, hardware, sweeps) -> xr.Dataset`** replaces `ScheduleNode`, `OuterScheduleNode` and `ExternalParameterNode`.
   - It walks the outer and external sweeps itself.
   - The external operations become calls on `Hardware`: set a current, or wait.
   - The special case `if self.node.name == "cz_calibration"` (`schedule_node.py:71`) becomes the outer sweep's own coordinate, a `MultiIndex`.
   - `configure_dataset` (`base/node.py:188`, 100 lines) becomes `get_dataset(raw, spec, sweeps, elements)`.
2. **`analyse` returns values; the spec names them.**
   - Six 01/12 analysis pairs differ only in the QOI key: motzoi, Rabi, NRabi, Ramsey, qubit spectroscopy and resonator spectroscopy. Each pair collapses into one function.
   - `qoi_to_redis_record` takes `(spec.qois, fits)`.
   - The 13 one-line `XNodeAnalysis(BaseAllQubitsAnalysis)` classes disappear.
   - `BaseAllQubitsAnalysis`/`BaseAllCouplersAnalysis` become `analyse_elements(spec, dataset)`, built on one function that splits a dataset by element (its `element` attribute). That function replaces `filter_ds_by_element`, `_group_by_coupler` and the `"_" in name` checks.
3. **Coordinate names are computed, not searched.** `configure_dataset` names coordinates `quantity + element`, and about 17 analyses then find them by substring (`for coord in coords: if "loops" in coord`). `get_coord_name(quantity, element)` replaces the search.
4. **Plots are separate functions.**
   - `plot_elements(spec, dataset, fits, path)` lays out the grid and saves the 100- and 400-dpi images.
   - It replaces `_manage_plots`, `_fill_plots` (3 copies), `_save_plots` and `display_and_save_plots`.
   - An analysis never holds a figure.
5. **Node specs.**
   - `lib/nodes/__init__.py` defines `DEFAULT_NODE_SPECS: Mapping[NodeEnum, NodeSpec]` in place of `DEFAULT_NODE_CLS_MAP`. One node per commit, each kept green by its step 2.2 golden.
   - The `qubit_samples`/`resonator_samples` helpers become `SweepFn`s, with their widths and counts as constants (convention 6).
   - **Public API:** `node_cls_map` stays accepted for one release, with a `DeprecationWarning`, and is converted by `NodeSpec.from_node_cls`. The README's custom nodes and the step 2.4 test keep working. `Changed` entry.
6. **Dummy data leaves the nodes.**
   - `generate_dummy_dataset` is copied across 13 nodes, with `np.random.seed` called inside loops.
   - `dev/dummy.py` replaces them with `get_dummy_dataset(spec, sweeps, signal, rng)`. It takes one signal model per kind (resonator dip, Rabi cosine, decay, random IQ) and one `numpy.random.Generator` passed in.
   - Dummy mode uses it through `Hardware`.
7. **Calibration status.**
   - `reset_qois` and `_check_calibration_status_redis` become `mark_not_calibrated(store, spec, elements)` and `is_in_spec(store, spec, elements)`. These replace the two copies in `QubitNode`/`CouplerNode` and the raw `hget` in `tuner.py:280`.
   - `reset_qois` only initialises missing statuses, so the new name says what it does.
   - A missing status raises `MissingCalibrationStatusError`.
8. **Delete the class hierarchy:**
   - `BaseNode`, `QubitNode` and `CouplerNode`;
   - `BaseMeasurement`, `MeasurementType`, `ScheduleNode`, `OuterScheduleNode` and `ExternalParameterNode`;
   - the analysis base classes;
   - `NodeManager`, whose `inspect_node` becomes the `run_node` composition above.

## Step 7: configuration and the session

Today `SessionContext` is passed to every function, and it holds:
- the configuration;
- the Redis connection and the store;
- the node registry;
- a log of touched fields.

It also makes `config/` import `lib/` (`session.py:65`), to get the node class map.

1. **pydantic-settings.**
   - `SessionContext` becomes a `BaseSettings`. It reads the `.env` file and the environment for its declared fields only.
   - Its built-in parsing replaces the hand-written casting validators: bools, enums by name, and comma-separated lists through a `NoDecode` field with one validator.
   - **Decide:** precedence. Today the `.env` file overrides the environment, the reverse of pydantic-settings, Docker and twelve-factor. Recommended: let the environment win, with a `Changed` entry.
   - `is_recalibration` and `ignore_spec` default to `True`, which the README's examples contradict. Pick defaults the README can state.
2. **Config apart from runtime.**
   - The Redis connection and `RedisStore` leave the model: the entry point creates them and passes them in.
   - `redis_fields_touched` becomes a value that `run_node` returns.
   - `config/` no longer imports `lib/`; the entry point fills in the node defaults.
   - `cluster_config` is typed with `backend/`'s `ClusterConfig`.
3. **One loader per config file.**
   - `DeviceConfigFile.from_toml`, `NodeConfig.from_toml`, `SpiConfig.from_toml` and `ClusterConfig.from_json` share one `load_config(model, path)`.
   - The hand-written `__getitem__`/`__contains__`/`__iter__` on `NodeConfig` and `SpiConfig` go, since `RootModel` gives `.root`.
4. **Safe deletion.** `is_safe_path` (`tuner.py:498`) guards `shutil.rmtree(session.data_dir)` with a list of five system paths. Replace it with deleting only what this run created: its own subfolder.

## Step 8: one Clifford implementation

Today there are two complete implementations of the two-qubit group:
- `clifford_group.py`, which builds an in-memory table;
- `two_qubit_clifford_group.py`, with crc32 hash files.

Two-qubit RB generates its sequences with one and decomposes them with the other. The two agree on all 11,520 elements today, but nothing keeps them in step.

On top of those, there are three single-qubit tables (`clifford_group.py:39`, `clifford_decomposition.py:41`, `utils/cliffords.py:25`) and a separate PTM implementation in `utils/cliffords.py`.

1. **Keep `clifford_group.py`**, moved to `lib/utils/cliffords.py`. It is PycQED-derived and tested, and its in-memory table builds in 0.8 s, so it needs no hash files. The step 3 import-time measure checks that it stays lazy.
2. **Single-qubit RB and purity benchmarking** use its `randomized_benchmarking_sequence(clifford_group=1)` and one gate-name → `Rxy` map.
3. **Delete:**
   - the old `utils/cliffords.py`;
   - `two_qubit_clifford_group.py` and `clifford_decomposition.py`;
   - `generate_clifford_hash_tables.py`;
   - `clifford_hash_tables/` (124 KB).

   Of the three `ExpDecayModel` copies, keep the one in `analysis_models.py`, and keep one copy of `mitigate`.
4. **Library check, recorded in the commit.** qiskit's `Clifford` composes and inverts, but it synthesises to cx/h/s. Our native X/Y90 + CZ decomposition would then need a transpile step and a heavy dependency, and pyGSTi is heavier still. Our own code wins: this is convention 9's "fighting the library" case.

## Step 9: long functions and the rest

1. **Long functions become compositions**, one per commit, with unit tests for the pure steps. The largest, after step 6 has moved them:

| Function | Lines |
| --- | --- |
| `tqg_randomized_benchmarking` `analyze_coupler` / `plotter` / `ro_shot` | 211 / 140 / 111 |
| `motzoi_parameter` `schedule_function` | 147 |
| `cz_calibration` `plotter` / `ro_shot` / `analyze_coupler` | 143 / 97 / 86 |
| `qubit_control/spectroscopy` `schedule_function` | 130 |
| `ramsey_fringes` `schedule_function` | 129 |
| `randomized_benchmarking` `analyse_qubit` | 126 |
| `resonator_spectroscopy` `schedule_function` | 124 |
| `ro_amplitude_optimization` `ro_shot` / `analyse_qubit` / `run_initial_fitting` | 110 / 81 / 81 |
| `cz_local_phases` `analyze_coupler` / `ro_shot` | 104 / 100 |
| `purity_benchmarking` `schedule_function` | 104 |
| `base/node.py` `configure_dataset` | 100 |
| `cz_parametrization` `analyze_coupler` | 92 |
| `cz_chevron` `analyze_coupler` | 91 |
| `coupler/spectroscopy` `_find_crossing_currents` (two diverged copies, made one) | 69 / 64 |

2. **Shared functions for the remaining repeats:**
   - `get_pair_probabilities(control, target, discriminators)`, for 4 CZ analyses;
   - `fit_sine_phase(data, x)`, for 3;
   - `get_assignment_fidelities(iq_per_amplitude, states)`, for 3 copies in `ro_amplitude_optimization`;
   - `scipy.stats.median_abs_deviation`, in place of the two `reject_outliers`/`has_peak` copies;
   - `wait_between_repetitions`, for T1, T2 and T2Echo;
   - `get_phase_paths(store, couplers)`, for 2 copies.
3. **Analyses read Redis through `RedisStore`**, or better, are given the values they need. This applies to:
   - `ro_amplitude_optimization/node.py:213`;
   - `resonator_spectroscopy/analysis.py:160, 190`;
   - `ramsey_fringes/analysis.py:37`;
   - `SpiDAC.set_initial_parking_currents`.
4. **`RedisStore`** keeps its tested serialisation.
   - **Decide:** whether `prune_fields`, `save_field` and `delete_many`, used only by tests, stay as API.
   - The spec's `element` replaces the `"_" in pk` test for coupler vs qubit (`base/node.py:178`).
5. **Logging.** `ExtendedLogger` adds its handlers at import time, but a library should only create its logger.
   - Keep `status` as a level.
   - Move `add_console_handler`/`add_file_handler` behind an explicit `setup_logging(stdout_level, file_level, log_dir)`, which the entry points call.

## Step 10: tests in the right place

1. Shared helpers stay in `tergite_tuner/tests/utils/`, grouped by what they do (`redis.py`, `datasets.py`, `sessions.py`). The unused `from conftest import …` lines in 5 test files go.
2. The empty `tests/` folders (`all_xy`, `t1`, `t2`) get their golden test from step 2.2, or are deleted.
3. `tests-readme.md` folds into the testing section of `DESIGN.md`.

## Step 11: qblox-scheduler, then the dependency diet

The migration that `main` had, replayed on the refactored code.

Measured on Python 3.13, today's qblox-based `main`:

| Environment | Size | Packages |
| --- | --- | --- |
| tergite-tuner on `main` | 622 MB | 136 |
| without qblox-scheduler, qblox-instruments, qcodes | 298 MB | 45 |
| + qblox-instruments and qcodes, only what they import | 335 MB | 61 |
| qblox-scheduler alone | 615 MB | 132 |

What we lean on is the scheduler's compiler:
- the timing grid and the `ref_pt`/`rel_time` alignment (80 uses);
- clocks, the NCO, and LO/IF with mixer corrections;
- sequencer and port allocation across 15 modules;
- long-pulse splitting;
- acquisition bookkeeping;
- the gate→pulse device layer.

Its own code is 2.6 MB. The weight is in its dependency tree: plotly, pyarrow (via qcodes), dask, and IPython via `rich[jupyter]`. It has no slim extra.

qcodes cannot go while we drive the Cluster through qblox-instruments, which requires it. Qibolab's Qblox driver also imports it.

1. **Measure the quantify line first.** Record step 3.2's install size and package count on the refactored quantify line, so the migration is judged against it.
2. **Port `e280b601` onto `backend/`.**
   - The node-level changes it made (imports, the acquisition flattening, the device types, `BinMode`) all land inside `backend/`. The fitting-model copy is already in.
   - Go straight to qblox-scheduler 1.0.x, not 1.0.0b8. 1.0.0 moved `BasicTransmonElement`, `dispersive_measurement_transmon` and `rxy_drag_pulse` into qblox-applications, which is not on PyPI and lists pytest, ruff and pre-commit as runtime dependencies. Vendor those three into `backend/device.py` (BSD-3, credited in `CREDITS.md`, as the quantify fitting models were).
   - Map `AcquisitionMode` to `average_segment_repetitions`, which replaces the deprecated `bin_mode`.
   - 1.0.1 pins `pydantic<=2.13.5`: loosen our `~=2.14.1`, or wait for upstream.
   - The step 2.3 digests are re-baselined in this commit. The step 2.1 dummy run and the step 2.2 goldens must hold unchanged, and so must the step 3 testbed quality.
3. **The SPI rack on `spirack`** (23 MB, numpy and pyserial), instead of qblox-instruments' qcodes driver.
   - Add a `CurrentSource` class in `backend/spi.py` with `set_currents(currents)` (serial ramp, ±3.1 mA limit, about 30 lines of our own ramping) and `zero()`.
   - Pass `reset_currents=False`. `spirack`'s default forces the span to `range_max_bi` at 0 mA, and the span warning at `spi.py:113` is about heating.
   - The OS sniffing in `_find_and_validate_spi_port` goes: open the port and report the error.
   - On its own this saves no space while the Cluster needs qcodes. What it removes is the coupler code's dependence on qcodes' parameter API.
4. **Trim the transitive extras.**
   - uv's `override-dependencies` drops qcodes' pyarrow and dask, and IPython, from our lock and CI image.
   - This lands only once the dummy run and a testbed run pass.
   - It helps uv installs only: `pip install tergite-tuner` still pulls the full tree.
5. **Not in this plan: a scheduler-free backend.**
   - Generating Q1ASM ourselves on qblox-instruments would get to about 335 MB and 61 packages. In return we would own the compiler: timing, NCO, allocation, waveform memory and firmware compatibility.
   - Qibolab would mean rewriting all 21 measurements onto its model, and it still needs qcodes.
   - Step 5 makes either one a change to a single package. If it is wanted, an RFC prototypes resonator spectroscopy on raw Q1ASM behind `backend/` and compares its acquisitions with the scheduler's, in dummy and real mode.
6. **tergite-backend** moves to the qblox-based release once its own stack has. Until then it stays on the last quantify-based release cut from `main` before this step.

## Step 12: close out

1. Read `DESIGN.md`, `README.md` and `CONTRIBUTING.md` against the tree.
   - Update the README's custom-node example to `NodeSpec`.
   - Remove the README TODOs that are done: the dummy whole-run test and a flexible node map.
2. Run the step 2.1 dummy tune-up, the step 3 comparison and a full testbed tune-up against the merged result. Compare the seed file with one from the baseline tag, made the same day.
3. Delete `docs/prototypes/`, the step 1 lint baselines that are empty, and this file; the history keeps them.
