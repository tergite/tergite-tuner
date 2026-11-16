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

from contextlib import contextmanager

import pytest
from qblox_instruments import Cluster
from qcodes.instrument import Instrument
from quantify_scheduler.instrument_coordinator import InstrumentCoordinator

from tergite_tuner.backend import Hardware
from tergite_tuner.exc import ClusterUnreachableError, InstrumentNameTakenError
from tergite_tuner.tests.utils.hardware import get_cluster_name, open_dummy_cluster
from tergite_tuner.utils.types.enums import MeasurementMode


def test_dummy_cluster_has_the_configured_modules(session_context):
    with _opened(session_context) as hardware:
        cluster = hardware.cluster

        assert isinstance(cluster, Cluster)
        assert sorted(cluster.get_connected_modules()) == [2, 3, 16]
        assert cluster.module2.is_rf_type and cluster.module2.is_qcm_type
        assert cluster.module3.is_rf_type and cluster.module3.is_qcm_type
        assert cluster.module16.is_rf_type and cluster.module16.is_qrm_type


def test_hardware_coordinates_the_cluster(session_context):
    with _opened(session_context) as hardware:
        assert isinstance(hardware.coordinator, InstrumentCoordinator)
        assert f"ic_{hardware.cluster.name}" in hardware.coordinator.components()


def test_output_attenuation_is_set_to_value_in_device_config(caplog, session_context):
    with caplog.at_level("WARNING"), _opened(session_context) as hardware:
        attenuations = (
            hardware.cluster.module2.out0_att(),
            hardware.cluster.module2.out1_att(),
            hardware.cluster.module3.out0_att(),
            hardware.cluster.module16.out0_att(),
        )

    # The qubit missing on purpose + all legacy couplers
    assert len(caplog.records) == 9

    log_records = caplog.records[-1]
    assert log_records.levelname == "WARNING"
    assert (
        log_records.message
        == "Skipping setting attenuation for 'q404:mw', as it is not in the connectivity graph of the cluster_config.json."
    )

    # q00:mw, q01:mw, q00_q01:fl, then q00:res and q01:res
    assert attenuations == (4, 8, 12, 18)


def test_unreachable_cluster_raises_instead_of_exiting(session_context, monkeypatch):
    class _RefusingCluster:
        def __init__(self, *_args, **_kwargs):
            raise ConnectionRefusedError()

    monkeypatch.setattr("tergite_tuner.backend.hardware.Cluster", _RefusingCluster)
    session = session_context.model_copy(update={"cluster_mode": MeasurementMode.real})

    with pytest.raises(ClusterUnreachableError):
        Hardware(session)


def test_closing_frees_the_names_the_tuner_opened(session_context):
    Hardware(session_context).close()

    assert not Instrument.exist(get_cluster_name(session_context))
    assert not Instrument.exist("lab_ic")


def test_a_passed_in_cluster_stays_open_after_closing(session_context):
    with open_dummy_cluster(session_context) as cluster:
        Hardware(session_context, cluster=cluster).close()

        assert Instrument.exist(cluster.name)
        assert not Instrument.exist("lab_ic")


def test_a_taken_cluster_name_raises_and_leaves_its_holder_open(session_context):
    with open_dummy_cluster(session_context) as cluster:
        with pytest.raises(InstrumentNameTakenError):
            Hardware(session_context)

        assert Instrument.exist(cluster.name)


def test_a_taken_coordinator_name_raises_and_closes_the_owned_cluster(session_context):
    other = InstrumentCoordinator("lab_ic")
    try:
        with pytest.raises(InstrumentNameTakenError):
            Hardware(session_context)

        assert Instrument.exist("lab_ic")
        assert not Instrument.exist(get_cluster_name(session_context))
    finally:
        other.close()


@contextmanager
def _opened(session):
    """A :class:`Hardware` for ``session``, closed on exit."""
    hardware = Hardware(session)
    try:
        yield hardware
    finally:
        hardware.close()
