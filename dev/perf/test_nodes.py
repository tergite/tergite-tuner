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
"""Time and peak memory of each node's compile, dataset assembly and analysis.

Run by dev/perf/record.sh, which writes the measurements with ``--perf-json``.
"""

import pytest

from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import (
    DEFAULT_NODE_NAMES,
    RECORDED_DATASETS,
    get_analyser,
    get_compiler,
    get_dataset_builder,
    get_redis_file,
)
from tergite_tuner.tests.utils.state import loaded_state

REDIS_VALUES = get_fixture_path("redis", "standard_redis_mock.json")
# purity benchmarking cannot be built (step 9.7)
NODE_NAMES = [name for name in DEFAULT_NODE_NAMES if name != "purity_benchmarking"]


@pytest.mark.parametrize("node_name", NODE_NAMES)
def test_compile(measure, node_name, session_context):
    with loaded_state(session_context, REDIS_VALUES):
        measure(get_compiler(node_name, session_context))


@pytest.mark.parametrize("node_name", NODE_NAMES)
def test_dataset(measure, node_name, session_context):
    with loaded_state(session_context, REDIS_VALUES):
        measure(get_dataset_builder(node_name, session_context))


@pytest.mark.parametrize("case", RECORDED_DATASETS)
def test_analysis(measure, case, session_context, tmp_path):
    golden_case = RECORDED_DATASETS[case]
    analyse = get_analyser(
        golden_case, tmp_path, session_context, should_save_plot=True
    )
    with loaded_state(session_context, get_redis_file(golden_case)):
        measure(analyse)
