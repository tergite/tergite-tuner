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

from tergite_tuner.tuner import NodeManager
from tergite_tuner.utils.types.enums import MeasurementMode
from tergite_tuner.utils.types.node_enum import NodeEnum


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
    node_manager = NodeManager(None, session=session_context)

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
