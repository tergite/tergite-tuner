# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from tergite_tuner.lib.utils.schedules import get_multiplexed_schedule


def test_points_vary_the_first_setting_fastest_and_count_acquisitions_per_qubit():
    calls = []
    get_multiplexed_schedule(
        "test",
        {"q1": None, "q2": None},
        {
            "frequencies": {"q1": [1, 2], "q2": [5, 6]},
            "amplitudes": {"q1": [0.1, 0.2], "q2": [0.3, 0.4]},
        },
        lambda _schedule, qubit, point, acq_index: calls.append(
            (qubit, point["frequencies"], point["amplitudes"], acq_index)
        ),
        repetitions=1,
    )

    assert calls == [
        ("q1", 1, 0.1, 0),
        ("q1", 2, 0.1, 1),
        ("q1", 1, 0.2, 2),
        ("q1", 2, 0.2, 3),
        ("q2", 5, 0.3, 0),
        ("q2", 6, 0.3, 1),
        ("q2", 5, 0.4, 2),
        ("q2", 6, 0.4, 3),
    ]
