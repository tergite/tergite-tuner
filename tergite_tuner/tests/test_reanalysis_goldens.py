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
"""Pins each node's analysis of a recorded dataset to the QOIs it gave when this test was added.

A change that moves a value on purpose rewrites its golden with
``UPDATE_GOLDENS=1 pytest tergite_tuner/tests/test_reanalysis_goldens.py``,
and the commit says why.
"""

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import xarray as xr

from tergite_tuner.lib.nodes import DEFAULT_NODE_CLS_MAP
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.redis import loaded_redis
from tergite_tuner.utils.types.node_enum import NodeEnum

NODES_DIR = Path(__file__).parent.parent / "lib" / "nodes"
STANDARD_RUN_DIR = Path(
    get_fixture_path(
        "data", "16-51-33_standard_run_ro_amplitude_three_state_optimization-SUCCESS"
    )
)
GOLDENS_DIR = Path(get_fixture_path("goldens"))
STANDARD_REDIS = get_fixture_path("redis", "standard_redis_mock.json")
# relative tolerance across platforms' floating point and fitting libraries
TOLERANCE = 1e-6
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


CASES = {
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


@pytest.mark.parametrize("case", CASES)
def test_reanalysis_gives_the_golden_qois(
    case, redis_connection, session_context, tmp_path
):
    golden_case = CASES[case]
    node_cls = DEFAULT_NODE_CLS_MAP[golden_case.node]
    _copy_dataset(
        _get_dataset_path(golden_case.dataset),
        tmp_path / f"dataset_{node_cls.name}.hdf5",
    )

    with loaded_redis(redis_connection, _get_redis_file(golden_case)):
        analysis = node_cls.analysis_cls(
            name=node_cls.name,
            redis_fields=_get_qois(node_cls),
            session=session_context,
            **golden_case.analysis_keywords,
        )
        qois = analysis.analyze_node(tmp_path, save_plot=False)

    values = _get_flat_values(qois)
    golden_path = GOLDENS_DIR / f"{case}.json"
    if os.environ.get("UPDATE_GOLDENS"):
        golden_path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n")
    golden = json.loads(golden_path.read_text())
    numbers = {key for key, value in golden.items() if _is_number(value)}
    assert {k: v for k, v in values.items() if k not in numbers} == {
        k: v for k, v in golden.items() if k not in numbers
    }
    assert {k: values.get(k) for k in numbers} == pytest.approx(
        {k: golden[k] for k in numbers}, rel=TOLERANCE
    )


def _get_dataset_path(dataset: str) -> Path:
    if dataset.startswith("2025"):
        return STANDARD_RUN_DIR / dataset
    return NODES_DIR / dataset


def _copy_dataset(source: Path, target: Path) -> None:
    """Datasets recorded before configure_dataset set ``elements`` get it from their variables (``yq06``)."""
    with xr.open_dataset(source) as dataset:
        if "elements" not in dataset.attrs:
            dataset.attrs["elements"] = [str(var)[1:] for var in dataset.data_vars]
        dataset.load().to_netcdf(target)


def _get_redis_file(golden_case: GoldenCase) -> Path:
    if golden_case.redis_file is not None:
        return get_fixture_path("redis", golden_case.redis_file)
    redis_files = sorted(
        _get_dataset_path(golden_case.dataset).parent.glob("redis*.json")
    )
    return redis_files[-1] if redis_files else STANDARD_REDIS


def _get_qois(node_cls: type) -> list[str]:
    return (
        getattr(node_cls, "qubit_qois", None)
        or getattr(node_cls, "coupler_qois", None)
        or []
    )


def _get_flat_values(qois: dict) -> dict:
    """``{"q06/rxy:amp180": 0.6, "q06/is_successful": True, ...}``, as approx compares flat dicts only."""
    values = {}
    for element, qoi in sorted(qois.items()):
        values[f"{element}/is_successful"] = qoi.analysis_successful
        for name, result in qoi.analysis_result.items():
            value = result["value"]
            if hasattr(value, "tolist"):
                value = value.tolist()
            if isinstance(value, list):
                for index, item in enumerate(value):
                    values[f"{element}/{name}/{index}"] = _to_json(item)
            else:
                values[f"{element}/{name}"] = _to_json(value)
    return values


def _to_json(value):
    if hasattr(value, "item"):
        value = value.item()
    return None if isinstance(value, float) and math.isnan(value) else value


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
