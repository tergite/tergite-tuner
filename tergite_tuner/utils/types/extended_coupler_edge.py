# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
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
from typing import Dict, Literal

from qblox_scheduler.backends.graph_compilation import OperationCompilationConfig
from qblox_scheduler.device_under_test.edge import Edge
from qblox_scheduler.operations import pulse_factories
from qblox_scheduler.structure.model import Numbers, Parameter, SchedulerSubmodule

from tergite_tuner.utils.types.extended_pulse_factories import (
    composite_soft_square_pulse,
)


class Spec(SchedulerSubmodule):
    """
    Submodule containing parameters for performing qubit spectroscopy measurements
    """

    coupler_spec_amp: float = Parameter(
        label=r"amplitude for the coupler spectroscopy pulse",
        initial_value=math.nan,
        vals=Numbers(min_value=-10, max_value=10, allow_nan=True),
    )


class CZ(SchedulerSubmodule):
    """
    Submodule containing parameters for performing a CZ operation
    """

    square_amp: float = Parameter(
        docstring=r"""Amplitude of the square envelope.""",
        unit="V",
        initial_value=0.1,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )
    square_duration: float = Parameter(
        docstring=r"""The square pulse duration in seconds.""",
        unit="s",
        initial_value=200e-9,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )
    half_square_duration: float = Parameter(
        docstring=r"""Half duration of the flux pulse for initial sweeps.""",
        unit="s",
        initial_value=200e-9,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )
    cz_width: float = Parameter(
        docstring=r"""AC flux pulse rising and lowering edge width""",
        initial_value=4e-9,
        unit="s",
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )
    parent_phase_correction: float = Parameter(
        docstring=r"""The phase correction for the parent qubit after the"""
        r""" square pulse operation has been performed.""",
        unit="degrees",
        initial_value=0.0,
        vals=Numbers(min_value=-1e12, max_value=1e12, allow_nan=True),
    )
    child_phase_correction: float = Parameter(
        docstring=r"""The phase correction for the parent qubit after the"""
        r""" square pulse operation has been performed.""",
        unit="degrees",
        initial_value=0.0,
        vals=Numbers(min_value=-1e12, max_value=1e12, allow_nan=True),
    )
    dc_flux_0: float = Parameter(
        docstring=r"""\Phi_{{0}}: DC flux quanta for the coupler tunability""",
        initial_value=0.0,
        unit="A",
        vals=Numbers(min_value=-3e-3, max_value=3e-3, allow_nan=True),
    )
    dc_flux_offset: float = Parameter(
        label=r"DC flux offset for the coupler tunability",
        initial_value=0.0,
        unit="A",
        vals=Numbers(min_value=-3e-3, max_value=3e-3, allow_nan=True),
    )
    edge_group: float = Parameter(
        label=r"Group assignment for the edge",
        initial_value=0.0,
        vals=Numbers(min_value=-10, max_value=10, allow_nan=True),
    )


class CouplerParameters(SchedulerSubmodule):
    """
    Submodule containing parameters related to the coupler operation
    """

    parking_current: float = Parameter(
        docstring=r"""DC current that creates the flux to bias the coupler""",
        initial_value=0.0,
        unit="A",
        vals=Numbers(min_value=-3e-3, max_value=3e-3, allow_nan=True),
    )
    initial_parking_current: float = Parameter(
        docstring=r"""helper parameter that holds an initial value for the DC current""",
        initial_value=0.0,
        unit="A",
        vals=Numbers(min_value=-3e-3, max_value=3e-3, allow_nan=True),
    )
    phase_path: Literal["via_20", "via_02"] | None = Parameter(
        docstring=r"""The path outside the compuational space where the sate goes to acqure a controlled phase""",
        unit="NA",
        initial_value=None,
    )


class EdgeClocksFrequencies(SchedulerSubmodule):
    cz_freq: float = Parameter(
        docstring=r"""AC flux frequency for a CZ gate""",
        unit="Hz",
        initial_value=100e6,
        vals=Numbers(min_value=0, max_value=1e12, allow_nan=True),
    )


class ExtendedCompositeSquareEdge(Edge):
    """
    An example Edge implementation which connects two BasicTransmonElements within a
    QuantumDevice. This edge implements a square flux pulse and two virtual z
    phase corrections for the CZ operation between the two BasicTransmonElements.
    """

    edge_type: Literal["ExtendedCompositeSquareEdge"] = "ExtendedCompositeSquareEdge"
    cz: CZ
    coupler_parameters: CouplerParameters
    spec: Spec
    clock_freqs: EdgeClocksFrequencies

    def generate_edge_config(self) -> Dict[str, Dict[str, OperationCompilationConfig]]:
        """
        Fills in the edges information to produce a valid device config for the
        qblox-scheduler making use of the
        :func:`~.circuit_to_device._compile_circuit_to_device` function.
        """
        return {
            self.name: {
                "CZ": OperationCompilationConfig(
                    factory_func=composite_soft_square_pulse,
                    factory_kwargs={
                        "square_port": self.name + ":fl",
                        "square_clock": self.name + ".cz",
                        "square_amp": self.cz.square_amp,
                        "square_duration": self.cz.square_duration,
                        "virt_z_parent_qubit_phase": self.cz.parent_phase_correction,
                        "virt_z_parent_qubit_clock": f"{self.parent_element_name}.01",
                        "virt_z_child_qubit_phase": self.cz.child_phase_correction,
                        "virt_z_child_qubit_clock": f"{self.child_element_name}.01",
                    },
                ),
                "spec": OperationCompilationConfig(
                    factory_func=pulse_factories.rxy_drag_pulse,
                    factory_kwargs={
                        "coupler_spec_amp": self.spec.coupler_spec_amp,
                    },
                    gate_info_factory_kwargs=["theta", "phi"],
                ),
            }
        }
