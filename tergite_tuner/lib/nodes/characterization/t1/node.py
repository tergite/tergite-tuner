# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Liangyu Chen 2024
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
"""T1: each qubit's relaxation time, averaged over repetitions."""

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.characterization.t1.measurement import T1Measurement
from tergite_tuner.lib.nodes.characterization.t2.analysis import (
    analyse_decay,
    plot_decay,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep, get_waits_between_points
from tergite_tuner.lib.utils.fitting_models import ExpDecayModel
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

DELAYS = 8e-9 + np.concatenate(
    [
        np.arange(0, 4e-6, 1e-6),
        np.arange(4e-6, 10e-6, 2e-6),
        np.arange(10e-6, 40e-6, 5e-6),
        np.arange(40e-6, 100e-6, 10e-6),
        np.arange(100e-6, 200e-6, 20e-6),
        np.arange(200e-6, 400e-6, 40e-6),
    ]
)
REPETITIONS = 5
SECONDS_BETWEEN_REPETITIONS = 1
DUMMY_T1 = 60e-6

model = ExpDecayModel()

DECAY = {
    "model": model,
    "time_parameter": "tau",
    "repetitions_coord": "T1_repetitions",
}


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    delays: dict[str, np.ndarray],
    multiplexing: str,
) -> Schedule:
    return T1Measurement(transmons).schedule_function(delays, multiplexing)


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return 1e-3 * np.exp(-sweeps["delays"] / DUMMY_T1) + 1e-4


T1_SPECS = {
    NodeEnum.T1: NodeSpec(
        name=NodeEnum.T1,
        element="qubit",
        get_schedule=get_schedule,
        analyse=partial(analyse_decay, **DECAY, guess_variable="delay"),
        qois={"time": "t1_time"},
        sweeps={"delays": get_fixed_sweep(DELAYS)},
        get_dummy_s21=get_dummy_s21,
        plot=partial(plot_decay, **DECAY, label="T1", should_show_spread=True),
        schedule_keywords={"multiplexing": "parallel"},
        external_sweeps={"T1_repetitions": get_fixed_sweep(np.arange(REPETITIONS))},
        set_external=get_waits_between_points(SECONDS_BETWEEN_REPETITIONS),
    )
}
