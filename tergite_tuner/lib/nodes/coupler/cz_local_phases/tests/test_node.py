# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2026
# (C) Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from tergite_tuner.lib.base.node import CouplerNode
from tergite_tuner.lib.nodes.coupler.cz_local_phases.analysis import (
    CZLocalPhasesNodeAnalysis,
)
from tergite_tuner.lib.nodes.coupler.cz_local_phases.measurement import (
    CZLocalPhasesMeasurement,
)
from tergite_tuner.lib.nodes.coupler.cz_local_phases.node import CZLocalPhasesNode
from tergite_tuner.lib.nodes.schedule_node import ScheduleNode
from tergite_tuner.tests.utils.decorators import loaded_redis
from tergite_tuner.utils.dto.extended_transmon_element import ExtendedTransmon

_REDIS_DATA_FILENAME = "redis-2026-02-06-18.json"


def test_node_creation(redis_connection, session_context, node_data_dir):
    redis_data_file = node_data_dir / _REDIS_DATA_FILENAME
    with loaded_redis(redis_connection, redis_data_file):
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        node = CZLocalPhasesNode(
            all_qubits=["q13", "q14"], couplers=["q13_q14"], session=session_context
        )
        assert isinstance(node, CouplerNode)


def test_class_attribute_objects(redis_connection, session_context, node_data_dir):
    redis_data_file = node_data_dir / _REDIS_DATA_FILENAME
    with loaded_redis(redis_connection, redis_data_file):
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        node = CZLocalPhasesNode(
            all_qubits=["q13", "q14"], couplers=["q13_q14"], session=session_context
        )
        assert isinstance(node.measurement_cls, type(CZLocalPhasesMeasurement))
        assert isinstance(node.analysis_cls, type(CZLocalPhasesNodeAnalysis))
        assert issubclass(node.measurement_type_cls, ScheduleNode)


def test_dummy_generation(redis_connection, session_context, node_data_dir):
    redis_data_file = node_data_dir / _REDIS_DATA_FILENAME
    with loaded_redis(redis_connection, redis_data_file):
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated

        coupler = "q13_q14"
        couplers = [coupler]
        node = CZLocalPhasesNode(
            all_qubits=["q13", "q14"], couplers=couplers, session=session_context
        )
        dummy_dataset = node.generate_dummy_dataset()

        number_of_local_phases = len(node.schedule_samplespace["local_phases"]["q13"])
        number_of_gate_modes = len(node.schedule_samplespace["gate_modes"][coupler])
        number_of_swap_modes = len(node.schedule_samplespace["swap"][coupler])

        samples = number_of_local_phases * number_of_gate_modes * number_of_swap_modes

        data_vars = dummy_dataset.data_vars

        assert len(data_vars) == 2 * len(couplers)
        assert data_vars[0].size == samples * node.loops
