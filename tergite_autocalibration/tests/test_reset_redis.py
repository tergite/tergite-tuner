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

from tergite_autocalibration.tests.utils.decorators import loaded_redis
from tergite_autocalibration.tests.utils.fixtures import get_fixture_path
from tergite_autocalibration.utils.backend.reset_redis_node import (
    reset_all_redis_nodes,
    reset_redis_nodes,
)

_redis_values = get_fixture_path("redis", "standard_redis_mock.json")


def test_simple_reset_redis_nodes(redis_connection):
    with loaded_redis(redis_connection, _redis_values):
        assert redis_connection.hget("cs:q00", "resonator_spectroscopy") == "calibrated"
        assert (
            redis_connection.hget("transmons:q00", "clock_freqs:readout")
            == "6826375232.52066"
        )
        assert redis_connection.hget("transmons:q00", "Ql") == "14852.044429629796"
        assert (
            redis_connection.hget("transmons:q00", "resonator_minimum")
            == "6826355555.555555"
        )

        assert redis_connection.hget("cs:q01", "resonator_spectroscopy") == "calibrated"
        assert (
            redis_connection.hget("transmons:q01", "clock_freqs:readout")
            == "6411557868.710736"
        )
        assert redis_connection.hget("cs:q00", "qubit_01_spectroscopy") == "calibrated"

        reset_redis_nodes(
            ["q00", "q01"],
            ["q00_q01"],
            ["resonator_spectroscopy", "qubit_01_spectroscopy"],
            redis_connection,
        )

        assert (
            redis_connection.hget("cs:q00", "resonator_spectroscopy")
            == "not_calibrated"
        )
        assert redis_connection.hget("transmons:q00", "clock_freqs:readout") == "nan"
        assert redis_connection.hget("transmons:q00", "Ql") == "nan"
        assert redis_connection.hget("transmons:q00", "resonator_minimum") == "nan"
        assert (
            redis_connection.hget("cs:q01", "resonator_spectroscopy")
            == "not_calibrated"
        )
        assert redis_connection.hget("transmons:q01", "clock_freqs:readout") == "nan"
        assert (
            redis_connection.hget("cs:q00", "qubit_01_spectroscopy") == "not_calibrated"
        )


def test_simple_reset_all_redis_nodes(redis_connection):
    with loaded_redis(redis_connection, _redis_values):
        assert redis_connection.hget("cs:q00", "resonator_spectroscopy") == "calibrated"
        assert (
            redis_connection.hget("transmons:q00", "rxy:motzoi")
            == "-0.05384615384615388"
        )
        assert (
            redis_connection.hget("transmons:q00", "measure_3state_opt:pulse_amp")
            == "0.04821428571428571"
        )
        assert (
            redis_connection.hget("transmons:q00", "measure_2state_opt:pulse_amp")
            == "0.035539772727272725"
        )

        reset_all_redis_nodes(["q00", "q01"], ["q00_q01"], redis_connection)

        assert (
            redis_connection.hget("cs:q00", "resonator_spectroscopy")
            == "not_calibrated"
        )
        assert redis_connection.hget("transmons:q00", "rxy:motzoi") == "0"
        assert (
            redis_connection.hget("transmons:q00", "measure_3state_opt:pulse_amp")
            == "0"
        )
        assert (
            redis_connection.hget("transmons:q00", "measure_2state_opt:pulse_amp")
            == "0"
        )
