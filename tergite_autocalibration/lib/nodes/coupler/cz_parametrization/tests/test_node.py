# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Eleftherios Moschandreou 2025
# (C) Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import pytest

from tergite_autocalibration.lib.base.node import CouplerNode
from tergite_autocalibration.lib.nodes.coupler.cz_parametrization.analysis import (
    CZParametrizationAnalysis,
)
from tergite_autocalibration.lib.nodes.coupler.cz_parametrization.measurement import (
    CZParametrizationMeasurement,
)
from tergite_autocalibration.lib.nodes.coupler.cz_parametrization.node import (
    CZParametrizationNode,
)
from tergite_autocalibration.lib.nodes.external_parameter_node import (
    ExternalParameterNode,
)
from tergite_autocalibration.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)
from tergite_autocalibration.utils.dto.extended_transmon_element import ExtendedTransmon


def test_cannotCreateCorrectType(redis_connection, session_context):
    """
    raise error if parking current does not exist on redis
    """
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    coupler = "q14_q15"
    if redis_connection.hexists(f"couplers:{coupler}", "initial_parking_current"):
        redis_connection.hdel(f"couplers:{coupler}", "initial_parking_current")

    with pytest.raises(TypeError):
        CZParametrizationNode(
            all_qubits=["q14", "q15"],
            couplers=["q14_q15"],
            session=session_context,
        )


def test_canCreateCorrectType(redis_connection, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    coupler = "q14_q15"
    redis_connection.hset(f"couplers:{coupler}", "initial_parking_current", "100e-6")
    redis_connection.hset(f"couplers:{coupler}", "cz_phase_path", "via_20")
    redis_connection.hset(f"couplers:{coupler}", "control_qubit", "q15")
    redis_connection.hset(f"couplers:{coupler}", "target_qubit", "q14")
    redis_connection.hset(f"transmons:{'q14'}", "clock_freqs:f01", "4.2e6")
    redis_connection.hset(f"transmons:{'q14'}", "clock_freqs:f12", "4.0e6")
    redis_connection.hset(f"transmons:{'q15'}", "clock_freqs:f01", "5.2e6")
    redis_connection.hset(f"transmons:{'q15'}", "clock_freqs:f12", "5.0e6")
    node = CZParametrizationNode(
        all_qubits=["q14", "q15"],
        couplers=[coupler],
        session=session_context,
    )
    assert isinstance(node, CouplerNode)


def test_ValidationReturnErrorWithSameQubitCoupler(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    with pytest.raises(ValueError):
        CZParametrizationNode(
            all_qubits=["q14", "q15"],
            couplers=["q14_q14"],
            session=session_context,
        )


@pytest.mark.skip
def test_ValidationReturnErrorWithQubitsNotMatchingCouplers(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    with pytest.raises(ValueError):
        CZParametrizationNode(
            all_qubits=["q14", "q16"],
            couplers=["q14_q15"],
            session=session_context,
        )


def test_MeasurementClassType(redis_connection, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    coupler = "q14_q15"
    redis_connection.hset(f"couplers:{coupler}", "initial_parking_current", "100e-6")
    redis_connection.hset(f"couplers:{coupler}", "control_qubit", "q15")
    redis_connection.hset(f"couplers:{coupler}", "target_qubit", "q14")
    redis_connection.hset(f"transmons:q14", "clock_freqs:f01", "5.2e6")
    redis_connection.hset(f"transmons:q14", "clock_freqs:f12", "5.0e6")
    redis_connection.hset(f"transmons:q15", "clock_freqs:f01", "4.2e6")
    redis_connection.hset(f"transmons:q15", "clock_freqs:f12", "4.0e6")
    redis_connection.hset(f"couplers:{coupler}", "cz_phase_path", "via_20")
    c = CZParametrizationNode(
        all_qubits=["q14", "q15"],
        couplers=[coupler],
        session=session_context,
    )
    assert isinstance(c.measurement_cls, type(CZParametrizationMeasurement))
    assert isinstance(c.analysis_cls, type(CZParametrizationAnalysis))
    assert issubclass(c.measurement_type_cls, ExternalParameterNode)


def test_dummy_generation(redis_connection, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    for coupler in DEFAULT_TEST_COUPLERS:
        c_qubit, t_qubit = coupler.split("_")
        redis_connection.hset(
            f"couplers:{coupler}", "initial_parking_current", "100e-6"
        )
        redis_connection.hset(f"couplers:{coupler}", "cz_phase_path", "via_20")
        redis_connection.hset(f"couplers:{coupler}", "control_qubit", c_qubit)
        redis_connection.hset(f"couplers:{coupler}", "target_qubit", t_qubit)

    for qubit in DEFAULT_TEST_QUBITS[::2]:
        redis_connection.hset(f"transmons:{qubit}", "clock_freqs:f01", "4.2e6")
        redis_connection.hset(f"transmons:{qubit}", "clock_freqs:f12", "4.0e6")
        redis_connection.hset(f"transmons:{qubit}", "centroid_I", "0")
        redis_connection.hset(f"transmons:{qubit}", "centroid_Q", "0")
        redis_connection.hset(f"transmons:{qubit}", "omega_01", "60")
        redis_connection.hset(f"transmons:{qubit}", "omega_12", "180")
        redis_connection.hset(f"transmons:{qubit}", "omega_20", "270")
    for qubit in DEFAULT_TEST_QUBITS[1::2]:
        redis_connection.hset(f"transmons:{qubit}", "clock_freqs:f01", "5.2e6")
        redis_connection.hset(f"transmons:{qubit}", "clock_freqs:f12", "5.0e6")
        redis_connection.hset(f"transmons:{qubit}", "centroid_I", "0")
        redis_connection.hset(f"transmons:{qubit}", "centroid_Q", "0")
        redis_connection.hset(f"transmons:{qubit}", "omega_01", "60")
        redis_connection.hset(f"transmons:{qubit}", "omega_12", "180")
        redis_connection.hset(f"transmons:{qubit}", "omega_20", "270")

    node = CZParametrizationNode(
        all_qubits=DEFAULT_TEST_QUBITS,
        couplers=DEFAULT_TEST_COUPLERS,
        session=session_context,
    )
    dummy_dataset = node.generate_dummy_dataset()
    first_coupler = DEFAULT_TEST_COUPLERS[0]

    number_of_frequencies = len(
        node.schedule_samplespace["cz_pulse_frequencies"][first_coupler]
    )
    number_of_amplitudes = len(
        node.schedule_samplespace["cz_pulse_amplitudes"][first_coupler]
    )

    data_vars = dummy_dataset.data_vars

    assert len(data_vars) == 2 * len(DEFAULT_TEST_COUPLERS)
    assert (
        data_vars[0].size == number_of_frequencies * number_of_amplitudes * node.loops
    )
