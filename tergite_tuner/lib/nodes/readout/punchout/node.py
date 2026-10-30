# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Punchout: the readout amplitude to use."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.readout.punchout.analysis import (
    analyse_punchout,
    plot_punchout,
    save_punchout_spectroscopies,
)
from tergite_tuner.lib.nodes.readout.punchout.measurement import PunchoutMeasurement
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    get_dummy_s21 as get_dummy_resonator,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.lib.utils.samplespace import resonator_samples
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

AMPLITUDES = np.linspace(0.004, 0.1, 7)


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    ro_frequencies: dict[str, np.ndarray],
    ro_amplitudes: dict[str, np.ndarray],
) -> Schedule:
    return PunchoutMeasurement(transmons).schedule_function(
        ro_frequencies, ro_amplitudes
    )


def get_dummy_s21(
    qubit: str, sweeps: Mapping[str, np.ndarray], session: "SessionContext"
) -> np.ndarray:
    """The ground-state resonator, the same at every amplitude."""
    spectrum = get_dummy_resonator(qubit, sweeps, session, state=0)
    return np.tile(spectrum[:, None], (1, len(sweeps["ro_amplitudes"])))


PUNCHOUT_SPECS = {
    NodeEnum.PUNCHOUT: NodeSpec(
        name=NodeEnum.PUNCHOUT,
        element="qubit",
        get_schedule=get_schedule,
        analyse=analyse_punchout,
        qois={"amplitude": "measure:pulse_amp"},
        sweeps={
            "ro_frequencies": resonator_samples,
            "ro_amplitudes": get_fixed_sweep(AMPLITUDES),
        },
        get_dummy_s21=get_dummy_s21,
        plot=plot_punchout,
        save_details=save_punchout_spectroscopies,
    )
}
