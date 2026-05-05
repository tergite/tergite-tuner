# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for :mod:`tergite_tuner.utils.backend.reset_redis_node`."""

import pytest

from tergite_tuner.lib.nodes import __NODE_STR_CLS_MAP__
from tergite_tuner.utils.backend.reset_redis_node import (
    reset_all_redis_nodes,
    reset_redis_nodes,
)


def _put_value(redis_connection, key, field, value):
    redis_connection.hset(key, field, value)


def test_reset_redis_nodes_resets_qubit_qois_to_nan(redis_connection):
    """Plain qubit qois are reset to ``"nan"``."""
    qubits = ["q00", "q01"]
    couplers = ["q00_q01"]

    # Use a simple node with qubit qois
    node_name = "resonator_spectroscopy"
    node_cls = __NODE_STR_CLS_MAP__[node_name]

    # Pre-populate with bogus values
    for q in qubits:
        for qoi in node_cls.qubit_qois or []:
            _put_value(redis_connection, f"transmons:{q}", qoi, "999")

    reset_redis_nodes(qubits, couplers, [node_name], redis_connection)

    for q in qubits:
        for qoi in node_cls.qubit_qois or []:
            assert (
                redis_connection.hget(f"transmons:{q}", qoi) == "nan"
            ), f"qoi {qoi} on {q} not reset to nan"


def test_reset_redis_nodes_zeros_motzoi_qois(redis_connection):
    """Qois containing ``"motzoi"`` are reset to ``"0"`` rather than ``"nan"``."""
    qubits = ["q00"]
    couplers = []

    motzoi_node_name = next(
        (
            name
            for name, cls in __NODE_STR_CLS_MAP__.items()
            if getattr(cls, "qubit_qois", None)
            and any("motzoi" in q for q in cls.qubit_qois)
        ),
        None,
    )
    assert motzoi_node_name is not None, "no motzoi-bearing node registered"

    reset_redis_nodes(qubits, couplers, [motzoi_node_name], redis_connection)
    motzoi_qois = [
        q for q in __NODE_STR_CLS_MAP__[motzoi_node_name].qubit_qois if "motzoi" in q
    ]
    for qoi in motzoi_qois:
        assert redis_connection.hget("transmons:q00", qoi) == "0"


def test_reset_redis_nodes_marks_not_calibrated(redis_connection):
    """Each reset node is flagged as ``not_calibrated`` in ``cs:<element>``."""
    qubits = ["q00", "q01"]
    couplers = []
    node_name = "resonator_spectroscopy"

    reset_redis_nodes(qubits, couplers, [node_name], redis_connection)

    for q in qubits:
        assert redis_connection.hget(f"cs:{q}", node_name) == "not_calibrated"


def test_reset_redis_nodes_resets_coupler_qois(redis_connection):
    """Coupler qois are reset to ``"nan"`` and the supervisor flag is set."""
    couplers = ["q00_q01"]
    qubits = []

    coupler_node = next(
        (
            (name, cls)
            for name, cls in __NODE_STR_CLS_MAP__.items()
            if getattr(cls, "coupler_qois", None)
        ),
        None,
    )
    assert coupler_node is not None, "no coupler-qoi node registered"
    node_name, node_cls = coupler_node

    reset_redis_nodes(qubits, couplers, [node_name], redis_connection)

    for c in couplers:
        for qoi in node_cls.coupler_qois:
            assert redis_connection.hget(f"couplers:{c}", qoi) == "nan"
        assert redis_connection.hget(f"cs:{c}", node_name) == "not_calibrated"


def test_reset_all_redis_nodes_calls_each_registered_node(redis_connection):
    """``reset_all_redis_nodes`` flags every registered node as not calibrated.

    The function dispatches to ``reset_redis_nodes`` with every entry
    in ``__NODE_STR_CLS_MAP__``, so every node should appear in the
    ``cs:q00`` hash for at least the qubit-bearing nodes.
    """
    qubits = ["q00"]
    couplers = ["q00_q01"]

    reset_all_redis_nodes(qubits, couplers, redis_connection)

    cs_q00 = {k: v for k, v in redis_connection.hgetall("cs:q00").items()}
    qubit_node_names = [
        name
        for name, cls in __NODE_STR_CLS_MAP__.items()
        if getattr(cls, "qubit_qois", None)
    ]
    for name in qubit_node_names:
        assert cs_q00.get(name) == "not_calibrated"
