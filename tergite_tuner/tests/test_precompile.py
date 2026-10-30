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


from quantify_scheduler.backends.qblox import constants as qblox_constants

from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import get_compiler
from tergite_tuner.tests.utils.state import loaded_state

_state_file = get_fixture_path("states", "standard_state.json")


def test_precompile_restores_the_grid_time_tolerance(session_context):
    default_tolerance = qblox_constants.GRID_TIME_TOLERANCE_TIME
    with loaded_state(session_context, _state_file):
        get_compiler("punchout", session_context)()

    assert qblox_constants.GRID_TIME_TOLERANCE_TIME == default_tolerance
