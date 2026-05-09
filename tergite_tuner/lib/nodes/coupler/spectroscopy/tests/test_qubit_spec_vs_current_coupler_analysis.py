# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import os
import re
from pathlib import Path

import matplotlib
import pytest
import xarray as xr
from matplotlib import pyplot as plt

from tergite_tuner.lib.base.analysis import BaseAnalysis, BaseCouplerAnalysis
from tergite_tuner.lib.base.node import qoi_to_redis_record
from tergite_tuner.lib.nodes.coupler.spectroscopy.analysis import (
    CouplerAnticrossingAnalysis,
    ResonatorSpectroscopyVsCurrentCouplerAnalysis,
)
from tergite_tuner.utils.dto.qoi import QOI

_RES_COUPLER_QOIS = [
    "control_resonator_crossing_points",
    "target_resonator_crossing_points",
]
_QUBIT_COUPLER_QOIS = ["control_qubit_crossing_points", "target_qubit_crossing_points"]
_COUPLER_SPEC_DATASET_FILE = "dataset_coupler_spectroscopy_0.hdf5"
_RES_SPEC_DATASET_FILE = "dataset_coupler_resonator_spectroscopy_0.hdf5"
_NO_CROSSINGS_DATASET_FILE = "dataset_qubit_spectroscopy_vs_current_no_crossings.hdf5"

_COUPLER_CROSSINGS = [
    # (coupler, q1_crossings, q2_crossings)
    (
        "q06_q07",
        [-0.001925, -0.0011, 0.001375, 0.0022],
        [-0.002025, -0.001, 0.0012875, 0.0023],
    ),
    (
        "q08_q09",
        [-0.00215, -0.00135, 0.001325, 0.002125],
        [-0.0023625, -0.0011375, 0.0011, 0.0022875],
    ),
    ("q12_q13", [-0.00190, -0.00105, 0.001475, 0.002375], [-0.0020875, 0.001375]),
    ("q14_q15", [-0.00185, -0.000825, 0.00155], [-0.0018, -0.00095, 0.00165]),
]


def test_coupler_anticrossing_analysis_create(session_context):
    a = CouplerAnticrossingAnalysis("name", ["redis_field"], session=session_context)
    assert isinstance(a, CouplerAnticrossingAnalysis)
    assert isinstance(a, BaseCouplerAnalysis)
    assert isinstance(a, BaseAnalysis)


@pytest.mark.parametrize("coupler, q1_crossings, q2_crossings", _COUPLER_CROSSINGS)
def test_get_crossings(
    coupler, q1_crossings, q2_crossings, session_context, node_data_dir
):
    ds_qu, ds_res = _get_dataset_for_coupler(coupler, node_data_dir)
    a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
        "resonator_spectroscopy_vs_current",
        _RES_COUPLER_QOIS,
        session_context,
    )
    q1, q2 = coupler.split("_")
    session_context.redis.hset(f"couplers:{coupler}", "control_qubit", q1)
    session_context.redis.hset(f"couplers:{coupler}", "target_qubit", q2)
    qoi = a.process_coupler(ds_res, coupler)
    record = qoi_to_redis_record(qoi, redis_fields=_RES_COUPLER_QOIS)
    session_context.redis_store.save_many(
        {
            "couplers": {coupler: record},
            "cs": {coupler: {"resonator_spectroscopy_vs_current": "calibrated"}},
        }
    )

    b = CouplerAnticrossingAnalysis("name", _QUBIT_COUPLER_QOIS, session_context)
    qoi = b.process_coupler(ds_qu, coupler)

    q1_actual_crossings = _get_crossing_for_qubit(qoi, q1)
    q2_actual_crossings = _get_crossing_for_qubit(qoi, q2)

    assert q1_actual_crossings == pytest.approx(q1_crossings, abs=1e-6)
    assert q2_actual_crossings == pytest.approx(q2_crossings, abs=1e-6)


def test_coupler_plot_is_created(session_context, node_data_dir):
    matplotlib.use("Agg")
    coupler = "q06_q07"
    ds_qu, ds_res = _get_dataset_for_coupler(coupler, node_data_dir)
    name = "resonator_spectroscopy_vs_current"
    a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
        name,
        _RES_COUPLER_QOIS,
        session_context,
    )
    qoi = a.process_coupler(ds_res, coupler)
    redis_value = qoi_to_redis_record(qoi, redis_fields=_RES_COUPLER_QOIS)
    session_context.redis_store.save_many(
        {
            "couplers": {coupler: {name: redis_value}},
            "cs": {coupler: {name: "calibrated"}},
        }
    )

    b = CouplerAnticrossingAnalysis(
        "qubit_spectroscopy_vs_current",
        _QUBIT_COUPLER_QOIS,
        session_context,
    )
    qoi = b.process_coupler(ds_qu, coupler)

    figure_path = node_data_dir / "qubit_spectroscopy_vs_current.png"
    figure_path.unlink(missing_ok=True)

    figures_dictionary = {}
    b.plotter(figures_dictionary)
    fig_list = figures_dictionary[coupler]
    fig = fig_list[0]
    fig.savefig(figure_path)
    plt.close()

    assert os.path.exists(figure_path)
    from PIL import Image

    with Image.open(figure_path) as img:
        assert img.format == "PNG", "File should be a PNG image"


@pytest.mark.skip()
def test_no_crossings_for_q16_q17(session_context, node_data_dir):
    dataset_path = node_data_dir / _NO_CROSSINGS_DATASET_FILE
    with xr.open_dataset(dataset_path) as ds:
        coupler = "q16_q17"
        ds = xr.merge(ds[var] for var in ["yq16", "yq17"])
        ds.attrs["coupler"] = coupler
        a = CouplerAnticrossingAnalysis("name", _QUBIT_COUPLER_QOIS, session_context)
        qoi = a.process_coupler(ds, coupler)

        q16_crossings = _get_crossing_for_qubit(qoi, "q16")
        q17_crossings = _get_crossing_for_qubit(qoi, "q17")
        assert q16_crossings == pytest.approx([0.000975], abs=1e-6)
        assert len(q17_crossings) == 0


def _get_crossing_for_qubit(qoi: QOI, qubit: str = "q06"):
    results = qoi.analysis_result
    qubit_number = int(re.sub("[^0-9]", "", qubit))
    if qubit_number % 2 == 0:
        crossing_points = "control_qubit_crossing_points"
    elif qubit_number % 2 == 1:
        crossing_points = "target_qubit_crossing_points"
    else:
        raise ValueError("Invalid qubit number")
    crossings = results[crossing_points]["value"]
    return crossings


def _get_dataset_for_coupler(coupler, node_data_dir: Path):
    qubits = coupler.split("_")
    dataset_path = node_data_dir / _COUPLER_SPEC_DATASET_FILE
    ds_qu = xr.open_dataset(dataset_path)
    ds_qu = xr.merge(ds_qu[var] for var in [f"y{qubits[0]}", f"y{qubits[1]}"])
    ds_qu.attrs["coupler"] = coupler

    dataset_path = node_data_dir / _RES_SPEC_DATASET_FILE
    ds_res = xr.open_dataset(dataset_path)
    ds_res = xr.merge(ds_res[var] for var in [f"y{qubits[0]}", f"y{qubits[1]}"])
    ds_res.attrs["coupler"] = coupler
    return ds_qu, ds_res
