# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Readout frequency optimization for two and for three states."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    get_dummy_s21 as get_dummy_resonator,
)
from tergite_tuner.lib.nodes.readout.ro_frequency_optimization.analysis import (
    analyse_ro_frequency,
    plot_three_state_ro_frequency,
    plot_two_state_ro_frequency,
)
from tergite_tuner.lib.nodes.readout.ro_frequency_optimization.measurement import (
    ROFrequencyOptimizationMeasurement,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.lib.utils.samplespace import resonator_samples
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    ro_opt_frequencies: dict[str, np.ndarray],
    qubit_states: dict[str, np.ndarray],
) -> Schedule:
    return ROFrequencyOptimizationMeasurement(transmons).schedule_function(
        ro_opt_frequencies, qubit_states
    )


def get_dummy_s21(
    qubit: str, sweeps: Mapping[str, np.ndarray], session: "SessionContext"
) -> np.ndarray:
    """The resonator with the qubit in each state, as resonator spectroscopy's dummy shifts it."""
    frequencies = {"ro_frequencies": sweeps["ro_opt_frequencies"]}
    return np.stack(
        [
            get_dummy_resonator(qubit, frequencies, session, state=int(state))
            for state in sweeps["qubit_states"]
        ],
        axis=1,
    )


RO_FREQUENCY_SPECS = {
    name: NodeSpec(
        name=name,
        element="qubit",
        get_schedule=get_schedule,
        analyse=analyse_ro_frequency,
        qois={"frequency": field},
        sweeps={
            "ro_opt_frequencies": resonator_samples,
            "qubit_states": get_fixed_sweep(np.arange(states, dtype=np.int8)),
        },
        get_dummy_s21=get_dummy_s21,
        plot=plot,
        plot_rows=rows,
    )
    for name, field, states, plot, rows in (
        (
            NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
            "extended_clock_freqs:readout_2state_opt",
            2,
            plot_two_state_ro_frequency,
            3,
        ),
        (
            NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
            "extended_clock_freqs:readout_3state_opt",
            3,
            plot_three_state_ro_frequency,
            1,
        ),
    )
}
