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

from collections import Counter

import numpy as np

from tergite_tuner.backend import (
    ExtendedCompositeSquareEdge,
    ExtendedTransmon,
)
from tergite_tuner.lib.nodes.coupler.cz_parametrization.measurement import (
    CZParametrizationMeasurement,
)


def test_each_coupler_excites_only_its_own_qubits():
    ExtendedTransmon.close_all()
    couplers = ["q00_q01", "q02_q03"]
    transmons = {q: ExtendedTransmon(q) for c in couplers for q in c.split("_")}
    edges = {}
    for coupler in couplers:
        control, target = coupler.split("_")
        edges[coupler] = ExtendedCompositeSquareEdge(control, target)
        edges[coupler].cz.half_square_duration(100e-9)

    schedule = CZParametrizationMeasurement(transmons, edges).cz_parametrization(
        cz_pulse_frequencies={c: np.array([1e6, 2e6]) for c in couplers},
        cz_pulse_amplitudes={c: np.array([0.1, 0.2, 0.3]) for c in couplers},
    )

    operations = [
        schedule.operations[schedulable["operation_id"]]
        for schedulable in schedule.schedulables.values()
    ]
    excitations = Counter(
        qubit
        for operation in operations
        if operation["name"].startswith("X ")
        for qubit in operation["gate_info"]["device_elements"]
    )
    assert excitations == {q: 2 * 3 for q in transmons}
