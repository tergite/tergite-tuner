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

import pytest

from tergite_tuner.tests.utils.fixtures import (
    get_fixture_path,
)
from tergite_tuner.tests.utils.goldens import DEFAULT_NODE_NAMES, get_dataset_builder
from tergite_tuner.tests.utils.state import loaded_state

_REDIS_VALUES = get_fixture_path("redis", "standard_redis_mock.json")


@pytest.mark.parametrize("node_name", DEFAULT_NODE_NAMES)
def test_every_node_has_a_dummy_dataset_it_can_configure(node_name, session_context):
    with loaded_state(session_context, _REDIS_VALUES):
        dataset = get_dataset_builder(node_name, session_context)()

    assert dataset.data_vars
