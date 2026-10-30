# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""The store round trips of a dummy run of each node: a command, or a pipeline, is one.

Run by dev/perf/record.sh, which writes the counts with ``--perf-json``.
"""

from collections.abc import Callable
from typing import Any

import pytest
from redis.client import Pipeline

from tergite_tuner.tests.utils import runs
from tergite_tuner.utils.types.node_enum import NodeEnum

# they cannot run (REFACTOR.md lists each)
FAILING_NODES = {
    NodeEnum.QUBIT_01_SPECTROSCOPY,
    NodeEnum.ALL_XY,
    NodeEnum.PURITY_BENCHMARKING,
}
NODES = [node for node in runs.DEFAULT_NODES if node not in FAILING_NODES]


@pytest.mark.parametrize("node", NODES, ids=lambda node: node.value)
def test_store_round_trips(
    record_measures, node, redis_connection, session_context, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    round_trips = []
    run_node = runs.run_node

    def count_run_node(*args: Any, **kwargs: Any) -> Any:
        with monkeypatch.context() as counting:
            counting.setattr(
                redis_connection,
                "execute_command",
                _count(redis_connection.execute_command, round_trips),
            )
            counting.setattr(Pipeline, "execute", _count(Pipeline.execute, round_trips))
            return run_node(*args, **kwargs)

    monkeypatch.setattr(runs, "run_node", count_run_node)
    runs.run_dummy_node(node, redis_connection, session_context, tmp_path)

    record_measures({"store_round_trips": len(round_trips)})


def _count(call: Callable[..., Any], round_trips: list[None]) -> Callable[..., Any]:
    def counted(*args: Any, **kwargs: Any) -> Any:
        round_trips.append(None)
        return call(*args, **kwargs)

    return counted
