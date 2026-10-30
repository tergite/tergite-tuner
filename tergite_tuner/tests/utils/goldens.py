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
from typing import TYPE_CHECKING

import xarray as xr

from tergite_tuner.backend import CompiledSchedule, ExtendedTransmon, configure_device
from tergite_tuner.lib import run
from tergite_tuner.lib.nodes import (
    DEFAULT_NODE_CLS_MAP,
    DEFAULT_NODE_NAME_CLS_MAP,
    DEFAULT_NODE_SPECS,
)
from tergite_tuner.lib.nodes.schedule_node import OuterScheduleNode
from tergite_tuner.lib.spec import Fits, NodeSpec
from tergite_tuner.storage.fs.dataset import load_dataset
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.utils.measurement import reduce_samplespace
from tergite_tuner.utils.types.node_enum import NodeEnum
from tergite_tuner.utils.types.qoi import QOI

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


DEFAULT_NODE_NAMES = sorted(
    {*DEFAULT_NODE_NAME_CLS_MAP, *(node.value for node in DEFAULT_NODE_SPECS)}
)
TEST_QUBITS = ["q00", "q01"]
TEST_COUPLERS = ["q00_q01"]


def get_compiler(
    node_name: str, session: "SessionContext"
) -> Callable[[], CompiledSchedule]:
    """Compiles a default node over its first samplespace point on q00 and q01, its device already built."""
    ExtendedTransmon.close_all()
    spec = DEFAULT_NODE_SPECS.get(NodeEnum(node_name))
    if spec is None:
        node = _get_node(node_name, session)
        samplespace = get_first_samplespace(node)
        return lambda: node.precompile(samplespace)
    device = configure_device(node_name, TEST_QUBITS, TEST_COUPLERS, session)
    sweeps = _get_default_sweeps(spec, session)
    return lambda: run.compile_node(spec, device, sweeps)


def get_dataset_builder(
    node_name: str, session: "SessionContext"
) -> Callable[[], xr.Dataset]:
    """Builds a default node's dataset from its dummy acquisitions, generated beforehand."""
    ExtendedTransmon.close_all()
    spec = DEFAULT_NODE_SPECS.get(NodeEnum(node_name))
    if spec is None:
        node = _get_node(node_name, session)
        node.reduced_external_samplespace = get_first_external_point(node)
        raw_dataset = node.generate_dummy_dataset()
        return lambda: node.configure_dataset(raw_dataset)
    sweeps = _get_default_sweeps(spec, session)
    raw_dataset = run.get_dummy_dataset(spec, sweeps, session)
    return lambda: run.get_dataset(raw_dataset, sweeps, TEST_QUBITS, spec.loops)


def get_analyser(
    golden_case: GoldenCase,
    data_path: Path,
    session: "SessionContext",
    should_save_plot: bool = False,
) -> Callable[[], dict[str, QOI]]:
    """Analyses a recorded dataset, copied into ``data_path``, as the node's own analysis does."""
    spec = DEFAULT_NODE_SPECS.get(golden_case.node)
    node_name = golden_case.node.value
    copy_dataset(
        get_dataset_path(golden_case.dataset), data_path / f"dataset_{node_name}.hdf5"
    )
    if spec is None:
        node_cls = DEFAULT_NODE_CLS_MAP[golden_case.node]
        return lambda: node_cls.analysis_cls(
            name=node_name,
            redis_fields=get_qois(node_cls),
            session=session,
            **golden_case.analysis_keywords,
        ).analyze_node(data_path, save_plot=should_save_plot)

    def analyse() -> dict[str, QOI]:
        s21s = run.get_element_s21s(load_dataset(node_name, data_path))
        fits = run.get_fits(spec, s21s, session)
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


def get_qois(node_cls: type) -> list[str]:
    return (
        getattr(node_cls, "qubit_qois", None)
        or getattr(node_cls, "coupler_qois", None)
        or []
    )


def get_first_samplespace(node) -> dict:
    """The schedule's own sweeps, plus the first point of an outer sweep, which needs one compile each."""
    if not issubclass(node.measurement_type_cls, OuterScheduleNode):
        return node.schedule_samplespace
    first_point = (0,) * len(node.outer_schedule_samplespace)
    return node.schedule_samplespace | reduce_samplespace(
        first_point, node.outer_schedule_samplespace
    )


def get_first_external_point(node) -> dict:
    """The first point of an external sweep, as the measurement loop sets it before each run."""
    first_point = (0,) * len(node.external_samplespace)
    return reduce_samplespace(first_point, node.external_samplespace)


def _get_node(node_name: str, session: "SessionContext"):
    return DEFAULT_NODE_NAME_CLS_MAP[node_name](
        all_qubits=TEST_QUBITS, couplers=TEST_COUPLERS, session=session
    )


def _get_default_sweeps(spec: NodeSpec, session: "SessionContext") -> run.Sweeps:
    return run.get_sweeps(spec, session.model_copy(update={"user_samplespace": {}}))


def _to_qoi(spec: NodeSpec, fits: Fits | None) -> QOI:
    if fits is None:
        return QOI({}, False)
    results = {
        spec.qois[name]: {"value": fit.value, "error": fit.error}
        for name, fit in fits.items()
        if name in spec.qois
    }
    return QOI(results, True)
