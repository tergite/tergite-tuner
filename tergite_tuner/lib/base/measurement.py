# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Stefan Hill 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


class BaseMeasurement:
    """Base of the measurements that build a node's schedule over its transmons and couplers."""

    def __init__(self, transmons: dict, couplers=None):
        if couplers is None:
            couplers = {}
        self.transmons = transmons
        self.couplers = couplers
        self.qubits = list(self.transmons.keys())
