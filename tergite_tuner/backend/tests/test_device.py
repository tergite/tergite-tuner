# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2026
# (C) Chalmers Next Labs AB 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import math
import os

import pytest
from qcodes.instrument import Instrument
from quantify_scheduler.device_under_test.transmon_element import (
    BasicTransmonElement,
)

from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.backend.device import (
    close_device_resources,
    configure_device,
    open_node_device,
    save_serial_device,
)
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
    get_fixture_path,
)
from tergite_tuner.tests.utils.hardware import open_host_device
from tergite_tuner.tests.utils.state import loaded_state

state_file = get_fixture_path("states", "standard_state.json")


def test_create_serial_device(session_context):
    with loaded_state(session_context, state_file):
        # ensure no other transmon objects are instantiated
        # this is because some other test doesn't close the device properly
        ExtendedTransmon.close_all()
        device_name = "test_device"
        test_device = configure_device(
            device_name,
            qubits=DEFAULT_TEST_QUBITS,
            couplers=DEFAULT_TEST_COUPLERS,
            session=session_context,
        )

        q00 = test_device.get_element("q00")
        pi_amplitude = q00.rxy.amp180()
        q00_q01 = test_device.get_edge("q00_q01")
        initial_parking_current = q00_q01.coupler_parameters.parking_current()
        cz_phase_path = q00_q01.coupler_parameters.phase_path()

        assert test_device.elements() == DEFAULT_TEST_QUBITS
        assert test_device.edges() == DEFAULT_TEST_COUPLERS

        assert math.isclose(pi_amplitude, 0.7308488204080522)
        assert math.isclose(initial_parking_current, 0.00065)
        assert cz_phase_path == "via_20"

        close_device_resources(test_device)


def test_a_device_of_one_qubit_leaves_out_its_couplers(session_context):
    """Ramsey 12 runs on one qubit at a time, with the session's couplers"""
    with loaded_state(session_context, state_file):
        ExtendedTransmon.close_all()
        test_device = configure_device(
            "test_device",
            qubits=DEFAULT_TEST_QUBITS[:1],
            couplers=DEFAULT_TEST_COUPLERS,
            session=session_context,
        )

        assert test_device.edges() == []
        test_device.generate_compilation_config()

        close_device_resources(test_device)


def test_save_serial_device(tmp_path, session_context):
    with loaded_state(session_context, state_file):
        # ensure no other transmon objects are instantiated
        # this is because some other test doesn't close the device properly
        ExtendedTransmon.close_all()
        device_name = "test_device"
        test_device = configure_device(
            device_name,
            qubits=DEFAULT_TEST_QUBITS,
            couplers=DEFAULT_TEST_COUPLERS,
            session=session_context,
        )
        save_serial_device(test_device, data_path=tmp_path)

    assert os.path.exists(os.path.join(tmp_path, f"{device_name}.json"))

    close_device_resources(test_device)


def test_open_node_device_runs_on_the_host_elements(session_context):
    ExtendedTransmon.close_all()
    with (
        loaded_state(session_context, state_file),
        open_host_device(DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS) as host_device,
        open_node_device(
            "node",
            DEFAULT_TEST_QUBITS,
            DEFAULT_TEST_COUPLERS,
            session_context,
            host_device,
        ) as device,
    ):
        q01 = device.get_element("q01")
        q00_q01 = device.get_edge("q00_q01")

        assert q01 is host_device.get_element("q01")
        assert q00_q01 is host_device.get_edge("q00_q01")
        assert math.isclose(device.get_element("q00").rxy.amp180(), 0.7308488204080522)
        assert q01.measure.acq_channel() == 1
        assert math.isclose(q00_q01.coupler_parameters.parking_current(), 0.00065)


def test_open_node_device_sets_the_host_elements_back(session_context):
    ExtendedTransmon.close_all()
    with (
        loaded_state(session_context, state_file),
        open_host_device(DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS) as host_device,
    ):
        q00 = host_device.get_element("q00")
        q00.rxy.amp180(0.1)
        q00.measure.acq_channel(7)
        host_device.get_edge("q00_q01").cz.square_amp(0.2)

        with (
            pytest.raises(RuntimeError),
            open_node_device(
                "node",
                DEFAULT_TEST_QUBITS,
                DEFAULT_TEST_COUPLERS,
                session_context,
                host_device,
            ),
        ):
            raise RuntimeError("node failed")

        assert q00.rxy.amp180() == 0.1
        assert q00.measure.acq_channel() == 7
        assert host_device.get_edge("q00_q01").cz.square_amp() == 0.2
        assert all(Instrument.exist(name) for name in ["q00", "q01", "q00_q01"])
        assert not Instrument.exist("node")


def test_open_node_device_builds_the_elements_the_host_lacks(session_context):
    ExtendedTransmon.close_all()
    with (
        loaded_state(session_context, state_file),
        open_host_device(DEFAULT_TEST_QUBITS[:1], []) as host_device,
    ):
        with open_node_device(
            "node",
            DEFAULT_TEST_QUBITS,
            DEFAULT_TEST_COUPLERS,
            session_context,
            host_device,
        ) as device:
            assert device.get_element("q00") is host_device.get_element("q00")
            assert math.isclose(
                device.get_edge("q00_q01").coupler_parameters.parking_current(),
                0.00065,
            )

        assert Instrument.exist("q00")
        assert not Instrument.exist("q01")
        assert not Instrument.exist("q00_q01")


def test_open_node_device_rejects_a_host_transmon_of_another_type(session_context):
    ExtendedTransmon.close_all()
    with (
        loaded_state(session_context, state_file),
        open_host_device(
            DEFAULT_TEST_QUBITS, [], transmon_type=BasicTransmonElement
        ) as host_device,
    ):
        with (
            pytest.raises(TypeError, match="ExtendedTransmon"),
            open_node_device(
                "node", DEFAULT_TEST_QUBITS, [], session_context, host_device
            ),
        ):
            pass

        assert Instrument.exist("q00")


# NOTE: batching is not supported anymore, but maybe useful in the future
