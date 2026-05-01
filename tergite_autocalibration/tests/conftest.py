# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Collection of shared fixtures for pytest to pick up"""

import numpy as np
import pytest

from tergite_autocalibration.config.session import SessionContext
from tergite_autocalibration.lib.nodes import NodeEnum
from tergite_autocalibration.utils.dto.enums import MeasurementMode


@pytest.fixture(scope="session")
def session_context() -> SessionContext:
    return SessionContext(
        cluster_mode=MeasurementMode.dummy,
        cluster_ip=None,
        target_node=NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
        qubits=["q00", "q01"],
        couplers=["q00_q01"],
        name="no_name_for_this_run_set",
        user_samplespace={
            "resonator_spectroscopy": {
                "ro_frequencies": {
                    "q00": np.linspace(4499999949.5, 4500000050.5, 101),
                    "q01": np.linspace(4899999949.5, 4900000050.5, 101),
                }
            },
        },
    )
