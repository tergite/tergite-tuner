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

from typing import TYPE_CHECKING

from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.misc.helpers import insert_nested_key

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def populate_initial_parameters(session: "SessionContext"):
    initial_qubit_parameters = session.device_config.qubits
    initial_coupler_parameters = session.device_config.couplers

    session.redis_store.save_many(
        {
            "transmons": {
                qubit: initial_qubit_parameters[qubit]
                for qubit in session.qubits
                if qubit in initial_qubit_parameters
            },
            "couplers": {
                coupler: initial_coupler_parameters[coupler]
                for coupler in session.couplers
                if coupler in initial_coupler_parameters
            },
        }
    )


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
    data = transmon_configuration[node_name]

    all_components_node_conf = data.get("all", {})
    session.redis_store.save_many(
        {
            "transmons": {
                k: all_components_node_conf for k in session.qubits + session.couplers
            },
            "couplers": {
                coupler: data[coupler]
                for coupler in session.couplers
                if coupler in data
            },
        }
    )


def revert_node_parameters(session: "SessionContext", node_name: str):
    """Reverts the node's parameters to the initial ones got from device config

    Args:
        node_name: name of the node
        session: session context we are working in
    """
    node_configuration = session.node_config
    if not node_name in node_configuration:
        return  # no node specific config found

    initial_params = session.device_config.qubits
    node_specific_dict = node_configuration[node_name].get("all", {})

    initial_data = {}
    for qubit in session.qubits:
        qubit_conf = initial_params.get(qubit)
        if qubit_conf:
            try:
                for node, node_conf in node_specific_dict.items():
                    for param in node_conf.keys():
                        insert_nested_key(
                            initial_data,
                            path=(qubit, node, param),
                            value=qubit_conf[node][param],
                        )
            except (TypeError, AttributeError) as e:
                raise NotImplementedError("Only field modules supported") from e
            except KeyError as e:
                raise KeyError(
                    f"missing node,param in qubit '{qubit}' config: {qubit_conf}, node conf: {node_specific_dict}"
                ) from e

    session.redis_store.save_many({"transmons": initial_data})
