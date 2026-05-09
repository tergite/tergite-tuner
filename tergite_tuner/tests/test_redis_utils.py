# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (c) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from tergite_tuner.lib.nodes import DEFAULT_NODE_NAME_CLS_MAP
from tergite_tuner.storage.redis.utils import (
    populate_initial_parameters,
    populate_node_parameters,
    revert_node_parameters,
)


def test_populate_initial_parameters(redis_connection, session_context):

    redis_connection.flushall()
    assert not redis_connection.keys()

    device = session_context.device_config
    populate_initial_parameters(session_context)
    redis_keys = redis_connection.keys()

    # ``populate_initial_parameters`` pushes only the qubits and couplers
    # selected for *this* calibration run (``session.qubits`` /
    # ``session.couplers``); the device config can describe more
    # components than are actually being calibrated.
    for qubit in session_context.qubits:
        assert f"transmons:{qubit}" in redis_keys
    for coupler in session_context.couplers:
        assert f"couplers:{coupler}" in redis_keys

    # test values are correctly uploaded onto redis
    ro_config_ruration = device.qubits["q00"]["measure"]["pulse_duration"]
    ro_redis_duration = float(
        redis_connection.hget("transmons:q00", "measure:pulse_duration")
    )
    assert ro_config_ruration == ro_redis_duration
    cz_amplitude_redis = float(
        redis_connection.hget("couplers:q00_q01", "cz_pulse_amplitude")
    )
    cz_amplitude_config = device.couplers["q00_q01"]["cz_pulse_amplitude"]
    assert cz_amplitude_redis == cz_amplitude_config


def test_populate_node_parameters(redis_connection, session_context):

    redis_connection.flushall()
    assert not redis_connection.keys()

    populate_node_parameters(
        "resonator_spectroscopy", is_node_calibrated=False, session=session_context
    )

    # test node config values are correctly uploaded onto redis
    node_config = session_context.node_config["resonator_spectroscopy"]["all"]
    reset_duration_config = node_config["reset"]["duration"]
    reset_duration_redis = float(
        redis_connection.hget("transmons:q00", "reset:duration")
    )
    assert reset_duration_config == reset_duration_redis


def test_revert_node_parameters(redis_connection, session_context):

    redis_connection.flushall()
    assert not redis_connection.keys()

    device = session_context.device_config
    initial_qubit_parameters = device.qubits
    node = "resonator_spectroscopy"

    # flush the duration value
    redis_connection.hset("transmons:q00", "reset:duration", "nan")

    revert_node_parameters(session_context, node_name=node)
    reset_duration_redis = float(
        redis_connection.hget("transmons:q00", "reset:duration")
    )
    initial_reset_value = initial_qubit_parameters["q00"]["reset"]["duration"]

    assert reset_duration_redis == initial_reset_value


def test_persist_qois(redis_connection, session_context):
    """
    Iterate over every registered node and check whether it correctly
    pushes its QOI placeholders to redis.
    """

    redis_connection.flushall()
    assert not redis_connection.keys()

    for node_name, node_cls in DEFAULT_NODE_NAME_CLS_MAP.items():
        redis_connection.flushall()
        assert not redis_connection.keys()

        session_context.qubits = ["q00", "q01"]
        session_context.couplers = ["q00_q01"]
        node_cls.persist_qois(session_context, node_name=node_name)

        if hasattr(node_cls, "qubit_qois") and node_cls.qubit_qois is not None:
            for qubit_qoi in node_cls.qubit_qois:
                assert redis_connection.hexists("transmons:q00", qubit_qoi)

        if hasattr(node_cls, "coupler_qois") and node_cls.coupler_qois is not None:
            for coupler_qoi in node_cls.coupler_qois:
                assert redis_connection.hexists("couplers:q00_q01", coupler_qoi)
