# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman 2024
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
"""Ramsey fringes over artificial detunings, from 0 and from 1: each transition's frequency."""

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.qubit_control.ramsey_fringes.analysis import (
    analyse_ramsey,
    plot_ramsey,
)
from tergite_tuner.lib.nodes.qubit_control.ramsey_fringes.measurement import (
    RamseyDetuningsMeasurement,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.lib.utils.analysis_models import RamseyModel
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

FREQUENCY_FIELDS = ("clock_freqs:f01", "clock_freqs:f12")
# delays from 4 ns to 2 us, in steps of this many 8 ns clock cycles, per transition
DELAY_STEPS = (12, 8)
ARTIFICIAL_DETUNINGS = np.arange(-2.1, 2.1, 0.8) * 1e6
# how far the dummy qubit is detuned from its stored frequency
DUMMY_DETUNING = 200e3

ramsey = RamseyModel()


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    ramsey_delays: dict[str, np.ndarray],
    artificial_detunings: dict[str, np.ndarray],
    state: int,
) -> Schedule:
    """The Ramsey schedule: two pi-half pulses each delay apart, at each artificial detuning.

    Args:
        transmons: the qubits to measure, by name.
        ramsey_delays: each qubit's delays between the pulses, in seconds.
        artificial_detunings: each qubit's detunings of the drive from its frequency,
            in Hz.
        state: the state the transition starts from: 0 for 0-1, 1 for 1-2.

    Returns:
        The schedule.
    """
    return RamseyDetuningsMeasurement(transmons).schedule_function(
        artificial_detunings, ramsey_delays, qubit_state=state
    )


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    """Ramsey fringes of a qubit ``DUMMY_DETUNING`` from its stored frequency.

    Args:
        _qubit: unused; part of the ``get_dummy_s21`` signature.
        sweeps: the qubit's sweeps' values: ``ramsey_delays`` and
            ``artificial_detunings``.
        _session: unused; part of the ``get_dummy_s21`` signature.

    Returns:
        The qubit's S21, a row per delay and a column per artificial detuning.
    """
    columns = []
    for detuning in sweeps["artificial_detunings"]:
        params = ramsey.make_params(
            amplitude=0.2,
            frequency=np.abs(detuning - DUMMY_DETUNING),
            tau=80e-6,
            phase=0,
            offset=0,
        )
        columns.append(ramsey.eval(params=params, t=sweeps["ramsey_delays"]))
    return np.stack(columns, axis=1)


RAMSEY_SPECS = {
    name: NodeSpec(
        name=name,
        element="qubit",
        get_schedule=partial(get_schedule, state=state),
        analyse=partial(analyse_ramsey, frequency_field=FREQUENCY_FIELDS[state]),
        qois={"frequency": FREQUENCY_FIELDS[state]},
        sweeps={
            "ramsey_delays": get_fixed_sweep(
                np.arange(4e-9, 2048e-9, DELAY_STEPS[state] * 8e-9)
            ),
            "artificial_detunings": get_fixed_sweep(ARTIFICIAL_DETUNINGS),
        },
        get_dummy_s21=get_dummy_s21,
        plot=plot_ramsey,
    )
    for state, name in enumerate(
        (NodeEnum.RAMSEY_CORRECTION, NodeEnum.RAMSEY_CORRECTION_12)
    )
}
