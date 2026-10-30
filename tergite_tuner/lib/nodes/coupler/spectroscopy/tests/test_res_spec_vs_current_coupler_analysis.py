# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import re

import matplotlib
import pytest
import xarray as xr
from matplotlib import pyplot as plt

from tergite_tuner.lib.nodes.coupler.spectroscopy.analysis import (
    ResonatorSpectroscopyVsCurrentCouplerAnalysis,
)
from tergite_tuner.tests.utils.datasets import get_coupler_dataset

RES_COUPLER_QOIS = [
    "control_resonator_crossing_points",
    "target_resonator_crossing_points",
]
_COUPLER_CROSSINGS = [
    # (coupler, q1_crossings, q2_crossings)
    (
        "q06_q07",
        [-0.000425, 0.000675],
        [-0.00025, 0.000525],
    ),
    (
        "q08_q09",
        [-0.0008, 0.00075],
        [],
    ),
    ("q12_q13", [-0.000425, 0.000825], []),
    ("q14_q15", [], [-0.00025, 0.000925]),
]


@pytest.mark.parametrize("coupler, q1_crossings, q2_crossings", _COUPLER_CROSSINGS)
def test_get_crossings(
    session_context,
    redis_connection,
    node_data_dir,
    coupler,
    q1_crossings,
    q2_crossings,
):
    dataset_path = node_data_dir / "dataset_coupler_resonator_spectroscopy_0.hdf5"
    q1, q2 = coupler.split("_")
    with xr.open_dataset(dataset_path) as ds:
        ds = xr.merge(ds[var] for var in [f"y{q1}", f"y{q2}"])
        ds.attrs["coupler"] = coupler
        a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
            get_coupler_dataset(ds, coupler, "name"), session_context
        )
        qoi = a.analyse()

        q1_crossings = _get_crossing_for_qubit(qoi, q1)
        q2_crossings = _get_crossing_for_qubit(qoi, q2)
        assert q1_crossings == pytest.approx(q1_crossings, abs=1e-6)
        assert q2_crossings == pytest.approx(q2_crossings, abs=1e-6)


def test_coupler_plot_is_created(node_data_dir, session_context, redis_connection):
    matplotlib.use("Agg")
    dataset_path = node_data_dir / "dataset_coupler_resonator_spectroscopy_0.hdf5"
    with xr.open_dataset(dataset_path) as ds:
        coupler = "q06_q07"
        ds = xr.merge(ds[var] for var in ["yq06", "yq07"])
        ds.attrs["coupler"] = coupler
        a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
            get_coupler_dataset(ds, coupler, "name"), session_context
        )
        a.analyse()

        figure_path = node_data_dir / "name.png"
        figure_path.unlink(missing_ok=True)

        figures_dictionary = {}
        a.plotter(figures_dictionary)
        fig_list = figures_dictionary[coupler]
        fig = fig_list[0]
        fig.savefig(figure_path)
        plt.close()

        assert figure_path.exists()
        from PIL import Image

        with Image.open(figure_path) as img:
            assert img.format == "PNG", "File should be a PNG image"


def _get_crossing_for_qubit(qoi: dict, qubit: str = "q06"):
    results = qoi
    qubit_number = int(re.sub("[^0-9]", "", qubit))
    if qubit_number % 2 == 0:
        crossing_points = "control_resonator_crossing_points"
    elif qubit_number % 2 == 1:
        crossing_points = "target_resonator_crossing_points"
    else:
        raise ValueError("Invalid qubit number")
    crossings = results[crossing_points].value
    return crossings
