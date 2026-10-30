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

from types import SimpleNamespace

import pytest

from tergite_tuner.lib.utils.schedule_execution import execute_schedule
from tergite_tuner.utils.types.enums import MeasurementMode


class _RefusingCoordinator:
    def prepare(self, _compiled_schedule):
        raise ValueError("nco_freq out of range")


def test_an_instrument_error_reaches_the_caller():
    with pytest.raises(ValueError, match="nco_freq"):
        execute_schedule(
            SimpleNamespace(name="schedule"),
            schedule_duration=0,
            lab_ic=_RefusingCoordinator(),
            cluster_status=MeasurementMode.dummy,
        )
