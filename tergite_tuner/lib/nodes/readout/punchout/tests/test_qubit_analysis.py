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

import pytest
import xarray as xr

from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.base.analysis import BaseAnalysis, BaseQubitAnalysis
from tergite_tuner.lib.nodes.readout.punchout.analysis import PunchoutQubitAnalysis


def test_ca_create_punchout_analysis(session_context: SessionContext):
    a = PunchoutQubitAnalysis("name", ["redis_field"], session=session_context)
    assert isinstance(a, PunchoutQubitAnalysis)
    assert isinstance(a, BaseQubitAnalysis)
    assert isinstance(a, BaseAnalysis)


def test_amplitude_for_q06(session_context: SessionContext, node_data_dir):
    dataset_path = node_data_dir / "dataset_punchout_0.hdf5"
    with xr.open_dataset(dataset_path) as ds:
        amplitude = _amplitude_for_qubit(ds, "q06", session=session_context)
        assert amplitude - 0.016 < 0.001


def test_amplitude_for_q07(node_data_dir, session_context: SessionContext):
    dataset_path = node_data_dir / "dataset_punchout_0.hdf5"
    with xr.open_dataset(dataset_path) as ds:
        amplitude = _amplitude_for_qubit(ds, "q07", session=session_context)
        assert amplitude - 0.016 < 0.001


def test_amplitude_for_q10(node_data_dir, session_context: SessionContext):
    dataset_path = node_data_dir / "dataset_punchout_0.hdf5"
    with xr.open_dataset(dataset_path) as ds:
        amplitude = _amplitude_for_qubit(ds, "q10", session=session_context)
        assert amplitude - 0.045 < 0.001


def test_amplitude_for_q12(node_data_dir, session_context: SessionContext):
    dataset_path = node_data_dir / "dataset_punchout_0.hdf5"
    with xr.open_dataset(dataset_path) as ds:
        amplitude = _amplitude_for_qubit(ds, "q12", session=session_context)
        assert amplitude - 0.030 < 0.001


def test_amplitude_for_q15(node_data_dir, session_context: SessionContext):
    dataset_path = node_data_dir / "dataset_punchout_0.hdf5"
    with xr.open_dataset(dataset_path) as ds:
        amplitude = _amplitude_for_qubit(ds, "q15", session=session_context)
        assert amplitude - 0.06 < 0.001


def _amplitude_for_qubit(ds, qubit, session):
    long_name = f"y{qubit}"
    ds = xr.merge(ds[var] for var in [long_name])
    ds.attrs["qubit"] = qubit

    a = PunchoutQubitAnalysis("name", ["measure:pulse_amp"], session=session)
    qoi = a.process_qubit(ds, qubit)
    return qoi.analysis_result["measure:pulse_amp"]["value"]
