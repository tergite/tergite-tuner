# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2026
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Stefan Hill 2024
# (C) Copyright Abdullah Al Amin 2026
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import math
from typing import Literal, Optional

from qblox_scheduler.enums import BinMode
from qblox_scheduler.operations.gate_library import Measure, Rxy
from qblox_scheduler.structure.model import Numbers, Parameter, SchedulerSubmodule

_AcqProtocol = Literal[
    "SSBIntegrationComplex",
    "Trace",
    "TriggerCount",
    "NumericalWeightedIntegrationComplex",
    "ThresholdedAcquisition",
]


class ExtendedClocksFrequencies(SchedulerSubmodule):
    readout_1: float = Parameter(
        label="Readout frequency when qubit is at |1>",
        unit="Hz",
        initial_value=math.nan,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )
    readout_2: float = Parameter(
        label="Readout frequency when qubit is at |2>",
        unit="Hz",
        initial_value=math.nan,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )
    readout_2state_opt: float = Parameter(
        label="Optimal Readout frequency for discriminating |0>,|1>",
        unit="Hz",
        initial_value=math.nan,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )
    readout_3state_opt: float = Parameter(
        label="Optimal Readout frequency for discriminating |0>,|1>, |2>",
        unit="Hz",
        initial_value=math.nan,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )


class R12(SchedulerSubmodule):
    """
    Submodule containing parameters for performing an R12 operations
    """

    ef_amp180: float = Parameter(
        label=r"$\pi-pulse amplitude for 12$",
        initial_value=math.nan,
        vals=Numbers(min_value=-10, max_value=10, allow_nan=True),
    )
    # quantify-scheduler's D_amp of the DRAG pulse; see motzoi_to_beta
    ef_motzoi: float = Parameter(
        initial_value=0.0,
        vals=Numbers(min_value=-1, max_value=1),
    )
    ef_duration: float = Parameter(
        initial_value=20e-9,
        unit="s",
        vals=Numbers(min_value=0, max_value=1),
    )


class Spec(SchedulerSubmodule):
    """
    Submodule containing parameters for performing qubit spectroscopy measurements
    """

    spec_amp: float = Parameter(
        label=r"amplitude for the qubit spectroscopy pulse",
        initial_value=math.nan,
        vals=Numbers(min_value=-1, max_value=1, allow_nan=True),
    )
    spec_ampl_optimal: float = Parameter(
        label=r"optimal spectroscopy amplitude to be used in coupler anticrossing",
        initial_value=math.nan,
        vals=Numbers(min_value=-1, max_value=1, allow_nan=True),
    )
    spec_ampl_12_optimal: float = Parameter(
        label=r"optimal spectroscopy amplitude to be used in coupler anticrossing",
        initial_value=math.nan,
        vals=Numbers(min_value=-1, max_value=1, allow_nan=True),
    )
    spec_duration: float = Parameter(
        initial_value=20e-9,
        unit="s",
        vals=Numbers(min_value=0, max_value=1e-3, allow_nan=True),
    )


class Rxy_12(Rxy):
    """
    A single qubit rotation on the 12 transition.
    """

    def __init__(self, qubit: str, theta: float = 180, phi: float = 0):
        super().__init__(theta=theta, phi=phi, qubit=qubit)
        self.data["name"] = f"Rxy-12({theta:.8g}, {phi:.8g}, '{qubit}')"
        self.data["gate_info"]["unitary"] = None  # this is not a Qubit operation
        # this key is used in compilation!
        self.data["gate_info"]["operation_type"] = "r12"

    def __str__(self) -> str:
        qubit = self.data["gate_info"]["device_elements"][0]
        return f"{self.__class__.__name__}(qubit='{qubit}')"


class Measure_RO1(Measure):
    _operation_type = "measure_1"
    _tex = r"$\langle0|$"

    def __init__(
        self,
        *qubits: str,
        coords: dict | None = None,
        acq_protocol: Optional[_AcqProtocol] = None,
        bin_mode: BinMode | None = None,
        feedback_trigger_label: Optional[str] = None,
    ):
        super().__init__(
            qubits[0],
            coords=coords,
            acq_protocol=acq_protocol,
            bin_mode=bin_mode,
            feedback_trigger_label=feedback_trigger_label,
        )
        self.data["name"] = f"{self.__class__.__name__} {', '.join(qubits)}"
        self.data["gate_info"].update(
            tex=self._tex,
            device_elements=list(qubits),
            operation_type=self._operation_type,
        )


class Measure_RO2(Measure_RO1):
    _operation_type = "measure_2"


class Measure_RO_3state_Opt(Measure_RO1):
    _operation_type = "measure_3state_opt"
    _tex = r"$\langle opt|$"


class Measure_RO_2state_Opt(Measure_RO1):
    _operation_type = "measure_2state_opt"
    _tex = r"$\langle opt|$"
