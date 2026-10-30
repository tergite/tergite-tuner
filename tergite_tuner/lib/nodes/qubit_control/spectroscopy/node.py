# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Liangyu Chen 2023, 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from lmfit.models import LorentzianModel

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.analysis import (
    analyse_qubit_spectroscopy,
    plot_qubit_spectroscopy,
)
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.measurement import (
    TwoTonesAmplitudeMeasurement,
    TwoTonesMultidimMeasurement,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.lib.utils.samplespace import qubit_samples
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

FREQUENCY_FIELDS = ("clock_freqs:f01", "clock_freqs:f12")
AMPLITUDE_FIELDS = ("spec:spec_ampl_optimal", "spec:spec_ampl_12_optimal")
AMPLITUDES = (np.linspace(1e-3, 8e-3, 5), np.linspace(6e-3, 3e-2, 3))
BRING_UP_AMPLITUDES = np.linspace(8e-3, 8e-2, 2)
BRING_UP_WIDTH, BRING_UP_POINTS = 500e6, 821
VNA_FIELDS = ("VNA_f01_frequency", "VNA_f12_frequency")

peak = LorentzianModel()


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    spec_pulse_amplitudes: dict[str, np.ndarray],
    spec_frequencies: dict[str, np.ndarray],
    state: int,
) -> Schedule:
    return TwoTonesMultidimMeasurement(transmons).schedule_function(
        spec_frequencies, spec_pulse_amplitudes, qubit_state=state
    )


def get_dummy_s21(
    qubit: str,
    sweeps: Mapping[str, np.ndarray],
    session: "SessionContext",
    state: int,
) -> np.ndarray:
    """A peak at the qubit's VNA frequency, the same at every amplitude."""
    frequency = session.device_config.qubits[qubit][VNA_FIELDS[state]]
    params = peak.make_params(amplitude=0.2, center=frequency, sigma=0.1e6)
    spectrum = peak.eval(params=params, x=sweeps["spec_frequencies"])
    return np.tile(spectrum, (len(sweeps["spec_pulse_amplitudes"]), 1))


def get_bring_up_frequencies(qubit: str, session: "SessionContext") -> np.ndarray:
    """``BRING_UP_POINTS`` frequencies over ``BRING_UP_WIDTH`` around the qubit's VNA f01."""
    centre = session.device_config.qubits[qubit]["VNA_f01_frequency"]
    return np.linspace(
        centre - BRING_UP_WIDTH / 2, centre + BRING_UP_WIDTH / 2, BRING_UP_POINTS
    )


def get_bring_up_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    spec_frequencies: dict[str, np.ndarray],
    spec_pulse_amplitudes: dict[str, float],
) -> Schedule:
    return TwoTonesAmplitudeMeasurement(transmons).schedule_function(
        spec_frequencies, spec_pulse_amplitudes
    )


def get_dummy_bring_up(
    qubit: str, sweeps: Mapping[str, np.ndarray], session: "SessionContext"
) -> np.ndarray:
    """A peak at the qubit's VNA f01, at the one amplitude of the run."""
    frequency = session.device_config.qubits[qubit][VNA_FIELDS[0]]
    params = peak.make_params(amplitude=0.2, center=frequency, sigma=0.1e6)
    return peak.eval(params=params, x=sweeps["spec_frequencies"])


QUBIT_SPECTROSCOPY_SPECS = {
    name: NodeSpec(
        name=name,
        element="qubit",
        get_schedule=partial(get_schedule, state=state),
        analyse=analyse_qubit_spectroscopy,
        qois={
            "frequency": FREQUENCY_FIELDS[state],
            "amplitude": AMPLITUDE_FIELDS[state],
        },
        sweeps={
            "spec_pulse_amplitudes": get_fixed_sweep(AMPLITUDES[state]),
            "spec_frequencies": partial(
                qubit_samples, transition=f"{state}{state + 1}"
            ),
        },
        get_dummy_s21=partial(get_dummy_s21, state=state),
        plot=plot_qubit_spectroscopy,
    )
    for state, name in enumerate(
        (NodeEnum.QUBIT_01_SPECTROSCOPY, NodeEnum.QUBIT_12_SPECTROSCOPY)
    )
}
QUBIT_SPECTROSCOPY_SPECS[NodeEnum.QUBIT_BRING_UP_SPECTROSCOPY] = NodeSpec(
    name=NodeEnum.QUBIT_BRING_UP_SPECTROSCOPY,
    element="qubit",
    get_schedule=get_bring_up_schedule,
    analyse=partial(
        analyse_qubit_spectroscopy, amplitude_coord="spec_pulse_amplitudes"
    ),
    qois={"frequency": FREQUENCY_FIELDS[0], "amplitude": AMPLITUDE_FIELDS[0]},
    sweeps={"spec_frequencies": get_bring_up_frequencies},
    get_dummy_s21=get_dummy_bring_up,
    plot=plot_qubit_spectroscopy,
    outer_sweeps={"spec_pulse_amplitudes": get_fixed_sweep(BRING_UP_AMPLITUDES)},
)
