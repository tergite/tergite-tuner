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

from qblox_instruments import Cluster
from quantify_scheduler.instrument_coordinator import InstrumentCoordinator

from tergite_tuner.tuner import HardwareManager, NodeManager
from tergite_tuner.utils.dto.enums import MeasurementMode
from tergite_tuner.utils.dto.node_enum import NodeEnum


def test_instantiate_calibration_config(session_context):
    assert session_context.cluster_mode == MeasurementMode.dummy
    assert session_context.cluster_ip is None
    assert session_context.cluster_timeout == 222
    assert set(session_context.qubits) == {"q00", "q01"}
    assert set(session_context.couplers) == {"q00_q01"}
    assert len(session_context.user_samplespace.keys()) == 1
    assert "resonator_spectroscopy" in session_context.user_samplespace
    assert (
        "ro_frequencies" in session_context.user_samplespace["resonator_spectroscopy"]
    )
    assert len(session_context.user_samplespace["resonator_spectroscopy"].keys()) == 1
    assert set(
        session_context.user_samplespace["resonator_spectroscopy"][
            "ro_frequencies"
        ].keys()
    ) == {"q00", "q01"}
    assert session_context.target_node_name == "ro_amplitude_two_state_optimization"


def test_instantiate_calibration_supervisor(session_context, redis_connection):
    hw_manager = HardwareManager(config=session_context)
    node_manager = NodeManager(
        hw_manager.get_instrument_coordinator(), session=session_context
    )
    lab_ic = hw_manager.get_instrument_coordinator()

    assert isinstance(hw_manager, HardwareManager)
    assert isinstance(node_manager, NodeManager)
    assert isinstance(lab_ic, InstrumentCoordinator)

    topo_order = node_manager.topo_order(session_context.target_node)
    assert isinstance(topo_order, list)
    assert tuple(topo_order) == (
        NodeEnum.RESONATOR_SPECTROSCOPY,
        NodeEnum.QUBIT_01_SPECTROSCOPY,
        NodeEnum.RABI_OSCILLATIONS,
        NodeEnum.RAMSEY_CORRECTION,
        NodeEnum.MOTZOI_PARAMETER,
        NodeEnum.N_RABI_OSCILLATIONS,
        NodeEnum.RESONATOR_SPECTROSCOPY_1,
        NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
    )


def test_hardware_manager_creates_dummy_cluster(session_context, redis_connection):
    hw_manager = HardwareManager(config=session_context)
    cl = hw_manager.cluster
    assert isinstance(cl, Cluster)

    for slot_idx in range(1, 16):
        _dummy_qcm_rf = getattr(cl, f"module{slot_idx}")
        assert _dummy_qcm_rf.present()
        assert _dummy_qcm_rf.is_rf_type and _dummy_qcm_rf.is_qcm_type

    assert cl.module16.present()
    assert cl.module17.present()
    assert cl.module16.is_rf_type and cl.module16.is_qrm_type
    assert cl.module17.is_rf_type and cl.module17.is_qrm_type


def test_hardware_manager_creates_ic(session_context, redis_connection):
    hw_manager = HardwareManager(config=session_context)
    assert isinstance(hw_manager.lab_ic, InstrumentCoordinator)
    assert hw_manager.get_instrument_coordinator().name == hw_manager.lab_ic.name


def test_output_attenuation_is_set_to_value_in_device_config(
    caplog, session_context, redis_connection
):
    """Output attenuation is set during the instantiation of the HardwareManager."""
    with caplog.at_level("WARNING"):
        hw_manager = HardwareManager(config=session_context)

    # The qubit missing on purpose + all legacy couplers
    assert len(caplog.records) == 9

    log_records = caplog.records[-1]
    assert log_records.levelname == "WARNING"
    assert (
        log_records.message
        == "Skipping setting attenuation for 'q404:mw', as it is not in the connectivity graph of the cluster_config.json."
    )

    assert hw_manager.cluster.module2.out0_att() == 4  # q00:mw
    assert hw_manager.cluster.module2.out1_att() == 8  # q01:mw
    assert hw_manager.cluster.module3.out0_att() == 12  # q00_q01:fl
    assert hw_manager.cluster.module16.out0_att() == 18  # q00:res, q01:res
