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

import networkx as nx
import pytest

from tergite_tuner import run_node
from tergite_tuner.config.types import SpiConfig
from tergite_tuner.lib.nodes import (
    DEFAULT_IGNORED_NODES,
    DEFAULT_NODE_CLS_MAP,
    DEFAULT_NODE_DAG_EDGES,
)
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.redis import loaded_redis
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon
from tergite_tuner.utils.types.node_enum import NodeEnum

_REDIS_VALUES = get_fixture_path("redis", "standard_redis_mock.json")
# the fixture spi_config.toml wires q06 to q25, not the session's coupler
_SPI_CONFIG = SpiConfig.model_validate(
    {"q00_q01": {"spi_module_number": 1, "dac_name": "dac0", "edge_group": 1}}
)
# each fails on a defect REFACTOR.md lists; strict, so a fix fails the test until removed
_KNOWN_FAILURES = {
    NodeEnum.QUBIT_01_SPECTROSCOPY: "five 6 us spectroscopy amplitudes overflow the waveform memory",
    NodeEnum.ALL_XY: "AllXY cannot run (step 9.7)",
    NodeEnum.PURITY_BENCHMARKING: "purity benchmarking cannot run (step 9.7)",
    NodeEnum.CZ_CHEVRON: "the CZ chevron analysis raises on data it cannot fit",
}
_DEFAULT_NODES = [
    pytest.param(
        node,
        id=node.value,
        marks=(
            [pytest.mark.xfail(reason=_KNOWN_FAILURES[node], strict=True)]
            if node in _KNOWN_FAILURES
            else []
        ),
    )
    for node in nx.topological_sort(nx.DiGraph(DEFAULT_NODE_DAG_EDGES))
    if node not in DEFAULT_IGNORED_NODES
]


@pytest.mark.slow
@pytest.mark.parametrize("node", _DEFAULT_NODES)
def test_every_default_node_runs_in_dummy_mode(
    node, redis_connection, session_context, tmp_path
):
    session = session_context.model_copy(
        update={
            "data_dir": tmp_path,
            "ignore_spec": True,
            "is_recalibration": True,
            "spi_config": _SPI_CONFIG,
            "user_samplespace": {},
        }
    )
    with loaded_redis(redis_connection, _REDIS_VALUES):
        ExtendedTransmon.close_all()
        run_node(node, session=session, refresh_session=False)

    # analyses of random IQ points may fail; reaching them without raising is the check
    node_name = DEFAULT_NODE_CLS_MAP[node].name
    assert (tmp_path / f"dataset_{node_name}.hdf5").exists()
