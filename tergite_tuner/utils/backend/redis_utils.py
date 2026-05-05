# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (c) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Abdullah Al Amin 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import TYPE_CHECKING, Type

from tergite_tuner.lib.base.node import BaseNode, CouplerNode, QubitNode
from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def populate_initial_parameters(session: "SessionContext"):
    initial_qubit_parameters = session.device_config.qubits
    initial_coupler_parameters = session.device_config.couplers

    # Populate the Redis database with the initial 'reasonable'
    # parameter values from the device_config object
    for qubit in session.qubits:
        per_qubit = initial_qubit_parameters.get(qubit, {})
        for module_key, module_value in per_qubit.items():
            if isinstance(module_value, dict):
                for parameter_key, parameter_value in module_value.items():
                    sub_module_key = module_key + ":" + parameter_key
                    session.redis.hset(
                        f"transmons:{qubit}", sub_module_key, parameter_value
                    )
            else:
                session.redis.hset(f"transmons:{qubit}", module_key, module_value)

    for coupler in session.couplers:
        per_coupler = initial_coupler_parameters.get(coupler, {})
        for module_key, module_value in per_coupler.items():
            session.redis.hset(f"couplers:{coupler}", module_key, module_value)


def _qubit_fields_to_redis(qubits: list[str], key: str, value: str, redis_connection):
    for qubit in qubits:
        redis_connection.hset(f"transmons:{qubit}", key, value)


def _coupler_fields_to_redis(
    couplers: list[str], key: str, value: str, redis_connection
):
    for coupler in couplers:
        redis_connection.hset(f"transmons:{coupler}", key, value)


def populate_node_parameters(
    node_name: str,
    is_node_calibrated: bool,
    session: "SessionContext",
):
    # Populate the Redis database with node specific parameter values from the toml file
    transmon_configuration = session.node_config
    if not node_name in transmon_configuration:
        logger.status(f"{node_name} does not have specific node config")
        return
    if is_node_calibrated:
        logger.status(f"{node_name} is already calibrated")
        return
    node_specific_dict = transmon_configuration[node_name].get("all", {})

    for field_key, field_value in node_specific_dict.items():
        if isinstance(field_value, dict):
            for sub_field_key, sub_field_value in field_value.items():
                sub_field_key = field_key + ":" + sub_field_key
                _qubit_fields_to_redis(
                    session.qubits, sub_field_key, sub_field_value, session.redis
                )
                _coupler_fields_to_redis(
                    session.couplers, sub_field_key, sub_field_value, session.redis
                )
        else:
            _qubit_fields_to_redis(
                session.qubits, field_key, field_value, session.redis
            )
            _coupler_fields_to_redis(
                session.couplers, field_key, field_value, session.redis
            )

    # node config for specific couplers:
    for coupler in session.couplers:
        if coupler in transmon_configuration[node_name]:
            coupler_specific_config = transmon_configuration[node_name][coupler]
            for field_key, field_value in coupler_specific_config.items():
                session.redis.hset(f"couplers:{coupler}", field_key, field_value)


def revert_node_parameters(node_name: str, session: "SessionContext"):

    node_configuration = session.node_config
    if not node_name in node_configuration:
        return  # no node specific config found

    initial_qubit_parameters = session.device.qubits

    node_specific_dict = node_configuration[node_name].get("all", {})

    for field_key, field_value in node_specific_dict.items():
        if not isinstance(field_value, dict):
            raise NotImplementedError("Only field modules supported")
        for sub_field_key in field_value.keys():
            for qubit in session.qubits:
                initial_qubit_field = initial_qubit_parameters[qubit][field_key]
                initial_value = initial_qubit_field[sub_field_key]
                key = field_key + ":" + sub_field_key
                # restore initial parameter value
                session.redis.hset(f"transmons:{qubit}", key, initial_value)


def populate_quantities_of_interest(
    node_cls: Type[BaseNode],
    node_name: str,
    qubits: list[str],
    couplers: list[str],
    redis_connection,
):
    # Populate the Redis database with the quantities of interest, at Nan value
    # Only if the key does NOT already exist
    # Thuis code should be moved to the specific classes
    if issubclass(node_cls, QubitNode):
        qubit_qois = node_cls.qubit_qois
        if qubit_qois is None:
            logger.warning(f"No qois for node {node_name}")
            return
        for qubit in qubits:
            redis_key = f"transmons:{qubit}"
            calibration_supervisor_key = f"cs:{qubit}"
            for qoi in qubit_qois:
                if not redis_connection.hexists(redis_key, qoi):
                    redis_connection.hset(f"transmons:{qubit}", qoi, "nan")
                    if qoi == "measure_3state_opt:pulse_amp":
                        redis_connection.hset(f"transmons:{qubit}", qoi, "0")
                    elif qoi == "measure_2state_opt:pulse_amp":
                        redis_connection.hset(f"transmons:{qubit}", qoi, "0")
                    elif qoi == "rxy:motzoi":
                        redis_connection.hset(f"transmons:{qubit}", qoi, "0")
                    elif qoi == "r12:ef_motzoi":
                        redis_connection.hset(f"transmons:{qubit}", qoi, "0")
            # flag for the calibration supervisor
            if not redis_connection.hexists(calibration_supervisor_key, node_name):
                redis_connection.hset(f"cs:{qubit}", node_name, "not_calibrated")

    elif issubclass(node_cls, CouplerNode):
        coupler_qois = node_cls.coupler_qois
        if coupler_qois is not None:
            for coupler in couplers:
                redis_key = f"couplers:{coupler}"
                calibration_supervisor_key = f"cs:{coupler}"
                for qoi in coupler_qois:
                    # check if field already exists
                    if not redis_connection.hexists(redis_key, qoi):
                        redis_connection.hset(f"couplers:{coupler}", qoi, "nan")
                # flag for the calibration supervisor
                if not redis_connection.hexists(calibration_supervisor_key, node_name):
                    redis_connection.hset(f"cs:{coupler}", node_name, "not_calibrated")

    else:
        raise ValueError(
            f"Node {node_name} with base type {node_cls} is not a valid Qubit or Coupler node. Cannot populate quantities of interest."
        )


def fetch_redis_params(param: str, this_element: str, redis_connection):
    if "_" in this_element:
        name = "couplers"
    else:
        name = "transmons"
    redis_config = redis_connection.hgetall(f"{name}:{this_element}")
    return float(redis_config[param])
