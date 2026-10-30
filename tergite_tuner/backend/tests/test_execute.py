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


import pytest

from tergite_tuner.backend.execute import run_schedule


class _Coordinator:
    def __init__(self, prepare_error: Exception | None = None):
        self.prepare_error = prepare_error
        self.waited = None

    def prepare(self, _compiled_schedule):
        if self.prepare_error:
            raise self.prepare_error

    def start(self):
        pass

    def wait_done(self, timeout_sec):
        self.waited = timeout_sec

    def retrieve_acquisition(self):
        return "acquisitions"

    def stop(self):
        pass


def test_an_instrument_error_reaches_the_caller():
    coordinator = _Coordinator(ValueError("nco_freq out of range"))
    with pytest.raises(ValueError, match="nco_freq"):
        run_schedule(coordinator, compiled_schedule=None, timeout=1)


def test_run_schedule_waits_at_most_the_timeout_and_returns_the_acquisitions():
    coordinator = _Coordinator()
    assert run_schedule(coordinator, compiled_schedule=None, timeout=12.5) == (
        "acquisitions"
    )
    assert coordinator.waited == 12.5
