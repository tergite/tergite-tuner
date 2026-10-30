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
   - A run's device values live in the session's device state: no node reads them from a database.
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

**Every commit is verified the same way:** `uv run` the step 1 linters (they also run in CI) and the style-guide test, then `uv run pytest tergite_tuner -n auto > "$LOG" 2>&1; echo "exit=$?" >> "$LOG"`. `DESIGN.md` changes in the same commit as any file it names. A commit that fixes a baselined lint or style-guide violation deletes its baseline entry, and no commit adds one.

**Every step ends with a sign-off.** Its last commit adds `docs/prototypes/<NN>-<step>.md`, a short acceptance script:
- the dummy tune-up of step 2.1;
- the reanalysis of step 2.2's recorded datasets;
- the step 3 performance comparison;
- at the end of steps 5, 6, 9 and 11, one run on a real device: resonator spectroscopy → Rabi → T1, and the coupler spectroscopy → CZ chain where couplers are wired.

Someone with access to a real device runs it and gives the go-ahead before the next step.

## Step 0: fix the bugs

The only behaviour changes in the plan. Each commit adds a test that fails before the fix, and gets a `Fixed` changelog entry. Where a decision is needed, it is marked **Decide** with a recommendation.

**Outcome.** Every item was checked against the code before it was fixed. Fixed, each with its test:
- 0.1 `7c747e2d`, 0.2 `609dacb3`, 0.3 `b2c22ac1` (the tolerance is needed: punchout's 264 s schedule builds up 2.3e-3 ns of float error, so it is scoped to the compile, not removed)
- 0.5 `2558a4b1`, 0.8 `37375889`, 0.11 `5c6c1574`, 0.12 `36cc170a`
- 0.14 `9538d6b0`, 0.15 `32f66e2c`, 0.16 `83856b2c`, 0.19 `3ca17bfa`
- 0.22 `fe0d6ec2`, 0.23 `7931a251` (several couplers now raise; benchmarking them in parallel is new work)
- 0.27 `1daf19d5`

The rest:
- **Not defects:**
  - 0.9: the CZ analyses read their keywords from `**kwargs` themselves.
  - 0.13: T1 and T2 are fitted in µs, so the seed file's unit is right.
  - 0.17: `inv_cm_opt = 0` is a placeholder for a matrix the export types as a float; the threshold branch is dead but changes nothing.
  - 0.26: the mutable defaults are only read; ruff's `B006` flags them in step 1.
- **Moved, as no failing test can show them:**
  - 0.4 and the dead threshold branch → step 4.2;
  - 0.10 → step 6.4;
  - 0.24 and `utils/cliffords.py`'s `UnboundLocalError` → step 8, which deletes both modules;
  - 0.25 → step 6.1 (`configure_dataset`) and step 9.6 (the CZ fixed-duration match). With zero-padded `qNN` names neither misfires today.
- **Left for later (decided):** 0.6–0.7. AllXY and Purity stay in the default map; nothing depends on them, so only a run that targets them reaches them, and it fails. Fixing them is step 9.7.
- **For real hardware, not a blind fix:**
  - 0.18: qubit spectroscopy's peak check has been overridden to `True` since `fca99544` (2024), and Rabi's fit uncertainty is hard-coded to 0. Re-enabling either changes which values a real run picks.
  - 0.20: the three suspects (the 1–2 pulse duration, the readout motzoi, the double correction on reanalysis).
  - 0.21: the CZ phase sign and units.
  - 0.23's analysis items: plots and the interleaving assumption.
  - Each needs a recorded dataset or a real run that shows the right answer, before its fix.

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
   - **Today's violations** are each tool's baseline, in `dev/lint/<tool>_baseline.txt`, keyed by file, rule and message rather than line. `python -m dev.lint.baseline <tool>` fails on a finding the baseline lacks and on an entry it no longer finds; `--update` rewrites it after a fix. This replaced stamping 650 `# noqa` comments into the source. Built: 650 ruff, 86 pylint and 55 vulture findings.
   - **Formatting:** **Decide** between `black` (pinned, as tergite-frontend uses it) and `ruff format`, its drop-in. Recommended: `ruff format`, so one tool covers lint and formatting.
   - **pylint**, for what ruff lacks:
     - `duplicate-code` (R0801), the copy-paste this repository is full of, with `min-similarity-lines=8`;
     - the design limits (`too-many-statements=50`, `too-many-branches`, `too-many-locals`).
     - Duplicates are keyed by the modules they span, and the size checks by the function, so editing a function does not churn the baseline.
   - **vulture**, for dead code: unused classes, functions, methods, properties and imports, outside the tests. Its unused variables are mostly pydantic fields, and ruff covers the real ones. Step 4 empties most of its baseline.
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

   Today's violations go in `tergite_tuner/tests/fixtures/styleguide_baseline.txt`. The test fails on a violation not in the baseline, and on a baseline line that no longer occurs, so that the baseline only shrinks. Built: 866 violations, 427 of them missing type hints, 175 non-verb names and 127 scheduler or Redis imports outside their package; none of host takeover after step 0. `__init__.py` re-exports and test-helper placement were left out: the package has no service facades, and no parser rule tells a shared helper from a test's own.
5. **CI runs all of it on every merge request, on `main` and on tags, in GitLab and in the GitHub mirror alike:** `uv sync --locked`, the formatter's check, `ruff check`, the pylint and vulture checks, then pytest with coverage (which includes the style-guide test). The `README.md` badge stays on the GitHub workflow.
6. **`docs/prototypes/`**, with a README saying it holds this refactor's acceptance scripts and is deleted at step 12.

## Step 2: pin behaviour with tests

Tests only. After this step, a refactor commit that changes behaviour fails a test.

1. **Every default node in dummy mode** (the README TODO). Built as `tests/test_tune_up.py`: one test per node in the default graph, each on the calibrated device in `standard_redis_mock.json` with `ignore_spec`, so a node does not depend on what the one before it wrote from random data. Analyses of random IQ points may fail, which is fine; the check is that the node measures, saves its dataset and analyses without raising. It takes about five minutes, so it is marked `slow`, and CI runs it. Four nodes fail, as strict `xfail`s that turn red when fixed:
   - qubit 01 spectroscopy: five 6 µs `SoftSquarePulse` amplitudes need 18,000 waveform samples, over the 16,384 limit. `test_precompile.py` missed it, as it does not apply the node config, whose 6 µs `node_config.example.toml` shares. For the real-hardware list.
   - AllXY and purity benchmarking (step 9.7).
   - CZ chevron: its analysis raised `IndexError` on data it could not fit (`analysis.py:217`); fixed in step 4.3, as the line was dead.

   Found besides: `NodeEnum.QUBIT_SPECTROSCOPY_VS_CURRENT` maps to the class named `coupler_anticrossing`. It saves and marks its status under that name, while `inspect_node` reads the status under the enum's, so the node never counts as calibrated. Fixed with a test in step 9.
2. **Golden reanalysis per node.**
   - For every node with a recorded dataset under `tests/data`, reanalyse it and compare the QOIs with a committed JSON, within a tolerance.
   - For nodes without one, record a dummy dataset with a fixed seed.
   - Steps 6 and 8 must keep every value.
   - Built as `tests/test_reanalysis_goldens.py`: 19 cases, each a node's own analysis class over one recorded dataset, with that dataset's Redis dump (or the single-run or standard mock) and the analysis keywords its node test passes. Goldens are flattened `element/field` values in `tests/fixtures/goldens/`; numbers compare within 1e-6 relative, the rest exactly, and `UPDATE_GOLDENS=1` rewrites them. Both CZ parametrization datasets are unsuccessful at node level, which the goldens pin as they are.
   - Left out, eight datasets: purity, Rabi, Rabi 12, qubit 01 and 12 and resonator spectroscopy, whose datasets predate the per-variable `qubit` attribute the node analysis splits on, so a real `reanalyse` of them fails too; the Ramsey standard run, whose device values were not recorded; and the anticrossing without crossings, on `q16_q17`, which the fixture device config lacks. Their single-qubit analyses keep their node tests. Re-recording them in the current format is step 6's first commit, before it changes any analysis.
3. **Golden schedules.**
   - For each node, compile its schedule against `cluster_config.example.json` with fixed device values.
   - Pin a digest of the compiled program: the sequencer programs, the waveforms and the acquisition metadata.
   - Steps 5 and 6 must keep every digest. Step 11 re-baselines them, as qblox-scheduler compiles differently.
   - Built as `tests/test_schedule_goldens.py`: a SHA-256 of each node's canonicalised `compiled_instructions` (every module's settings, sequencer programs, waveforms and acquisition metadata) on the standard mock device, with outer sweeps at their first point. Floats keep 9 significant digits, below where platforms' maths libraries differ, and waveform names, which are Python hashes seeded per process, give way to a sorted list. It is stable across processes and hash seeds, and a changed pulse phase fails it. 33 nodes; purity benchmarking cannot be built. It takes about 40 s, and `test_precompile.py`, which compiles every outer point, mostly duplicates it: step 3.5 decides whether to keep both.
4. **Public API.** `tune_device`, `run_node`, `reanalyse`, `read_result` and `generate_calib_seed_file` are each called the ways the README shows, including a custom node class through `node_cls_map`. The seed file is compared with a committed one. Built as `tests/test_public_api.py` beside the existing `test_export.py`: `tune_device` up to resonator spectroscopy, `run_node` alone and with a custom node class, and `reanalyse` of the standard run's resonator dataset, which must mark its qubits calibrated. The suite without the slow test now takes about 2 m 50 s, `test_precompile.py`'s randomized benchmarking compiles 67 s of it (step 3.5).

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
3. **On real hardware**, at the sign-offs that include a real run:
   - **time:** wall time per node, split into compile, instrument and analysis. `run_node` logs the three phases' durations at `INFO`, so a run's log is its measurement.
   - **quality:** readout assignment fidelity, single-qubit RB fidelity, T1 and T2, and CZ fidelity where couplers are wired.
   - **How quality is judged:** these drift from day to day, so they are compared with a same-day run of the baseline tag on the same qubits, not with a fixed number.
4. **`dev/perf/record.sh <dir>`** records items 1 and 2 into a directory; the baselines live in `dev/perf/baselines/`.
   - `dev/perf/compare.py dev/perf/baselines <dir>` exits 1 when any time, memory, import time or install size is more than 10% worse.
   - The 10% is a starting threshold, tuned once the first runs show how noisy each measure is.
   - CI runs `record.sh` and `compare.py` on one fixed runner. It reports without failing until the noise is known, then fails like any other check.
   - Built: baselines are per machine, `dev/perf/baselines/<machine>/`, as timings depend on it. `macos-arm64` was recorded at `215e64cb`: dummy run 285 s and 841 MB, fast tests 181 s, import 5.1 s, install 743 MB in 152 packages, and each node's measures in `nodes.json`. Two recordings on that MacBook, under a load average of 8, differed by up to 11% (import), 9% (memory) and 8% (tests), so the threshold is 15%, with noise floors of 0.05 s and 1 MB; import is the fastest of five runs, as load only ever slows one down. The GitLab job `performance` runs on `main` and tags and by hand on a merge request, keeps its recording as an artifact, and compares with `baselines/ci` once one is committed from it; until then, and while the shared runners' noise is unknown, it may fail without failing the pipeline.
   - Found: importing tergite_tuner takes 5–7 s, before anything runs; most of it is quantify-scheduler and its plotting stack. Step 11 measures it again.
5. **A faster test suite.** The suite takes about 2 minutes for 320 tests, and every commit runs it. Investigate, then make one commit per finding:
   - `pytest --durations=30` shows where the time goes. `test_precompile.py` compiles every node, and quantify-scheduler compilation is the likely cost.
   - Fixtures rebuilt per test that can be session-scoped: the session context, loaded Redis dumps, compiled devices.
   - `pytest-xdist` (`-n auto`), once the tests that share module state (`ExtendedTransmon.close_all()`, the global matplotlib backend) are isolated.
   - A `slow` marker for the compile-everything tests, so the per-commit run can skip them while CI runs all of them.
   - Record the suite's wall time in `dev/perf/baselines/` with the rest, so the refactor does not slow it down.
   - Built: compiling every outer-sweep point is marked `slow` (`f2734497`), which took the suite without slow tests from about 3 min to 71 s, and pytest-xdist runs it in parallel: 35 s for the fast tests and 1 m 45 s for everything, on 12 cores, against about 8 min serially. The run in parallel surfaced unseeded dummy data, now seeded (`3ca8cbb4`). CI runs serially: in GitLab's containers, `-n auto` made the job slower, likely because each worker pays the 5–8 s import and the container has few cores. Fixtures were not session-scoped: no fixture costs more than the tests it would share.

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
   - `BaseNode.samplespace`, always `{}` (step 0.4), and the branch of `ro_amplitude_optimization/utils.py:62-74` that cannot be taken.
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
├── __init__.py          re-exports, __all__ as strings: the scheduler's Schedule, ClockResource, gates, pulses, BinMode, and ours below
├── device.py            QuantumDevice, configure_device, save_serial_device, close_device_resources
├── transmon.py          ExtendedTransmon
├── edge.py              ExtendedCompositeSquareEdge
├── gates.py             Measure_RO1, Measure_RO_3state_Opt, and the transmon's R12, Spec and clock channels
├── pulse_factories.py   composite_soft_square_pulse
├── compile.py           compile_schedule(schedule, device, name) -> CompiledSchedule
├── execute.py           run_schedule(coordinator, compiled, timeout) -> xr.Dataset
├── hardware.py          Hardware (Cluster, InstrumentCoordinator, SPI rack), set_output_attenuations
└── spi.py               SpiDAC
```

1. **Move the device types.** `utils/types/extended_*.py` and `lib/utils/device.py` move to `backend/device.py`. Everything outside `backend/` imports from there.
2. **`compile_schedule`** replaces the two copies of `precompile` in `QubitNode` and `CouplerNode` (`base/node.py:316, 530`), which differ only in the edges.
3. **`run_schedule`** replaces `execute_schedule`:
   - It drops the fake progress thread (`schedule_execution.py:37-49`), which only sleeps for the estimated duration. Log the estimate instead, or use the coordinator's real progress if it reports any.
   - The hard-coded 3600 s wait becomes the schedule's estimated duration plus the session's `cluster_timeout`. `cluster_timeout` alone (222 s by default) is shorter than punchout's 264 s schedule.
4. **`BinMode`** comes from `tergite_tuner.backend` (22 uses). An `AcquisitionMode` enum of our own was planned, but every use passes it straight to a scheduler operation's `bin_mode`, so it would need wrapping each of those operations to translate it back; the re-export gives step 11 the same one place to change.
5. **Shared schedule building blocks**, one commit each, moving every measurement onto them:
   - `get_multiplexed_schedule(name, transmons, sweeps, add_point, repetitions)` replaces the skeleton all 10 readout and qubit-control schedules copy: root reset, per-qubit reset, the nested sweep with its `acq_index` arithmetic, measure, reset. It iterates in the order `configure_dataset` reshapes (`order="F"`), so that ordering lives in one place.
   - `prepare_state(schedule, transmon, state)`, `get_drive_clock(qubit, state)`, `get_measure_operation(state)` and `add_12_clocks(schedule, transmons)` replace the 0/1/2-state dispatch copied in 8 measurements. The ef π DRAG pulse alone is built 4 times.
   - From the 5 CZ measurements: `add_cz_clock(schedule, coupler, cz_frequency)` with `DOWNCONVERT_FREQUENCY` defined once, `add_pair_measurement(schedule, control, target, acq_index, ref_op)`, and `get_repeated_schedule(name, shot, loop_repetitions, padding)`.
6. **`Hardware`** replaces `HardwareManager`.
   - It is a class, as it owns the Cluster connection, the instrument coordinator and the SPI rack. The entry point creates it and passes it to the node.
   - `set_output_attenuations` stays a function of `(cluster, connectivity, attenuations)`.
   - The dummy Cluster's modules come from `cluster_config.hardware_description`, not from a hard-coded 15 QCM_RF + 2 QRM_RF (`tuner.py:104`).

**Built.** The device files moved whole rather than merging into one `device.py`, which keeps their history and headers and each file under pylint's 1,000 lines; the scheduler's operations are re-exported from `__init__.py` alone, since an `operations.py` repeating the list tripped pylint's duplicate-code check. No package code outside `backend/` imports quantify-scheduler or qblox-instruments; the style guide now confines `qblox_instruments` there too, and keeps `backend/` from importing `lib`, `tuner` and `export`. Two tests still import the scheduler. The shared schedule building blocks live in `lib/utils/schedules.py`, as they build our measurements from `backend`'s operations:
- `get_multiplexed_schedule` carries 8 of the 10 schedules: RO amplitude and RO frequency optimization have another shape (shots in a loop; operations in a different order from their acquisition indices).
- `get_drive_clock`, `get_measure_operation`, `prepare_state` and `add_12_clocks` carry the state dispatch of 7 measurements.
- `add_cz_clock`, `get_cz_clock_frequency`, `add_pair_measurement` and `get_repeated_schedule` carry the 5 CZ measurements; `DOWNCONVERT_FREQUENCY` was defined in four places.

The compiled-program goldens did not move. Two kinds of variation would have moved them, so they stay, as step 9.12 and 9.13. Step 5 took the package from 26,457 to 26,280 lines of Python, tests included: the nodes lost 416, and `lib/utils/schedules.py`, which replaces them, has 168.

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

**Built.** All 34 node entries are `NodeSpec`s, run by `lib/run.py`, and the class hierarchy is gone. The compiled-program and reanalysis goldens did not move. Where it departs from the plan:
- **`node_cls_map` was deleted, not deprecated** (decided with the user): custom nodes go in the session's `node_specs`. tergite-backend's test helper, which read the node classes, moves to the specs in the same change.
- **`NodeSpec` has more than the plan's fields**, each added by the first node that needed it: `get_dummy_s21`, `loops`, `plot_rows`, `save_details` (punchout's and the coupler nodes' own figures), `qubit_sweeps` (a coupler node's settings swept per qubit), `set_external`/`reset_external`, and `get_schedule_keywords`/`get_analysis_keywords` (values read from Redis).
- **Analyses return fits, but the large ones keep their classes**: the readout amplitude, benchmarking and coupler analyses sit on small `ElementAnalysis`/`CouplerAnalysis` bases that take one element's data, and still search coordinates by substring. Step 9 turns them into functions. The other analyses are functions, which find their coordinates with `get_coord_name`, and each 0-1/1-2 pair is one function.
- **A failed analysis's fits are kept, marked `failed`**, so its values and figures can be inspected; nothing failed is stored.
- **Dummy models live in each node's module**, seeded or noiseless, not in `dev/dummy.py`; dummy mode no longer sleeps between T1 and T2 repetitions.
- **`BaseMeasurement` stays**: the schedules are still the measurement classes, which `get_class_schedule` wraps.
- The alias of step 9.8 remains: `QUBIT_SPECTROSCOPY_VS_CURRENT` runs coupler anticrossing's spec, under its name.

## Step 7: configuration, the session and the device state

`SessionContext` is passed to every function. It is the run's context, as a request context is a request's: everything in a run shares it, and the run's state with it. What goes wrong is where that state lives:
- Redis holds it, and every run writes the device config over Redis first. Redis adds only what earlier runs left behind, which no config shows.
- Redis also holds state that lives only during a node: `populate_node_parameters` writes each node's config overrides before it and `revert_node_parameters` writes them back after, and 14 raw `session.redis` calls in 8 files read values mid-run (NRabi's amplitude, Ramsey's frequency, the resonator plots, the discriminator in `calculate_probabilities`, the parking currents).
- A copy of a session shares the original's touched-field log, since `model_copy` is shallow.

`config/` also imports `lib/` (`session.py:65`), to get the node defaults.

1. **pydantic-settings.**
   - `SessionContext` becomes a `BaseSettings`. It reads the `.env` file and the environment for its declared fields only.
   - Its built-in parsing replaces the hand-written casting validators: bools, enums by name, and comma-separated lists through a `NoDecode` field with one validator.
   - **Decided:** the environment wins over the `.env` file, as in pydantic-settings, Docker and twelve-factor, with a `Changed` entry.
   - **Decided:** `is_recalibration` and `ignore_spec` keep their `True` defaults; the README states them.
2. **The session is the run's context.**
   - It holds the device state and the calibration statuses, in memory (item 5).
   - A copy of a session gets its own state, not its original's.
   - `config/` no longer imports `lib/`; the entry point fills in the node defaults.
   - `cluster_config` is typed with `backend/`'s `ClusterConfig`.
3. **One loader per config file.**
   - `DeviceConfigFile.from_toml`, `NodeConfig.from_toml`, `SpiConfig.from_toml` and `ClusterConfig.from_json` share one `load_config(model, path)`.
   - The hand-written `__getitem__`/`__contains__`/`__iter__` on `NodeConfig` and `SpiConfig` go, since `RootModel` gives `.root`.
4. **Safe deletion.** `is_safe_path` (`tuner.py:498`) guards `shutil.rmtree(session.data_dir)` with a list of five system paths. Replace it with deleting only what this run created: its own subfolder.
5. **No store: the device state in memory.** A run starts from what its caller gives it, never from what an earlier run left in a database.
   - A session's device state starts from the device config, with an earlier calibration's results over it when the caller gives them: a `CalibrationResults`, or the results file a run wrote, as a session field. A periodic recalibration passes its latest calibration this way.
   - A node is in spec when those results mark it calibrated, as the `cs` hashes do today. **Later:** the results' values, such as their age or fit errors, could decide whether a node needs recalibrating.
   - A node's config overrides apply to its own copy of the state, so nothing is reverted.
   - Measurements and analyses read the state. After each node, its fits and statuses go into it; a node that fails changes nothing.
   - Each run writes the state's results into its folder, as `CalibrationResults` JSON.
   - `read_result(session)` reads the session's state; `session_only` keeps the fields this session's nodes set. `generate_calib_seed_file` takes a session or a results file.
   - Going: the `redis` and `fakeredis` dependencies, `redis_url`, `storage/redis/`, the `Store` interface, the touched-field log, `populate_*`/`revert_node_parameters`, the raw reads above and the perf suite's store round-trip count. Each with a `Changed` entry.
   - **tergite-backend**, in a worktree on a branch of its own: it passes its latest calibration to the session, reads the results from the session, and no longer needs Redis for the tuner. Its test helper writes into the session's state instead of the `cs:` hashes.

**Built.** Items 1–5 are in, with the session holding the device state and no store. Where it departs from the plan:
- **A `Store` behind a URL was built, then removed** when the plan dropped the store; it stays in the history (`42de6fa0`), as does the perf suite's round-trip count it was measured with.
- **A recalibration keeps each node's config overrides** for the nodes after it, as Redis did; otherwise they sit over the state only while the node runs.
- **`cluster_config` kept its type**, quantify-scheduler's compilation config from `backend/`, which tergite-backend passes as is; a subclass type would reject it.
- **Options given with a session are set over its values** (`SessionContext.update`), a step 0 bug: they were dropped, so tergite-backend's one-qubit-at-a-time nodes ran every qubit.
- **The tests' Redis dumps became state JSON**, the records a `DeviceState` takes as is.
- `reanalyse` no longer takes `keep_data_files`: it writes nothing to delete.

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

**Built.** One group, in `lib/utils/cliffords/`, for all three nodes; no compiled program moved. Where it departs from the plan:
- **A package, not one module**: the group, its Pauli transfer matrices and its sequence helpers, about 900 lines together.
- **Single-qubit RB keeps its sequences**: the old table is the group's Epstein decomposition element for element, and `randomized_benchmarking_sequence` takes the qubit's generator as its seed, so each length keeps drawing from one stream.
- **Only purity's `ExpDecayModel` was a copy**, merged into `analysis_models`' with its own first guesses passed in; `fitting_models`' is T1 and T2's decay-time model and stays. The `mitigate` copies were already gone.
- The two-qubit table built in memory raised the dummy tune-up's peak from 610 to 719 MB, under the baseline's 841 MB.

## Step 9: long functions and the rest

1. ~~**Long functions become compositions**, one per commit, with unit tests for the pure steps~~: no function has 60 lines or more. The largest, after step 6 had moved them:

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

2. ~~Shared functions for the remaining repeats~~:
   - `fit_sine_phase(model, data, x, plot_x)`, for CZ local phases and CZ calibration, each keeping its own model;
   - `classify_shots(iq, states, lda)`, for the two- and three-state readout amplitude analyses;
   - already shared after step 6: the waits between T1, T2 and T2 echo repetitions (`get_waits_between_points`) and `get_phase_path`; the `reject_outliers`/`has_peak` copies were gone;
   - not shared: the four CZ analyses' `calculate_probabilities` calls, two lines each that each analysis then uses differently.
3. ~~Analyses read Redis through `RedisStore`~~: step 7.5 gives them the session's device state, and removes `RedisStore`.
4. ~~The spec's `element` replaces the `"_" in pk` test for coupler vs qubit~~: it went with `base/node.py` in step 6.
5. ~~Logging~~: the handlers are behind `setup_logging(stdout_level, file_level, log_dir)`, which the entry points call; `status` stays a level.
6. ~~Match couplers by name~~: CZ calibration checks `coupler in session.fixed_duration_couplers`.
7. ~~Fix AllXY and Purity~~: purity benchmarking runs on the sweep layout its measurement and analysis share, and AllXY has an analysis; neither has a recorded dataset yet.
8. ~~One name per node~~: qubit spectroscopy vs current has the same measurement under its own name, and a test checks every default spec is named for its node.
9. ~~Qubit 01 spectroscopy's waveform memory~~: the node configs give it 3 µs pulses, which fit.
10. ~~The CZ chevron analysis raised on data it could not fit~~: its `IndexError` came from a dead `np.linspace` over the working frequencies, removed in step 4.3.
11. ~~The T2 and two-qubit RB analyses raised `ZeroDivisionError`~~: T2 fails its fits when a repetition guesses a 0 Hz oscillation, and CZ RB when a standard decay fits to zero.
12. ~~One reset alignment~~: each schedule keeps the alignment its compiled program has had since before the refactor; making them one would change programs that run as they are.
13. ~~Resonator spectroscopy prepares |2> without the ef motzoi~~: it prepares |2> with `prepare_state`, as the readout optimizations do.

**Built.** Every function over 60 lines was split, one commit each, and no compiled program moved. Where it departs from the plan:
- **The crossing finders became the anticrossing's**: the resonator-vs-current copy's grouping moved the anticrossing's crossings, while the anticrossing's left the other node's unchanged.
- **The three schedules built point by point** (resonator and qubit spectroscopy, Ramsey) keep `get_multiplexed_schedule`'s callback, now a method bound with `functools.partial` instead of a nested function.
- **Dead code went with the splits**: readout amplitude's per-amplitude shot arrays, which nothing read, and CZ calibration's unused plot flags.
- **Two bugs got their own commits**: CZ chevron floored 100 ns to 96 ns, and the CZ pulse shifted a qubit's clock by NaN for an uncalibrated phase correction.
- Docstrings that the splits showed wrong were corrected: the dependency order's, and the child phase correction's, which named the parent.

## Step 10: tests in the right place

1. ~~Shared helpers stay in `tergite_tuner/tests/utils/`, grouped by what they do~~: `datasets.py`, `fixtures.py`, `goldens.py`, `pytest.py`, `runs.py` and `state.py`; Redis went in step 7, and no test imports from `conftest`.
2. ~~The empty `tests/` folders (`all_xy`, `t1`, `t2`) get their golden test from step 2.2, or are deleted~~: AllXY and T2 have tests, and T1's folder is gone, as T2's decay test fits T1's dummy decay with the analysis they share.
3. ~~`tests-readme.md` folds into the testing section of `DESIGN.md`~~.

**Built.** The earlier steps had done most of it: only T1's folder and the readme were left.

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
   - The step 2.3 digests are re-baselined in this commit. The step 2.1 dummy run and the step 2.2 goldens must hold unchanged, and so must the step 3 quality on real hardware.
3. **The SPI rack on `spirack`** (23 MB, numpy and pyserial), instead of qblox-instruments' qcodes driver.
   - Add a `CurrentSource` class in `backend/spi.py` with `set_currents(currents)` (serial ramp, ±3.1 mA limit, about 30 lines of our own ramping) and `zero()`.
   - Pass `reset_currents=False`. `spirack`'s default forces the span to `range_max_bi` at 0 mA, and the span warning at `spi.py:113` is about heating.
   - The OS sniffing in `_find_and_validate_spi_port` goes: open the port and report the error.
   - On its own this saves no space while the Cluster needs qcodes. What it removes is the coupler code's dependence on qcodes' parameter API.
4. **Trim the transitive extras.**
   - Measured on the quantify line (step 3): of the 743 MB install, about 230 MB is never imported: PyQt5 and pyqtgraph (138 MB, via quantify-core), plotly (39 MB, via quantify-scheduler), and `ipykernel` with jedi and debugpy (43 MB, via qcodes). pyarrow (123 MB) stays, as the pandas/xarray chain imports it. Drop the rest with impossible markers, e.g. `override-dependencies = ["pyqt5; python_version < '0'", ...]`, and add the same overrides to tergite-backend, which shares the environment and also installs with uv. Shipping empty stub modules instead was considered and rejected: pip still installs the real packages that quantify declares, and stand-in packages under those names would break anything else in the environment that uses them.
   - Import time is a separate problem: of its 5–8 s, scipy takes 2.0 s, pandas 1.0 s and scikit-learn 0.6 s, which the tuner uses itself; quantify-scheduler's own code takes 0.24 s, and nothing above is imported. Lazy imports of the analysis stack in the nodes that need it would help, not trimming.
   - uv's `override-dependencies` drops what is never imported from our lock and CI image (below); pyarrow stays.
   - This lands only once the dummy run and a real run pass.
   - It helps uv installs only: `pip install tergite-tuner` still pulls the full tree.
5. **Not in this plan: a scheduler-free backend.**
   - Generating Q1ASM ourselves on qblox-instruments would get to about 335 MB and 61 packages. In return we would own the compiler: timing, NCO, allocation, waveform memory and firmware compatibility.
   - Qibolab would mean rewriting all 21 measurements onto its model, and it still needs qcodes.
   - Step 5 makes either one a change to a single package. If it is wanted, an RFC prototypes resonator spectroscopy on raw Q1ASM behind `backend/` and compares its acquisitions with the scheduler's, in dummy and real mode.
6. **tergite-backend** moves to the qblox-based release once its own stack has. Until then it stays on the last quantify-based release cut from `main` before this step.

## Step 12: close out

1. ~~Read `DESIGN.md`, `README.md` and `CONTRIBUTING.md` against the tree~~: the custom-node example was already a `NodeSpec`; the done TODOs, the Redis mentions and a `run_node` example without its node are gone, and the examples share one session, so each node starts from the last one's results.
2. Run the step 2.1 dummy tune-up, the step 3 comparison and a full tune-up on real hardware against the merged result. Compare the seed file with one from the baseline tag, made the same day.
3. Delete `docs/prototypes/`, the step 1 lint baselines that are empty, and this file; the history keeps them.
