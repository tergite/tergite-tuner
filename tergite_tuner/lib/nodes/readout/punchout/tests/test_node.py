# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.lib.nodes.readout.punchout.node import PunchoutNode
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)


def test_punchout_node_can_be_initialized(session_context):
    ExtendedTransmon.close_all()
    node = PunchoutNode(
        all_qubits=DEFAULT_TEST_QUBITS,
        couplers=DEFAULT_TEST_COUPLERS,
        session=session_context,
    )

    assert node.name == "punchout"
    assert node.redis_fields == ["measure:pulse_amp"]
