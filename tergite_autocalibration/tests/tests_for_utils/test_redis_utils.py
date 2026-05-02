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
from tergite_autocalibration.lib.utils.node_factory import NodeFactory
from tergite_autocalibration.utils.backend.redis_utils import (
    populate_initial_parameters,
    populate_node_parameters,
    populate_quantities_of_interest,
    revert_node_parameters,
)


def test_populate_initial_parameters(redis_connection, session_context):

    redis_connection.flushall()
    assert not redis_connection.keys()

    configuration = session_context.config
    device = configuration.device
    qubits = list(device.qubits.keys())
    couplers = list(device.couplers.keys())
    populate_initial_parameters(qubits, couplers, redis_connection, configuration)
    redis_keys = redis_connection.keys()

    # test that all device elements are on redis
    for qubit in qubits:
        assert f"transmons:{qubit}" in redis_keys
    for coupler in couplers:
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

    configuration = session_context.config
    device = configuration.device
    qubits = device.qubits.keys()
    couplers = device.couplers.keys()
    populate_node_parameters(
        "resonator_spectroscopy",
        False,
        list(qubits),
        list(couplers),
        redis_connection,
        configuration,
    )

    # test node config values are correctly uploaded onto redis
    node_config = configuration.node["resonator_spectroscopy"]["all"]
    reset_duration_config = node_config["reset"]["duration"]
    reset_duration_redis = float(
        redis_connection.hget("transmons:q00", "reset:duration")
    )
    assert reset_duration_config == reset_duration_redis


def test_revert_node_parameters(redis_connection, session_context):

    redis_connection.flushall()
    assert not redis_connection.keys()

    configuration = session_context.config
    device = configuration.device
    qubits = device.qubits.keys()
    initial_qubit_parameters = device.qubits
    node = "resonator_spectroscopy"

    # flush the duration value
    redis_connection.hset("transmons:q00", "reset:duration", "nan")

    revert_node_parameters(node, list(qubits), redis_connection, configuration)
    reset_duration_redis = float(
        redis_connection.hget("transmons:q00", "reset:duration")
    )
    initial_reset_value = initial_qubit_parameters["q00"]["reset"]["duration"]

    assert reset_duration_redis == initial_reset_value


def test_populate_quantities_of_interest(redis_connection):
    """
    Iterate over all nodes in the factory and check whether they correctly push qois to redis
    """

    redis_connection.flushall()
    assert not redis_connection.keys()

    node_factory = NodeFactory()
    for node_name in node_factory.all_node_names():
        redis_connection.flushall()
        assert not redis_connection.keys()

        populate_quantities_of_interest(
            node_name, node_factory, ["q00", "q01"], ["q00_q01"], redis_connection
        )

        node_cls = node_factory.get_node_class(node_name)

        if hasattr(node_cls, "qubit_qois"):
            for qubit_qoi in node_cls.qubit_qois:
                assert redis_connection.hexists("transmons:q00", qubit_qoi)

        if hasattr(node_cls, "coupler_qois"):
            for coupler_qoi in node_cls.coupler_qois:
                assert redis_connection.hexists("couplers:q00_q01", coupler_qoi)
