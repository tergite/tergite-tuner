# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
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
"""T2 and T2 echo: each qubit's dephasing times, averaged over repetitions."""

from collections.abc import Callable, Mapping
from functools import partial
from typing import TYPE_CHECKING

import lmfit
import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.characterization.t2.analysis import (
    T2Model,
    analyse_decay,
    plot_decay,
)
from tergite_tuner.lib.nodes.characterization.t2.measurement import (
    T2EchoMeasurement,
    T2Measurement,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep, get_waits_between_points
from tergite_tuner.lib.utils.fitting_models import ExpDecayModel
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

T2_DELAYS = 8e-9 + np.arange(0, 150e-6, 5e-6)
ECHO_DELAYS = 8e-9 + np.concatenate(
    [
        np.arange(0, 40e-6, 10e-6),
        np.arange(40e-6, 100e-6, 20e-6),
        np.arange(100e-6, 400e-6, 50e-6),
        np.arange(400e-6, 900e-6, 100e-6),
        np.arange(900e-6, 1500e-6, 200e-6),
    ]
)
REPETITIONS = 3
SECONDS_BETWEEN_REPETITIONS = 3
# the dummy qubit's fringes, in microseconds
DUMMY_T2_US, DUMMY_FREQUENCY_PER_US = 60, 0.05

t2_model = T2Model()
echo_model = ExpDecayModel()


def get_t2_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    delays: dict[str, np.ndarray],
    multiplexing: str,
) -> Schedule:
    return T2Measurement(transmons).schedule_function(delays, multiplexing)


def get_echo_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    delays: dict[str, np.ndarray],
    multiplexing: str,
) -> Schedule:
    return T2EchoMeasurement(transmons).schedule_function(delays, multiplexing)


def get_dummy_t2(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    delays = sweeps["delays"] * 1e6
    fringes = np.cos(2 * np.pi * DUMMY_FREQUENCY_PER_US * delays)
    return 1e-4 * (1 + fringes * np.exp(-delays / DUMMY_T2_US))


def get_dummy_echo(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return 1e-3 * np.exp(-sweeps["delays"] * 1e6 / (4 * DUMMY_T2_US)) + 1e-4


def _get_spec(
    name: NodeEnum,
    field: str,
    label: str,
    get_schedule: Callable[..., Schedule],
    delays: np.ndarray,
    model: lmfit.Model,
    time_parameter: str,
    guess_variable: str,
    get_dummy_s21: Callable[..., np.ndarray],
) -> NodeSpec:
    decay = {
        "model": model,
        "time_parameter": time_parameter,
        "repetitions_coord": "repeat",
    }
    return NodeSpec(
        name=name,
        element="qubit",
        get_schedule=get_schedule,
        analyse=partial(analyse_decay, **decay, guess_variable=guess_variable),
        qois={"time": field},
        sweeps={"delays": get_fixed_sweep(delays)},
        get_dummy_s21=get_dummy_s21,
        plot=partial(
            plot_decay,
            **decay,
            label=label,
            should_show_spread=name == NodeEnum.T2_ECHO,
        ),
        schedule_keywords={"multiplexing": "one_by_one"},
        external_sweeps={"repeat": get_fixed_sweep(np.arange(REPETITIONS))},
        set_external=get_waits_between_points(SECONDS_BETWEEN_REPETITIONS),
    )


T2_SPECS = {
    spec.name: spec
    for spec in (
        _get_spec(
            NodeEnum.T2,
            "t2_time",
            "T2",
            get_t2_schedule,
            T2_DELAYS,
            t2_model,
            "x0",
            "x",
            get_dummy_t2,
        ),
        _get_spec(
            NodeEnum.T2_ECHO,
            "t2_echo_time",
            "T2 Echo",
            get_echo_schedule,
            ECHO_DELAYS,
            echo_model,
            "tau",
            "delay",
            get_dummy_echo,
        ),
    )
}
