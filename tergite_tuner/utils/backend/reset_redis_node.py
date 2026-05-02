# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Liangyu Chen 2024
# (c) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import List

from tergite_tuner.lib.nodes import __NODE_STR_CLS_MAP__
from tergite_tuner.utils.logging import logger


def reset_all_redis_nodes(
    qubits: List[str], couplers: List[str], redis_connection
) -> None:
    """
    Wraps :func:`reset_redis_nodes` and resets every node in the
    canonical :data:`__NODE_STR_CLS_MAP__`.

    Args:
        qubits: list of qubit identifiers (e.g. ``["q00", "q01"]``) to reset.
        couplers: list of coupler identifiers (e.g. ``["q00_q01"]``) to reset.
        redis_connection: redis client to write to.
    """
    reset_redis_nodes(
        qubits, couplers, list(__NODE_STR_CLS_MAP__.keys()), redis_connection
    )


def reset_redis_nodes(
    qubits: List[str],
    couplers: List[str],
    node_names: List[str],
    redis_connection,
) -> None:
    """
    Reset the qubit and coupler values for given nodes in redis.

    Args:
        qubits: list of qubit identifiers (e.g. ``["q00", "q01"]``) to reset.
        couplers: list of coupler identifiers (e.g. ``["q00_q01"]``) to reset.
        node_names: names of nodes whose qois should be reset to ``"nan"``.
        redis_connection: redis client to write to.
    """
    for node_name in node_names:
        node_cls = __NODE_STR_CLS_MAP__[node_name]

        logger.status(f"Resetting node: {node_name}")
        qubit_qois = getattr(node_cls, "qubit_qois", None)
        if qubit_qois:
            for qubit in qubits:
                redis_prefix_ = f"transmons:{qubit}"
                for qoi in qubit_qois:
                    redis_connection.hset(redis_prefix_, qoi, "nan")
                    if "motzoi" in qoi:
                        redis_connection.hset(redis_prefix_, qoi, "0")
                    if "measure_3state_opt:pulse_amp" in qoi:
                        redis_connection.hset(redis_prefix_, qoi, "0")
                    if "measure_2state_opt:pulse_amp" in qoi:
                        redis_connection.hset(redis_prefix_, qoi, "0")
                redis_connection.hset(f"cs:{qubit}", node_name, "not_calibrated")

        coupler_qois = getattr(node_cls, "coupler_qois", None)
        if coupler_qois:
            for coupler in couplers:
                redis_prefix_ = f"couplers:{coupler}"
                for coupler_qoi in coupler_qois:
                    redis_connection.hset(redis_prefix_, coupler_qoi, "nan")
                redis_connection.hset(f"cs:{coupler}", node_name, "not_calibrated")
