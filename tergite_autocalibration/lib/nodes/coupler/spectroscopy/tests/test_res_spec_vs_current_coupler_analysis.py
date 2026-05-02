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
from pathlib import Path

import pytest
import xarray as xr
from numpy import ndarray

from tergite_autocalibration.lib.base.analysis import BaseAnalysis, BaseCouplerAnalysis
from tergite_autocalibration.lib.nodes.coupler.spectroscopy.analysis import (
    ResonatorSpectroscopyVsCurrentCouplerAnalysis,
)
from tergite_autocalibration.utils.dto.qoi import QOI


def test_CanCreate():
    a = ResonatorSpectroscopyVsCurrentCouplerAnalysis("name", ["redis_field"])
    assert isinstance(a, ResonatorSpectroscopyVsCurrentCouplerAnalysis)
    assert isinstance(a, BaseCouplerAnalysis)
    assert isinstance(a, BaseAnalysis)


def getCrossingForQubit(qoi: QOI, qubit: str = "q06"):
    results = qoi.analysis_result
    qubit_number = int(re.sub("[^0-9]", "", qubit))
    if qubit_number % 2 == 0:
        crossing_points = "control_resonator_crossing_points"
    elif qubit_number % 2 == 1:
        crossing_points = "target_resonator_crossing_points"
    else:
        raise ValueError("Invalid qubit number")
    crossings = results[crossing_points]["value"]
    return crossings


@pytest.fixture(autouse=False)
def setup_q06_q07_data():
    dataset_path = (
        Path(__file__).parent / "data" / "dataset_coupler_resonator_spectroscopy_0.hdf5"
    )
    ds = xr.open_dataset(dataset_path)
    coupler = "q06_q07"
    ds = xr.merge(ds[var] for var in ["yq06", "yq07"])
    ds.attrs["coupler"] = coupler
    return ds, coupler


res_coupler_qois = [
    "control_resonator_crossing_points",
    "target_resonator_crossing_points",
]


def test_get_crossings_for_q06_q07(
    setup_q06_q07_data: tuple[xr.Dataset, str, ndarray, ndarray],
    session_context,
    redis_connection,
):
    ds, coupler = setup_q06_q07_data
    a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
        "name",
        res_coupler_qois,
        session_context,
    )
    qoi = a.process_coupler(ds, coupler)

    q6_crossings = getCrossingForQubit(qoi, "q06")
    q7_crossings = getCrossingForQubit(qoi, "q07")
    assert q6_crossings == pytest.approx([-0.000425, 0.000675], abs=1e-6)
    assert q7_crossings == pytest.approx([-0.00025, 0.000525], abs=1e-6)


@pytest.fixture(autouse=False)
def setup_q08_q09_data():
    dataset_path = (
        Path(__file__).parent / "data" / "dataset_coupler_resonator_spectroscopy_0.hdf5"
    )
    ds = xr.open_dataset(dataset_path)
    coupler = "q08_q09"
    ds = xr.merge(ds[var] for var in ["yq08", "yq09"])
    ds.attrs["coupler"] = coupler
    return ds, coupler


def test_get_crossings_for_q08_q09(
    setup_q08_q09_data: tuple[xr.Dataset, str, ndarray, ndarray],
    session_context,
    redis_connection,
):
    ds, coupler = setup_q08_q09_data
    a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
        "name",
        res_coupler_qois,
        session_context,
    )
    qoi = a.process_coupler(ds, coupler)

    q8_crossings = getCrossingForQubit(qoi, "q08")
    q9_crossings = getCrossingForQubit(qoi, "q09")
    assert q8_crossings == pytest.approx([-0.0008, 0.00075], abs=1e-6)
    assert not q9_crossings


@pytest.fixture(autouse=False)
def setup_q12_q13_data():
    dataset_path = (
        Path(__file__).parent / "data" / "dataset_coupler_resonator_spectroscopy_0.hdf5"
    )
    ds = xr.open_dataset(dataset_path)
    coupler = "q12_q13"
    ds = xr.merge(ds[var] for var in ["yq12", "yq13"])
    ds.attrs["coupler"] = coupler
    return ds, coupler


def test_get_crossings_for_q12_q13(
    setup_q12_q13_data: tuple[xr.Dataset, str, ndarray, ndarray],
    session_context,
    redis_connection,
):
    ds, coupler = setup_q12_q13_data
    a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
        "name",
        res_coupler_qois,
        session_context,
    )
    qoi = a.process_coupler(ds, coupler)

    q12_crossings = getCrossingForQubit(qoi, "q12")
    q13_crossings = getCrossingForQubit(qoi, "q13")
    assert q12_crossings == pytest.approx([-0.000425, 0.000825], abs=1e-6)
    assert not q13_crossings


@pytest.fixture(autouse=False)
def setup_q14_q15_data():
    dataset_path = (
        Path(__file__).parent / "data" / "dataset_coupler_resonator_spectroscopy_0.hdf5"
    )
    ds = xr.open_dataset(dataset_path)
    coupler = "q14_q15"
    ds = xr.merge(ds[var] for var in ["yq14", "yq15"])
    ds.attrs["coupler"] = coupler
    return ds, coupler


def test_get_crossings_for_q14_q15(
    setup_q14_q15_data: tuple[xr.Dataset, str, ndarray, ndarray],
    session_context,
    redis_connection,
):
    ds, coupler = setup_q14_q15_data
    a = ResonatorSpectroscopyVsCurrentCouplerAnalysis(
        "name",
        res_coupler_qois,
        session_context,
    )
    qoi = a.process_coupler(ds, coupler)

    q14_crossings = getCrossingForQubit(qoi, "q14")
    q15_crossings = getCrossingForQubit(qoi, "q15")
    assert not q14_crossings
    assert q15_crossings == pytest.approx([-0.00025, 0.000925], abs=1e-6)
