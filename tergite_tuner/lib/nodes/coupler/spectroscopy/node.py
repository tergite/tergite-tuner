# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Michele Faucci Giannelli 2024, 2025
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Qubit and resonator spectroscopy against each coupler's current: where the coupler crosses them."""

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np
from lmfit.models import LorentzianModel

from tergite_tuner.lib.nodes.coupler.spectroscopy.analysis import (
    CouplerAnticrossingAnalysis,
    ResonatorSpectroscopyVsCurrentCouplerAnalysis,
)
from tergite_tuner.lib.nodes.coupler.utils import reset_dc_currents, set_dc_currents
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.measurement import (
    TwoTonesMultidimMeasurement,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.measurement import (
    ResonatorSpectroscopyMeasurement,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    get_dummy_s21 as get_dummy_resonator,
)
from tergite_tuner.lib.spec import (
    NodeSpec,
    get_class_schedule,
    get_coupler_analyser,
    get_fixed_sweep,
    save_coupler_figures,
)
from tergite_tuner.lib.utils.samplespace import qubit_samples, resonator_samples
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

QUBIT_CURRENTS = np.arange(-2e-3, 2e-3, 80e-6)
RESONATOR_CURRENTS = np.arange(-1e-3, 1e-3, 50e-6)
# the dummy coupler crosses the qubit near these currents, offset to avoid dividing by zero
DUMMY_ASYMPTOTES = np.array([-0.001, 0.001]) + 3 / 5 * 1e-7

peak = LorentzianModel()


def get_dummy_anticrossing(
    qubit: str, sweeps: Mapping[str, np.ndarray], session: "SessionContext"
) -> np.ndarray:
    """A qubit peak the coupler pushes away as its current nears the asymptotes."""
    low, high = DUMMY_ASYMPTOTES
    current = sweeps["dc_currents"]
    frequency = session.device_config.qubits[qubit]["VNA_f01_frequency"]
    frequency += 2e6 * np.abs(low * high) / (current - low) / (current - high)
    params = peak.make_params(amplitude=0.2, center=frequency, sigma=0.1e6)
    return peak.eval(params=params, x=sweeps["spec_frequencies"])


def get_dummy_resonator_vs_current(
    qubit: str, sweeps: Mapping[str, np.ndarray], session: "SessionContext"
) -> np.ndarray:
    return get_dummy_resonator(qubit, sweeps, session, state=0)


COUPLER_ANTICROSSING_SPEC = NodeSpec(
    name=NodeEnum.COUPLER_ANTICROSSING,
    element="coupler",
    get_schedule=get_class_schedule(TwoTonesMultidimMeasurement),
    analyse=get_coupler_analyser(CouplerAnticrossingAnalysis),
    qois={
        "control_qubit_crossing_points": "control_qubit_crossing_points",
        "target_qubit_crossing_points": "target_qubit_crossing_points",
    },
    sweeps={"spec_frequencies": qubit_samples},
    get_dummy_s21=get_dummy_anticrossing,
    schedule_keywords={"qubit_state": 0},
    qubit_sweeps=frozenset({"spec_frequencies"}),
    external_sweeps={"dc_currents": get_fixed_sweep(QUBIT_CURRENTS)},
    set_external=set_dc_currents,
    reset_external=reset_dc_currents,
    save_details=save_coupler_figures,
)

COUPLER_SPECTROSCOPY_SPECS = {
    NodeEnum.RESONATOR_SPECTROSCOPY_VS_CURRENT: NodeSpec(
        name=NodeEnum.RESONATOR_SPECTROSCOPY_VS_CURRENT,
        element="coupler",
        get_schedule=get_class_schedule(ResonatorSpectroscopyMeasurement),
        analyse=get_coupler_analyser(ResonatorSpectroscopyVsCurrentCouplerAnalysis),
        qois={
            "control_resonator_crossing_points": "control_resonator_crossing_points",
            "target_resonator_crossing_points": "target_resonator_crossing_points",
        },
        sweeps={"ro_frequencies": resonator_samples},
        get_dummy_s21=get_dummy_resonator_vs_current,
        qubit_sweeps=frozenset({"ro_frequencies"}),
        external_sweeps={"dc_currents": get_fixed_sweep(RESONATOR_CURRENTS)},
        set_external=set_dc_currents,
        reset_external=reset_dc_currents,
        save_details=save_coupler_figures,
    ),
    NodeEnum.COUPLER_ANTICROSSING: COUPLER_ANTICROSSING_SPEC,
    # the same measurement, after resonator spectroscopy vs current in the graph
    NodeEnum.QUBIT_SPECTROSCOPY_VS_CURRENT: dataclasses.replace(
        COUPLER_ANTICROSSING_SPEC, name=NodeEnum.QUBIT_SPECTROSCOPY_VS_CURRENT
    ),
}
