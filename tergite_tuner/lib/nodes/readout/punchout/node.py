# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import numpy as np

from tergite_tuner.lib.base.node import QubitNode
from tergite_tuner.lib.nodes.readout.punchout.analysis import PunchoutNodeAnalysis
from tergite_tuner.lib.nodes.readout.punchout.measurement import PunchoutMeasurement
from tergite_tuner.lib.nodes.schedule_node import ScheduleNode
from tergite_tuner.lib.utils.samplespace import resonator_samples


class PunchoutNode(QubitNode):
    """
    This class implements the punchout node, which is used to measure the
    readout amplitude.
    """

    name: str = "punchout"
    measurement_cls = PunchoutMeasurement
    analysis_cls = PunchoutNodeAnalysis
    measurement_type_cls = ScheduleNode
    qubit_qois = ["measure:pulse_amp"]

    def __init__(self, all_qubits: list[str], **schedule_keywords):
        super().__init__(all_qubits, **schedule_keywords)

        self.schedule_samplespace = {
            "ro_frequencies": {
                qubit: resonator_samples(qubit, self.session)
                for qubit in self.all_qubits
            },
            "ro_amplitudes": {
                qubit: np.linspace(0.004, 0.1, 7) for qubit in self.all_qubits
            },
        }
