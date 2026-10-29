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

from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    ResonatorSpectroscopyNode,
)
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon


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
