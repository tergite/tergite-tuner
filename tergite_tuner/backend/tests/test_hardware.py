# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import pytest
from qblox_instruments import Cluster
from quantify_scheduler.instrument_coordinator import InstrumentCoordinator

from tergite_tuner.backend import Hardware
from tergite_tuner.exc import ClusterUnreachableError
from tergite_tuner.utils.types.enums import MeasurementMode


def test_dummy_cluster_has_the_configured_modules(session_context):
    cluster = Hardware(session_context).cluster

    assert isinstance(cluster, Cluster)
    assert sorted(cluster.get_connected_modules()) == [2, 3, 16]
    assert cluster.module2.is_rf_type and cluster.module2.is_qcm_type
    assert cluster.module3.is_rf_type and cluster.module3.is_qcm_type
    assert cluster.module16.is_rf_type and cluster.module16.is_qrm_type


def test_hardware_coordinates_the_cluster(session_context):
    hardware = Hardware(session_context)

    assert isinstance(hardware.coordinator, InstrumentCoordinator)
    assert f"ic_{hardware.cluster.name}" in hardware.coordinator.components()


def test_output_attenuation_is_set_to_value_in_device_config(caplog, session_context):
    with caplog.at_level("WARNING"):
        hardware = Hardware(session_context)

    # The qubit missing on purpose + all legacy couplers
    assert len(caplog.records) == 9

    log_records = caplog.records[-1]
    assert log_records.levelname == "WARNING"
    assert (
        log_records.message
        == "Skipping setting attenuation for 'q404:mw', as it is not in the connectivity graph of the cluster_config.json."
    )

    assert hardware.cluster.module2.out0_att() == 4  # q00:mw
    assert hardware.cluster.module2.out1_att() == 8  # q01:mw
    assert hardware.cluster.module3.out0_att() == 12  # q00_q01:fl
    assert hardware.cluster.module16.out0_att() == 18  # q00:res, q01:res


def test_unreachable_cluster_raises_instead_of_exiting(session_context, monkeypatch):
    class _RefusingCluster:
        close_all = staticmethod(lambda: None)

        def __init__(self, *_args, **_kwargs):
            raise ConnectionRefusedError()

    monkeypatch.setattr("tergite_tuner.backend.hardware.Cluster", _RefusingCluster)
    session = session_context.model_copy(update={"cluster_mode": MeasurementMode.real})

    with pytest.raises(ClusterUnreachableError):
        Hardware(session)
