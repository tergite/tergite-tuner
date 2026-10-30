# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023
# (C) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from enum import Enum


class MeasurementMode(Enum):
    """
    Used to set the cluster mode e.g.  real cluster or re analyse
    """

    real = 0
    dummy = 1
    re_analyse = 2


class SPIMode(Enum):
    """
    Used to set the cluster mode e.g.  real cluster or re analyse
    """

    real = 0
    dummy = 1


class QubitRole(Enum):
    """
    Defines whether a qubit is target or control for a given coupler
    """

    TARGET = "TARGET"
    CONTROL = "CONTROL"
    NOTSET = "NOTSET"
