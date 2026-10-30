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

from tergite_tuner.lib.nodes.characterization.purity_benchmarking.node import (
    DUMMY_UNITARITY,
)
from tergite_tuner.tests.utils.runs import run_dummy_node
from tergite_tuner.utils.types.node_enum import NodeEnum


@pytest.mark.slow
def test_a_dummy_run_recovers_the_dummy_unitarity(
    session_context, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    session = run_dummy_node(NodeEnum.PURITY_BENCHMARKING, session_context, tmp_path)

    for qubit in session.qubits:
        fidelity = session.state.read("transmons", qubit, "purity_fidelity")
        assert fidelity == pytest.approx(DUMMY_UNITARITY, abs=1e-6)
