# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""The recorded datasets the goldens and the benchmarks analyse, and how to set each up."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import xarray as xr

from tergite_tuner.backend import CompiledSchedule, ExtendedTransmon, configure_device
from tergite_tuner.lib import run
from tergite_tuner.lib.nodes import (
    DEFAULT_NODE_SPECS,
)
from tergite_tuner.lib.spec import Fits, NodeSpec, is_failed
from tergite_tuner.storage.fs.dataset import load_dataset
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

NODES_DIR = Path(__file__).parent.parent.parent / "lib" / "nodes"
STANDARD_RUN_DIR = Path(
    get_fixture_path(
        "data", "16-51-33_standard_run_ro_amplitude_three_state_optimization-SUCCESS"
    )
)
STANDARD_REDIS = get_fixture_path("redis", "standard_redis_mock.json")
# Left out: purity benchmarking, Rabi and Rabi 12, qubit 01 and 12 spectroscopy and resonator
# spectroscopy, whose datasets predate the per-variable ``qubit`` attribute the node analysis
# splits on; the Ramsey standard run, whose device values were not recorded; and the
# anticrossing without crossings, on q16_q17, which the fixture device config lacks.


@dataclass(frozen=True)
class Result:
    """An element's analysis as the goldens record it: each stored field's value and error."""

    analysis_result: dict[str, dict[str, Any]]
    analysis_successful: bool


@dataclass(frozen=True)
class GoldenCase:
    node: NodeEnum
    dataset: str
    redis_file: str | None = None
    analysis_keywords: dict = field(default_factory=dict)


RECORDED_DATASETS = {
    "randomized_benchmarking": GoldenCase(
        NodeEnum.RANDOMIZED_BENCHMARKING,
        "characterization/randomized_benchmarking/tests/data/dataset_randomized_benchmarking.hdf5",
    ),
    "cz_calibration": GoldenCase(
        NodeEnum.CZ_CALIBRATION,
        "coupler/cz_calibration/tests/data/dataset_cz_calibration.hdf5",
    ),
    "cz_chevron": GoldenCase(
        NodeEnum.CZ_CHEVRON,
        "coupler/cz_chevron/tests/data/dataset_cz_chevron_0.hdf5",
        analysis_keywords={
            "q13_q14": {"phase_path": "via_20", "number_of_working_points": 3}
        },
    ),
    "cz_local_phases": GoldenCase(
        NodeEnum.CZ_LOCAL_PHASES,
        "coupler/cz_local_phases/tests/data/dataset_cz_local_phases.hdf5",
    ),
    "cz_parametrization_0": GoldenCase(
        NodeEnum.CZ_PARAMETRIZATION,
        "coupler/cz_parametrization/tests/data/dataset_cz_parametrization_0.hdf5",
        analysis_keywords={"q14_q15": {"phase_path": "via_20"}},
    ),
    "cz_parametrization_1": GoldenCase(
        NodeEnum.CZ_PARAMETRIZATION,
        "coupler/cz_parametrization/tests/data/dataset_cz_parametrization_1.hdf5",
        analysis_keywords={"q14_q15": {"phase_path": "via_20"}},
    ),
    "resonator_spectroscopy_vs_current": GoldenCase(
        NodeEnum.RESONATOR_SPECTROSCOPY_VS_CURRENT,
        "coupler/spectroscopy/tests/data/dataset_coupler_resonator_spectroscopy_0.hdf5",
    ),
    "coupler_anticrossing": GoldenCase(
        NodeEnum.COUPLER_ANTICROSSING,
        "coupler/spectroscopy/tests/data/dataset_coupler_spectroscopy_0.hdf5",
    ),
    "cz_rb": GoldenCase(
        NodeEnum.CZ_RB,
        "coupler/tqg_randomized_benchmarking/tests/data/dataset_cz_rb.hdf5",
    ),
    "motzoi_parameter": GoldenCase(
        NodeEnum.MOTZOI_PARAMETER,
        "qubit_control/motzoi_parameter/tests/data/dataset_motzoi_parameter.hdf5",
    ),
    "motzoi_12_parameter": GoldenCase(
        NodeEnum.MOTZOI_12_PARAMETER,
        "qubit_control/motzoi_parameter/tests/data/dataset_motzoi_12_parameter.hdf5",
    ),
    "n_rabi_oscillations": GoldenCase(
        NodeEnum.N_RABI_OSCILLATIONS,
        "qubit_control/rabi_oscillations/tests/data/dataset_n_rabi_oscillations.hdf5",
        redis_file="single-run-redis-data.json",
    ),
    "n_rabi_12_oscillations": GoldenCase(
        NodeEnum.N_RABI_12_OSCILLATIONS,
        "qubit_control/rabi_oscillations/tests/data/dataset_n_rabi_oscillations_12.hdf5",
        redis_file="single-run-redis-data.json",
    ),
    "punchout": GoldenCase(
        NodeEnum.PUNCHOUT, "readout/punchout/tests/data/dataset_punchout_0.hdf5"
    ),
    "ro_amplitude_three_state_optimization": GoldenCase(
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
        "readout/ro_amplitude_optimization/tests/data/dataset_ro_amplitude_three_state_optimization.hdf5",
    ),
    "ro_frequency_three_state_optimization": GoldenCase(
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
        "readout/ro_frequency_optimization/tests/data/dataset_ro_frequency_three_state_optimization.hdf5",
    ),
    "standard_run_resonator_spectroscopy": GoldenCase(
        NodeEnum.RESONATOR_SPECTROSCOPY,
        "20250728-165136-525-9c2f16-resonator_spectroscopy/dataset_resonator_spectroscopy.hdf5",
    ),
    "standard_run_qubit_01_spectroscopy": GoldenCase(
        NodeEnum.QUBIT_01_SPECTROSCOPY,
        "20250728-165142-378-6c2eaa-qubit_01_spectroscopy/dataset_qubit_01_spectroscopy.hdf5",
    ),
    "standard_run_rabi_oscillations": GoldenCase(
        NodeEnum.RABI_OSCILLATIONS,
        "20250728-165219-145-8960cd-rabi_oscillations/dataset_rabi_oscillations.hdf5",
        redis_file="single-run-redis-data.json",
    ),
}


DEFAULT_NODE_NAMES = sorted(node.value for node in DEFAULT_NODE_SPECS)
TEST_QUBITS = ["q00", "q01"]
TEST_COUPLERS = ["q00_q01"]


def get_compiler(
    node_name: str, session: "SessionContext"
) -> Callable[[], CompiledSchedule]:
    """Compiles a default node over its first samplespace point on q00 and q01, its device already built."""
    ExtendedTransmon.close_all()
    spec = DEFAULT_NODE_SPECS[NodeEnum(node_name)]
    device = configure_device(node_name, TEST_QUBITS, TEST_COUPLERS, session)
    sweeps = _get_first_point_sweeps(spec, session)
    return lambda: run.compile_node(spec, device, sweeps, session)


def get_dataset_builder(
    node_name: str, session: "SessionContext"
) -> Callable[[], xr.Dataset]:
    """Builds a default node's dataset from its dummy acquisitions, generated beforehand."""
    ExtendedTransmon.close_all()
    spec = DEFAULT_NODE_SPECS[NodeEnum(node_name)]
    sweeps = _get_default_sweeps(spec, session)
    raw_dataset = run.get_dummy_dataset(
        spec,
        _get_first_point_sweeps(spec, session, should_include_external=True),
        session,
    )
    couplers = TEST_COUPLERS if spec.element == "coupler" else None
    return lambda: run.get_dataset(
        raw_dataset, sweeps, TEST_QUBITS, spec.loops, couplers
    )


def get_analyser(
    golden_case: GoldenCase,
    data_path: Path,
    session: "SessionContext",
    should_save_plot: bool = False,
) -> Callable[[], dict[str, Result]]:
    """Analyses a recorded dataset, copied into ``data_path``, as the node's own analysis does."""
    spec = DEFAULT_NODE_SPECS[golden_case.node]
    node_name = golden_case.node.value
    copy_dataset(
        get_dataset_path(golden_case.dataset), data_path / f"dataset_{node_name}.hdf5"
    )

    def analyse() -> dict[str, Result]:
        dataset = load_dataset(node_name, data_path)
        if spec.element == "coupler":
            s21s = run.get_coupler_datasets(dataset, node_name)
        else:
            s21s = run.get_element_s21s(dataset)
        fits = {
            element: spec.analyse(
                s21,
                session,
                **(
                    golden_case.analysis_keywords.get(element)
                    or run.get_analysis_keywords(spec, element, session)
                ),
            )
            for element, s21 in s21s.items()
        }
        if should_save_plot:
            run.plot_elements(spec, s21s, fits, data_path, session)
        return {
            element: _to_qoi(spec, element_fits)
            for element, element_fits in fits.items()
        }

    return analyse


def get_dataset_path(dataset: str) -> Path:
    if dataset.startswith("2025"):
        return STANDARD_RUN_DIR / dataset
    return NODES_DIR / dataset


def copy_dataset(source: Path, target: Path) -> None:
    """Datasets recorded before configure_dataset set ``elements`` get it from their variables (``yq06``)."""
    with xr.open_dataset(source) as dataset:
        if "elements" not in dataset.attrs:
            dataset.attrs["elements"] = [str(var)[1:] for var in dataset.data_vars]
        dataset.load().to_netcdf(target)


def get_redis_file(golden_case: GoldenCase) -> Path:
    if golden_case.redis_file is not None:
        return get_fixture_path("redis", golden_case.redis_file)
    redis_files = sorted(
        get_dataset_path(golden_case.dataset).parent.glob("redis*.json")
    )
    return redis_files[-1] if redis_files else STANDARD_REDIS


def _get_default_sweeps(spec: NodeSpec, session: "SessionContext") -> run.Sweeps:
    return run.get_sweeps(spec, session.model_copy(update={"user_samplespace": {}}))


def _to_qoi(spec: NodeSpec, fits: Fits | None) -> Result:
    if fits is None:
        return Result({}, False)
    results = {
        spec.qois[name]: {"value": fit.value, "error": fit.error}
        for name, fit in fits.items()
        if name in spec.qois
    }
    return Result(results, not is_failed(fits))


def _get_first_point_sweeps(
    spec: NodeSpec, session: "SessionContext", should_include_external: bool = False
) -> run.Sweeps:
    """The schedule's own sweeps, plus the first point of its outer sweeps, and of its external ones if ``should_include_external``."""
    default_session = session.model_copy(update={"user_samplespace": {}})
    sweeps = _get_default_sweeps(spec, session)
    sweeps |= run.get_points(run.get_outer_sweeps(spec, default_session))[0]
    if should_include_external:
        sweeps |= run.get_points(run.get_external_sweeps(spec, default_session))[0]
    return sweeps
