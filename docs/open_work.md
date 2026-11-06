# Open work

What is known to be unfinished. For maintainers.

## To do

- [ ] Update export to BCC to be more generic to allow any BaseModel class to be output
- [ ] Give `tergite_tuner/backend/`, the node `measurement.py` modules, `config/session.py`, `config/types/cluster.py`,
  `lib/run.py` and `lib/utils/schedules.py` Google-style docstrings once `feature/qblox-scheduler`, which rewrites them, is merged

## Not yet verified on a real device

These need a real Cluster, with `CLUSTER_MODE='real'`; a dummy run cannot show them.

- [ ] Run resonator spectroscopy, also at |2>; bring-up, 01 and 12 qubit spectroscopy with the example node config; Rabi, motzoi and the readout optimizations; T1 and T2. Each should complete, and its values match a run of 2026.06.0.
- [ ] Run coupler anticrossing, resonator spectroscopy vs current, then CZ chevron, calibration, local phases and RB on one coupler; their crossings and fidelities should match an earlier run. CZ parametrization on two couplers excites each coupler's qubits only in its own shots, and CZ RB on two couplers raises `ValueError`.
- [ ] Run punchout, the longest schedule at about 264 s, and a CZ calibration with its real `loop_repetitions`: neither raises a timeout, and punchout leaves quantify-scheduler's `GRID_TIME_TOLERANCE_TIME` at `0.0011`.
- [ ] Run a tune-up through CZ calibration with `save_plot`, then a second session with `calibration` set to the first's `results.json`: its nodes start from the first run's values, and the plots look as before.
- [ ] Run single-qubit RB, interleaved with X90, purity benchmarking and AllXY: each stores its values, and RB's fidelity matches an earlier run.
- [ ] Check the fixes a dummy run cannot: `CLUSTER_IP` with no Cluster raises `ClusterUnreachableError` and the Python session survives; `save_plot` over SSH without a display saves its plots; Rabi and three-state readout amplitude optimization give each qubit its own pulse duration; a `spec_duration` of 8 µs compiles; resonator spectroscopy 1 stores a quality factor of about 10⁴ as `Ql_1`.
- [ ] Decide, from recorded data: re-enabling qubit spectroscopy's peak check, which has passed every peak since 2024, and Rabi's fit uncertainty, fixed at 0; the 1-2 pulse duration, the readout motzoi and reanalysis's double correction; the CZ phase's sign and units, which lose the sign today.
- [ ] Run tergite-backend's recalibration against this build: its one-qubit-at-a-time nodes measure one qubit each.
- [ ] Once a real run passes, drop what is installed but never imported, with `override-dependencies` in uv: PyQt5 and pyqtgraph through quantify-core, plotly through quantify-scheduler, and `ipykernel` with jedi and debugpy through qcodes, about 230 MB of the install. Check the imports of a real run first; tergite-backend, which shares the environment, takes the same overrides.
- [ ] Compare a full tune-up's seed file with one from 2026.06.0, made the same day.
