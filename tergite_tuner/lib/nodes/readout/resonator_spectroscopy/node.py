# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
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
"""Resonator spectroscopy with the qubit in 0, 1 and 2: each state's readout frequency."""

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.analysis import (
    analyse_resonator,
    plot_resonator,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.measurement import (
    ResonatorSpectroscopyMeasurement,
)
from tergite_tuner.lib.spec import NodeSpec
from tergite_tuner.lib.utils import fitting_models as fm
from tergite_tuner.lib.utils.samplespace import resonator_samples
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

NAMES = (
    NodeEnum.RESONATOR_SPECTROSCOPY,
    NodeEnum.RESONATOR_SPECTROSCOPY_1,
    NodeEnum.RESONATOR_SPECTROSCOPY_2,
)
QOIS = (
    {"frequency": "clock_freqs:readout", "Ql": "Ql", "minimum": "resonator_minimum"},
    {
        "frequency": "extended_clock_freqs:readout_1",
        "Ql": "Ql_1",
        "minimum": "resonator_minimum_1",
    },
    {"frequency": "extended_clock_freqs:readout_2"},
)
# how far below its VNA frequency the dummy resonator sits, with the qubit in each state
DUMMY_SHIFTS = (0, 0.5e6, 1e6)

resonator = fm.ResonatorModel()


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    ro_frequencies: dict[str, np.ndarray],
    state: int,
) -> Schedule:
    """The resonator spectroscopy schedule, with each qubit prepared in ``state``.

    Args:
        transmons: the qubits' transmons by name.
        ro_frequencies: each qubit's readout frequencies.
        state: the state to prepare each qubit in: 0, 1 or 2.

    Returns:
        The schedule.
    """
    return ResonatorSpectroscopyMeasurement(transmons).schedule_function(
        ro_frequencies, qubit_state=state
    )


def get_dummy_s21(
    qubit: str,
    sweeps: Mapping[str, np.ndarray],
    session: "SessionContext",
    state: int,
) -> np.ndarray:
    """A resonator below the qubit's VNA frequency, shifted further for each higher ``state``.

    Args:
        qubit: the qubit.
        sweeps: the readout frequencies.
        session: the session whose device config holds the VNA frequency.
        state: the qubit's state: 0, 1 or 2.

    Returns:
        S21 at each readout frequency.
    """
    frequency = session.device_config.resonators[qubit]["VNA_frequency"]
    params = resonator.make_params(
        fr=frequency - DUMMY_SHIFTS[state],
        Ql=15000,
        Qe=20000,
        A=0.01,
        theta=0.5,
        phi_v=0,
        phi_0=0,
    )
    return resonator.eval(params=params, f=sweeps["ro_frequencies"])


RESONATOR_SPECTROSCOPY_SPECS = {
    NAMES[state]: NodeSpec(
        name=NAMES[state],
        element="qubit",
        get_schedule=partial(get_schedule, state=state),
        analyse=analyse_resonator,
        qois=QOIS[state],
        sweeps={"ro_frequencies": resonator_samples},
        get_dummy_s21=partial(get_dummy_s21, state=state),
        plot=partial(plot_resonator, state=state),
    )
    for state in range(3)
}
