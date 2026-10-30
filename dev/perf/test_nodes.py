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

from typing import Any

import pytest

from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.lib.nodes import DEFAULT_NODE_CLS_MAP, DEFAULT_NODE_NAME_CLS_MAP
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import (
    RECORDED_DATASETS,
    copy_dataset,
    get_dataset_path,
    get_first_external_point,
    get_first_samplespace,
    get_qois,
    get_redis_file,
)
from tergite_tuner.tests.utils.redis import loaded_redis

REDIS_VALUES = get_fixture_path("redis", "standard_redis_mock.json")
# purity benchmarking cannot be built (step 9.7)
NODE_NAMES = [
    name for name in DEFAULT_NODE_NAME_CLS_MAP if name != "purity_benchmarking"
]


@pytest.mark.parametrize("node_name", NODE_NAMES)
def test_compile(measure, node_name, redis_connection, session_context):
    with loaded_redis(redis_connection, REDIS_VALUES):
        node = _get_node(node_name, session_context)
        samplespace = get_first_samplespace(node)
        measure(lambda: node.precompile(samplespace))


@pytest.mark.parametrize("node_name", NODE_NAMES)
def test_dataset(measure, node_name, redis_connection, session_context):
    with loaded_redis(redis_connection, REDIS_VALUES):
        node = _get_node(node_name, session_context)
        node.reduced_external_samplespace = get_first_external_point(node)
        raw_dataset = node.generate_dummy_dataset()
        measure(lambda: node.configure_dataset(raw_dataset))


@pytest.mark.parametrize("case", RECORDED_DATASETS)
def test_analysis(measure, case, redis_connection, session_context, tmp_path):
    golden_case = RECORDED_DATASETS[case]
    node_cls = DEFAULT_NODE_CLS_MAP[golden_case.node]
    copy_dataset(
        get_dataset_path(golden_case.dataset),
        tmp_path / f"dataset_{node_cls.name}.hdf5",
    )

    def analyse() -> dict:
        analysis = node_cls.analysis_cls(
            name=node_cls.name,
            redis_fields=get_qois(node_cls),
            session=session_context,
            **golden_case.analysis_keywords,
        )
        return analysis.analyze_node(tmp_path, save_plot=True)

    with loaded_redis(redis_connection, get_redis_file(golden_case)):
        measure(analyse)


def _get_node(node_name: str, session_context) -> Any:
    ExtendedTransmon.close_all()
    return DEFAULT_NODE_NAME_CLS_MAP[node_name](
        all_qubits=["q00", "q01"], couplers=["q00_q01"], session=session_context
    )
