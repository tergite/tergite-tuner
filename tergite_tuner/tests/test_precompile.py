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


import pytest
from quantify_scheduler.backends.qblox import constants as qblox_constants

from tergite_tuner.backend import ExtendedTransmon, configure_device
from tergite_tuner.lib import run
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import get_compiler
from tergite_tuner.tests.utils.state import loaded_state
from tergite_tuner.utils.types.node_enum import NodeEnum

_state_file = get_fixture_path("states", "standard_state.json")
# purity benchmarking cannot be built (step 9.7)
_OUTER_NODES = [
    node
    for node, spec in DEFAULT_NODE_SPECS.items()
    if spec.outer_sweeps and node != NodeEnum.PURITY_BENCHMARKING
]


# every outer-sweep point: test_schedule_goldens.py compiles the first one on every run
@pytest.mark.slow
@pytest.mark.parametrize("node", _OUTER_NODES, ids=lambda node: node.value)
def test_every_outer_point_compiles(node, session_context):
    spec = DEFAULT_NODE_SPECS[node]
    session = session_context.model_copy(update={"user_samplespace": {}})
    with loaded_state(session, _state_file):
        ExtendedTransmon.close_all()
        device = configure_device(
            node.value, run.get_qubits(spec, session), session.couplers, session
        )
        sweeps = run.get_sweeps(spec, session)
        for point in run.get_points(run.get_outer_sweeps(spec, session)):
            run.compile_node(spec, device, sweeps | point, session)


def test_precompile_restores_the_grid_time_tolerance(session_context):
    default_tolerance = qblox_constants.GRID_TIME_TOLERANCE_TIME
    with loaded_state(session_context, _state_file):
        get_compiler("punchout", session_context)()

    assert qblox_constants.GRID_TIME_TOLERANCE_TIME == default_tolerance
