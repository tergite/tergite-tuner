# This code is part of Tergite
#
# (C) Chalmers Next Labs AB 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from itertools import product

import pytest

from tergite_tuner.lib.nodes import DEFAULT_NODE_NAME_CLS_MAP
from tergite_tuner.lib.nodes.schedule_node import OuterScheduleNode
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.redis import loaded_redis
from tergite_tuner.utils.measurement import (
    reduce_samplespace,
    samplespace_dimensions,
)
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon

_redis_values = get_fixture_path("redis", "standard_redis_mock.json")
_node_names = list(DEFAULT_NODE_NAME_CLS_MAP.keys())


@pytest.mark.parametrize("node_name", _node_names)
def test_precompile_all_nodes_without_error(
    node_name, redis_connection, session_context
):
    with loaded_redis(redis_connection, _redis_values):
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        node_cls = DEFAULT_NODE_NAME_CLS_MAP[node_name]
        node = node_cls(
            all_qubits=["q00", "q01"],
            couplers=["q00_q01"],
            session=session_context,
        )

        if node_name == "purity_benchmarking":
            pytest.skip(
                "We skip purity_benchmarking for now, because it needs some refactoring."
            )

        if issubclass(node.measurement_type_cls, OuterScheduleNode):
            # The assembly of samplespaces is taken from the OuterScheduleNode
            outer_dimensions = samplespace_dimensions(node.outer_schedule_samplespace)
            iterations = product(*(range(n) for n in outer_dimensions))
            for this_iteration in iterations:
                reduced_outer_samplespace = reduce_samplespace(
                    this_iteration, node.outer_schedule_samplespace
                )
                samplespace = node.schedule_samplespace | reduced_outer_samplespace
                node.precompile(samplespace)

        else:
            node.precompile(node.schedule_samplespace)
