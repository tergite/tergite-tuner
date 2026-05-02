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

from tergite_autocalibration.lib.base.node import CouplerNode
from tergite_autocalibration.lib.nodes.coupler.cz_chevron.analysis import (
    CZChevronAnalysis,
)
from tergite_autocalibration.lib.nodes.coupler.cz_chevron.measurement import (
    CZChevronMeasurement,
)
from tergite_autocalibration.lib.nodes.coupler.cz_chevron.node import CZChevronNode
from tergite_autocalibration.lib.nodes.schedule_node import OuterScheduleNode
from tergite_autocalibration.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)
from tergite_autocalibration.utils.dto.extended_transmon_element import ExtendedTransmon


def test_node_creation(redis_connection, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    coupler = "q13_q14"
    session_context.redis.hset(
        f"couplers:{coupler}", "initial_parking_current", "100e-6"
    )
    session_context.redis.hset(f"couplers:{coupler}", "cz_half_duration", "92e-9")
    session_context.redis.hset(f"couplers:{coupler}", "control_qubit", "q13")
    session_context.redis.hset(f"couplers:{coupler}", "target_qubit", "q14")
    session_context.redis.hset(f"transmons:{'q13'}", "clock_freqs:f01", "4.2e6")
    session_context.redis.hset(f"transmons:{'q13'}", "clock_freqs:f12", "4.0e6")
    session_context.redis.hset(f"transmons:{'q14'}", "clock_freqs:f01", "5.2e6")
    session_context.redis.hset(f"transmons:{'q14'}", "clock_freqs:f12", "5.0e6")
    session_context.redis.hset(f"couplers:{'q13_q14'}", "cz_pulse_frequency", "7.16e8")
    node = CZChevronNode(
        couplers=[coupler],
        session=session_context,
    )
    assert isinstance(node, CouplerNode)


def test_class_attribute_objects(redis_connection, session_context):
    session_context.redis.hset(f"couplers:{'q13_q14'}", "cz_pulse_frequency", "7.16e8")
    session_context.redis.hset(f"couplers:{'q13_q14'}", "cz_half_duration", "92e-9")
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node = CZChevronNode(
        couplers=["q13_q14"],
        session=session_context,
    )
    assert isinstance(node.measurement_cls, type(CZChevronMeasurement))
    assert isinstance(node.analysis_cls, type(CZChevronAnalysis))
    assert issubclass(node.measurement_type_cls, OuterScheduleNode)


def test_dummy_generation(redis_connection, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    for coupler in DEFAULT_TEST_COUPLERS:
        c_qubit, t_qubit = coupler.split("_")
        session_context.redis.hset(f"couplers:{coupler}", "cz_half_duration", "92e-9")
        session_context.redis.hset(f"couplers:{coupler}", "control_qubit", c_qubit)
        session_context.redis.hset(f"couplers:{coupler}", "target_qubit", t_qubit)
        session_context.redis.hset(
            f"couplers:{coupler}", "initial_parking_current", "100e-6"
        )
        session_context.redis.hset(
            f"couplers:{coupler}", "cz_pulse_frequency", "7.16e8"
        )
    for qubit in DEFAULT_TEST_QUBITS[::2]:
        session_context.redis.hset(f"transmons:{qubit}", "clock_freqs:f01", "4.2e6")
        session_context.redis.hset(f"transmons:{qubit}", "clock_freqs:f12", "4.0e6")
    for qubit in DEFAULT_TEST_QUBITS[1::2]:
        session_context.redis.hset(f"transmons:{qubit}", "clock_freqs:f01", "5.2e6")
        session_context.redis.hset(f"transmons:{qubit}", "clock_freqs:f12", "5.0e6")

    node = CZChevronNode(DEFAULT_TEST_COUPLERS, session=session_context)
    dummy_dataset = node.generate_dummy_dataset()
    first_coupler = DEFAULT_TEST_COUPLERS[0]

    number_of_durations = len(
        node.schedule_samplespace["cz_pulse_durations"][first_coupler]
    )

    data_vars = dummy_dataset.data_vars

    assert len(data_vars) == 2 * len(DEFAULT_TEST_COUPLERS)
    assert data_vars[0].size == number_of_durations * node.loops
