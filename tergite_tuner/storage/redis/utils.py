# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (c) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Abdullah Al Amin 2026
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import copy
from typing import TYPE_CHECKING, Any, Dict

from tergite_tuner.utils.dicts import insert_nested_key, update_nested
from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def populate_initial_parameters(session: "SessionContext"):
    """Populates the store with the initial values from the device config

    Args:
        session: the session context
    """
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
    """Populate the database with node specific parameter values from the node config

    Args:
        session: the session context
        node_name: the name of the node
        is_node_calibrated: whether the node is calibrated
    """
    transmon_configuration = session.node_config
    if node_name not in transmon_configuration.root:
        logger.status(f"{node_name} does not have specific node config")
        return
    if is_node_calibrated:
        logger.status(f"{node_name} is already calibrated")
        return
    data = transmon_configuration.root[node_name]
    couplers = session.couplers
    qubits = session.qubits

    session.redis_store.save_many(
        {
            "transmons": {q: _get_qubit_node_config(data, q) for q in qubits},
            "couplers": {
                coupler: data[coupler] for coupler in couplers if coupler in data
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
    if node_name not in node_configuration.root:
        return  # no node specific config found

    initial_params = session.device_config.qubits

    initial_data = {}
    for qubit in session.qubits:
        qubit_conf = initial_params.get(qubit)
        node_specific_dict = _get_qubit_node_config(
            node_configuration.root[node_name], qubit
        )
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


def _get_qubit_node_config(node_section: Dict[str, Any], qubit: str) -> Dict[str, Any]:
    """The qubit's own section of a node's config, falling back to its 'all' section."""
    qubit_config = copy.deepcopy(node_section.get(qubit, {}))
    update_nested(qubit_config, node_section.get("all", {}))
    return qubit_config
