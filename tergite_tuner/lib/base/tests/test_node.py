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

import matplotlib
import pytest

from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.lib.nodes import DEFAULT_NODE_NAME_CLS_MAP
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    ResonatorSpectroscopyNode,
)
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
    get_fixture_path,
)
from tergite_tuner.tests.utils.goldens import get_first_external_point
from tergite_tuner.tests.utils.redis import loaded_redis

_REDIS_VALUES = get_fixture_path("redis", "standard_redis_mock.json")


@pytest.mark.parametrize("save_plot", [True, False])
def test_node_keeps_the_callers_matplotlib_backend(session_context, save_plot):
    ExtendedTransmon.close_all()
    original_backend = matplotlib.get_backend()
    matplotlib.use("pdf")
    session = session_context.model_copy(update={"save_plot": save_plot})

    try:
        ResonatorSpectroscopyNode(
            DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session
        )
        assert matplotlib.get_backend() == "pdf"
    finally:
        matplotlib.use(original_backend)


@pytest.mark.parametrize("node_name", list(DEFAULT_NODE_NAME_CLS_MAP))
def test_every_node_has_a_dummy_dataset_it_can_configure(
    node_name, redis_connection, session_context
):
    with loaded_redis(redis_connection, _REDIS_VALUES):
        ExtendedTransmon.close_all()
        node = DEFAULT_NODE_NAME_CLS_MAP[node_name](
            all_qubits=["q00", "q01"], couplers=["q00_q01"], session=session_context
        )
        node.reduced_external_samplespace = get_first_external_point(node)

        dataset = node.configure_dataset(node.generate_dummy_dataset())

    assert dataset.data_vars
