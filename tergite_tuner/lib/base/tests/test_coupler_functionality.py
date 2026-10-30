# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025, 2026
# (C) Copyright Eleftherios Moschandreou 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


from tergite_tuner.lib.nodes.coupler.cz_chevron.node import CZChevronNode
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
    get_fixture_path,
)
from tergite_tuner.tests.utils.redis import loaded_redis
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon

redis_mock = get_fixture_path("redis", "standard_redis_mock.json")


class DummySpiManager:
    def __init__(self):
        self._currents_dict = None  # internal storage

    def set_dac_current(self, currents_dict: dict):
        self._currents_dict = currents_dict

    def get_dac_current(self) -> dict | None:
        return self._currents_dict


def test_set_parking_current_from_redis_recalibration_on(
    redis_connection, session_context
):
    """Set parking currents does nothing if is_recalibration is True."""
    session_context.is_recalibration = True
    with loaded_redis(redis_connection, redis_mock):
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        node = CZChevronNode(
            couplers=DEFAULT_TEST_COUPLERS,
            qubits=DEFAULT_TEST_QUBITS,
            session=session_context,
        )
        node.spi_manager = DummySpiManager()

        node.set_parking_current_from_redis()
        assert node.spi_manager.get_dac_current() is None


def test_set_parking_current_from_redis_recalibration_off(
    redis_connection, session_context
):
    """Sets parking currents in redis if is_recalibration is False."""
    # set recalibration false to ensure currents are set
    session_context.is_recalibration = False
    with loaded_redis(redis_connection, redis_mock):
        # currents are set only when is_recalibration is False
        session_context.is_recalibration = False
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        node = CZChevronNode(
            couplers=DEFAULT_TEST_COUPLERS,
            qubits=DEFAULT_TEST_QUBITS,
            session=session_context,
        )
        node.spi_manager = DummySpiManager()

        node.set_parking_current_from_redis()
        currents_dict = node.spi_manager.get_dac_current()
        assert "q00_q01" in currents_dict
        assert currents_dict["q00_q01"] == 0.00095


def test_set_parking_current_from_redis_recalibration(
    redis_connection, session_context
):
    """Currents are set only when is_recalibration is False"""
    with loaded_redis(redis_connection, redis_mock):
        # currents are set only when is_recalibration is False
        session_context.is_recalibration = True
        ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
        node = CZChevronNode(
            couplers=DEFAULT_TEST_COUPLERS,
            qubits=DEFAULT_TEST_QUBITS,
            session=session_context,
        )
        node.spi_manager = DummySpiManager()

        node.set_parking_current_from_redis()
        assert node.spi_manager.get_dac_current() is None
