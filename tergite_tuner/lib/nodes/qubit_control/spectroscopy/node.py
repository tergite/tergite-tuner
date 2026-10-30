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
from tergite_tuner.lib.base.node import QubitNode
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.analysis import (
    QubitSpectroscopyNodeAnalysis,
    analyse_qubit_spectroscopy,
    plot_qubit_spectroscopy,
)
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.measurement import (
    TwoTonesAmplitudeMeasurement,
    TwoTonesMultidimMeasurement,
)
from tergite_tuner.lib.nodes.schedule_node import OuterScheduleNode
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.lib.utils.samplespace import qubit_samples
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

FREQUENCY_FIELDS = ("clock_freqs:f01", "clock_freqs:f12")
AMPLITUDE_FIELDS = ("spec:spec_ampl_optimal", "spec:spec_ampl_12_optimal")
AMPLITUDES = (np.linspace(1e-3, 8e-3, 5), np.linspace(6e-3, 3e-2, 3))
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


class Qubit01SpectroscopyAmplitudeNode(QubitNode):
    name: str = "qubit_bring_up_spectroscopy"
    measurement_cls = TwoTonesAmplitudeMeasurement
    analysis_cls = QubitSpectroscopyNodeAnalysis
    measurement_type_cls = OuterScheduleNode
    qubit_qois = ["clock_freqs:f01", "spec:spec_ampl_optimal"]

    def __init__(
        self,
        all_qubits: list[str],
        couplers: list[str],
        session: "SessionContext",
        **schedule_kwargs,
    ):
        super().__init__(all_qubits, couplers, session, **schedule_kwargs)

        self.outer_schedule_samplespace = {
            "spec_pulse_amplitudes": {
                qubit: np.linspace(8e-3, 8e-2, 2) for qubit in self.all_qubits
            },
        }

        self.schedule_samplespace = {
            "spec_frequencies": {
                qubit: self.qubit_samples(qubit) for qubit in self.all_qubits
            },
        }

    def qubit_samples(self, qubit: str) -> np.ndarray:
        qub_spec_samples = 821
        sweep_range = 500e6
        VNA_frequency = self.session.device_config.qubits[qubit]["VNA_f01_frequency"]
        min_freq = VNA_frequency - sweep_range / 2
        max_freq = VNA_frequency + sweep_range / 2
        return np.linspace(min_freq, max_freq, qub_spec_samples)
