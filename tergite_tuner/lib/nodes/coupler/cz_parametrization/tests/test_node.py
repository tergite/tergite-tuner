# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Eleftherios Moschandreou 2025
# (C) Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import pytest

from tergite_tuner.lib.nodes.coupler.cz_parametrization.node import (
    CZ_PARAMETRIZATION_SPECS,
)
from tergite_tuner.lib.run import get_external_sweeps, get_sweeps, validate_couplers
from tergite_tuner.utils.types.node_enum import NodeEnum

SPEC = CZ_PARAMETRIZATION_SPECS[NodeEnum.CZ_PARAMETRIZATION]
COUPLER = "q14_q15"


@pytest.fixture
def coupler_session(session_context):
    session_context.state.load(
        {
            "couplers": {
                COUPLER: {
                    "initial_parking_current": 100e-6,
                    "cz_phase_path": "via_20",
                    "control_qubit": "q15",
                    "target_qubit": "q14",
                }
            },
            "transmons": {
                "q14": {"clock_freqs:f01": 4.2e6, "clock_freqs:f12": 4.0e6},
                "q15": {"clock_freqs:f01": 5.2e6, "clock_freqs:f12": 5.0e6},
            },
        }
    )
    return session_context.model_copy(
        update={"couplers": [COUPLER], "user_samplespace": {}}
    )


def test_a_missing_parking_current_raises(coupler_session):
    coupler_session.state.load(
        {"couplers": {COUPLER: {"initial_parking_current": None}}}
    )

    with pytest.raises(TypeError):
        get_external_sweeps(SPEC, coupler_session)


def test_the_current_is_the_initial_parking_current(coupler_session):
    assert get_external_sweeps(SPEC, coupler_session)["dc_currents"][COUPLER] == [
        pytest.approx(100e-6)
    ]


def test_frequencies_sweep_around_the_cz_transition(coupler_session):
    frequencies = get_sweeps(SPEC, coupler_session)["cz_pulse_frequencies"][COUPLER]

    # via_20: the target's f01 less the control's f12, rounded down to 10 kHz
    assert frequencies[0] == pytest.approx(0.8e6 - 10e6)
    assert frequencies[-1] == pytest.approx(0.8e6 + 4e6)


@pytest.mark.parametrize("couplers", [["q14_q14"], ["q14_q15", "q15_q16"]])
def test_couplers_sharing_a_qubit_are_refused(couplers):
    with pytest.raises(ValueError):
        validate_couplers(couplers)
