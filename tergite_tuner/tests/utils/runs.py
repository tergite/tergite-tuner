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

from pathlib import Path

import networkx as nx
import numpy as np

from tergite_tuner import run_node
from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.config.session import SessionContext
from tergite_tuner.config.types import SpiConfig
from tergite_tuner.lib.nodes import DEFAULT_IGNORED_NODES, DEFAULT_NODE_DAG_EDGES
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.state import (
    loaded_state,
    set_drive_frequencies_from_device,
)
from tergite_tuner.utils.types.node_enum import NodeEnum

DUMMY_REDIS_VALUES = get_fixture_path("redis", "standard_redis_mock.json")
# the fixture spi_config.toml wires q06 to q25, not the session's coupler
DUMMY_SPI_CONFIG = SpiConfig.model_validate(
    {"q00_q01": {"spi_module_number": 1, "dac_name": "dac0", "edge_group": 1}}
)
DEFAULT_NODES = [
    node
    for node in nx.topological_sort(nx.DiGraph(DEFAULT_NODE_DAG_EDGES))
    if node not in DEFAULT_IGNORED_NODES
]


def run_dummy_node(
    node: NodeEnum,
    session_context: SessionContext,
    data_dir: Path,
    keep_data_files: bool = True,
) -> None:
    """Recalibrates ``node`` alone on the dummy cluster, from the standard recorded values."""
    session = session_context.model_copy(
        update={
            "data_dir": data_dir,
            "ignore_spec": True,
            "is_recalibration": True,
            "spi_config": DUMMY_SPI_CONFIG,
            "user_samplespace": {},
        }
    )
    with loaded_state(session, DUMMY_REDIS_VALUES):
        set_drive_frequencies_from_device(session.state, session.device_config)
        # nodes' own dummy generators draw from numpy's global generator
        np.random.seed(0)
        ExtendedTransmon.close_all()
        run_node(
            node,
            session=session,
            refresh_session=False,
            keep_data_files=keep_data_files,
        )
