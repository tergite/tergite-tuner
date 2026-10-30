# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2026
# (C) Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import numpy as np
import pytest

from tergite_tuner.backend import ExtendedTransmon, configure_device
from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking import (
    measurement as tqg_measurement,
)
from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.measurement import (
    CZRBMeasurement,
)
from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.utils.two_qubit_clifford_group import (
    TwoQubitClifford,
)
from tergite_tuner.tests.utils.state import loaded_state


def test_align_cliffords(session_context, node_data_dir):
    redis_data_file = node_data_dir / "redis-2026-02-10-11-23-12.json"
    with loaded_state(session_context, redis_data_file):
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        qubits = ["q13", "q14"]
        couplers = ["q13_q14"]
        clifford_gate_index = 9799

        device = configure_device("cz_rb", qubits, couplers, session_context)
        transmons_dict = {qubit: device.get_element(qubit) for qubit in qubits}
        edges_dict = {coupler: device.get_edge(coupler) for coupler in couplers}
        cz_rb_measurement = CZRBMeasurement(
            transmons=transmons_dict, couplers=edges_dict
        )

        cliff_gate_decomposition = TwoQubitClifford(
            clifford_gate_index
        ).gate_decomposition

        assert cliff_gate_decomposition == [
            ("mY90", "q0"),
            ("X90", "q0"),
            ("I", "q1"),
            ("CZ", ["q0", "q1"]),
            ("Y90", "q0"),
            ("mY90", "q1"),
            ("CZ", ["q0", "q1"]),
            ("mX90", "q0"),
            ("Y180", "q0"),
            ("mY90", "q1"),
        ]

        grouped_gate_decomposition = cz_rb_measurement.align_cliffords(
            couplers[0], cliff_gate_decomposition
        )

        assert grouped_gate_decomposition == [
            {"q0": ["mY90", "X90"], "q1": ["I", "I"]},
            {"q13_q14": ["CZ"]},
            {"q0": ["Y90"], "q1": ["mY90"]},
            {"q13_q14": ["CZ"]},
            {"q0": ["mX90", "Y180"], "q1": ["I", "mY90"]},
        ]


def _get_rb_measurement(session_context, node_data_dir, couplers):
    redis_data_file = node_data_dir / "redis-2026-02-10-11-23-12.json"
    with loaded_state(session_context, redis_data_file):
        ExtendedTransmon.close_all()
        qubits = sorted({q for coupler in couplers for q in coupler.split("_")})
        device = configure_device("cz_rb", qubits, couplers, session_context)
        transmons = {qubit: device.get_element(qubit) for qubit in qubits}
        edges = {coupler: device.get_edge(coupler) for coupler in couplers}
    return CZRBMeasurement(transmons=transmons, couplers=edges)


def test_only_interleaved_modes_interleave_the_cz(
    session_context, node_data_dir, monkeypatch
):
    coupler = "q13_q14"
    measurement = _get_rb_measurement(session_context, node_data_dir, [coupler])
    interleaved_ids = []

    def _record_sequence(*args, interleaved_clifford_idx=None, **kwargs):
        interleaved_ids.append(interleaved_clifford_idx)
        return np.array([0])

    monkeypatch.setattr(
        tqg_measurement, "randomized_benchmarking_sequence", _record_sequence
    )

    measurement.ro_shot(
        seeds={coupler: 1},
        number_of_cliffords={coupler: np.array([1, 2])},
        interleave_modes={coupler: np.array([True, False])},
        apply_inverse_gate=True,
        coupler_dict={coupler: {"control_qubit": "q13", "target_qubit": "q14"}},
    )

    assert interleaved_ids == [4368, 4368, None, None]


def test_rb_rejects_more_than_one_coupler(session_context, node_data_dir):
    couplers = ["q13_q14", "q15_q16"]
    measurement = _get_rb_measurement(session_context, node_data_dir, couplers)

    with pytest.raises(ValueError, match="one coupler"):
        measurement.ro_shot(
            seeds={c: 1 for c in couplers},
            number_of_cliffords={c: np.array([1]) for c in couplers},
            interleave_modes={c: np.array([False]) for c in couplers},
            apply_inverse_gate=True,
            coupler_dict={
                c: dict(zip(("control_qubit", "target_qubit"), c.split("_")))
                for c in couplers
            },
        )
