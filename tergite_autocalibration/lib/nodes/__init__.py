# This code is part of Tergite
#
# (C) Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Entry point for the nodes module"""

from enum import Enum


class NodeEnum(int, Enum):
    """an enumeration of all the nodes in their order"""

    PUNCHOUT = 0
    RESONATOR_SPECTROSCOPY = 1
    QUBIT_01_SPECTROSCOPY = 2
    RABI_OSCILLATIONS = 3
    RAMSEY_CORRECTION = 4
    RESONATOR_SPECTROSCOPY_1 = 5
    QUBIT_12_SPECTROSCOPY = 6
    RABI_OSCILLATIONS_12 = 7
    RAMSEY_CORRECTION_12 = 8
    RESONATOR_SPECTROSCOPY_2 = 9
    RO_FREQUENCY_TWO_STATE_OPTIMIZATION = 10
    RO_FREQUENCY_THREE_STATE_OPTIMIZATION = 11
    RO_AMPLITUDE_TWO_STATE_OPTIMIZATION = 12
    RO_AMPLITUDE_THREE_STATE_OPTIMIZATION = 13
    RESONATOR_SPECTROSCOPY_VS_CURRENT = 14
    QUBIT_SPECTROSCOPY_VS_CURRENT = 15
    T1 = 16
    T2 = 17
    T2_ECHO = 18
    RANDOMIZED_BENCHMARKING_SSRO = 19
    ALL_XY = 20
    CHECK_CLIFFORDS = 21
    CZ_CHEVRON = 22
    CZ_CHEVRON_TEST = 23
    CZ_CHEVRON_AMPLITUDE = 24
    CZ_OPTIMIZE_CHEVRON = 25
    RESET_CHEVRON = 26
    RESET_CALIBRATION_SSRO = 27
    CZ_CALIBRATION = 28
    CZ_CALIBRATION_SSRO = 29
    CZ_DYNAMIC_PHASE = 30
    CZ_DYNAMIC_PHASE_SWAP = 31
    PROCESS_TOMOGRAPHY_SSRO = 32
    TQG_RANDOMIZED_BENCHMARKING = 33
    TQG_RANDOMIZED_BENCHMARKING_INTERLEAVED = 34

    @classmethod
    def from_string(cls, string) -> "NodeEnum":
        """Gets the NodeEnum given a string"""
        return cls[string.upper()]

    def to_string(self) -> str:
        """Converts the NodeEnum to a string"""
        return str(self.name).lower()
