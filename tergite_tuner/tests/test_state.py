# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (c) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from tergite_tuner.config.types import NodeConfig
from tergite_tuner.lib import run
from tergite_tuner.state import DeviceState
from tergite_tuner.tuner import NodeManager
from tergite_tuner.utils.types.node_enum import NodeEnum

RESONATOR = NodeEnum.RESONATOR_SPECTROSCOPY
NODE_CONFIG = NodeConfig.model_validate(
    {
        "resonator_spectroscopy": {
            "all": {"reset": {"duration": 60e-6}},
            "q01": {"reset": {"duration": 90e-6}},
        }
    }
)


def test_a_session_starts_from_the_device_config_of_its_elements(session_context):
    device = session_context.device_config
    state = session_context.state

    assert state.read("transmons", "q00", "measure:pulse_duration") == (
        device.qubits["q00"]["measure"]["pulse_duration"]
    )
    assert state.read("couplers", "q00_q01", "cz_pulse_amplitude") == (
        device.couplers["q00_q01"]["cz_pulse_amplitude"]
    )
    assert set(state.get_records()["transmons"]) == set(session_context.qubits)


def test_a_calibration_goes_over_the_device_config(session_context):
    session = session_context.model_copy(
        update={
            "calibration": {"transmons": {"q00": {"measure": {"pulse_duration": 1e-6}}}}
        }
    )

    assert session.state.read("transmons", "q00", "measure:pulse_duration") == 1e-6
    assert not session.state.written_paths


def test_a_copied_session_writes_only_its_own_state(session_context):
    copy = session_context.model_copy()
    copy.state.write({"transmons": {"q00": {"rxy:amp180": 0.5}}})

    assert copy.state.read("transmons", "q00", "rxy:amp180") == 0.5
    assert session_context.state.read("transmons", "q00", "rxy:amp180") != 0.5
    assert not session_context.state.written_paths


def test_update_sets_options_over_a_session_and_keeps_its_state(session_context):
    state = session_context.state
    state.write({"transmons": {"q00": {"rxy:amp180": 0.5}}})

    session_context.update(qubits=["q00"], target_node="T1")

    assert session_context.qubits == ["q00"]
    assert session_context.target_node == NodeEnum.T1
    assert session_context.target_node_name == "t1"
    assert session_context.couplers == ["q00_q01"]
    assert session_context.state is state
    assert state.read("transmons", "q00", "rxy:amp180") == 0.5


def test_update_gives_the_state_the_config_of_added_qubits(session_context):
    session_context.update(qubits=["q00"])
    session_context.state.write({"transmons": {"q00": {"rxy:amp180": 0.5}}})

    session_context.update(qubits=["q00", "q01"])

    config = session_context.device_config.qubits["q01"]
    state = session_context.state
    assert state.read("transmons", "q00", "rxy:amp180") == 0.5
    assert state.read("transmons", "q01", "measure:pulse_duration") == (
        config["measure"]["pulse_duration"]
    )


def test_a_nodes_config_applies_only_while_it_runs(session_context, monkeypatch):
    session = session_context.model_copy(
        update={"node_config": NODE_CONFIG, "is_recalibration": False}
    )
    initial = session.state.read("transmons", "q01", "reset:duration")
    durations = _run_node(session, monkeypatch)

    assert durations == {"q00": 60e-6, "q01": 90e-6}
    assert session.state.read("transmons", "q01", "reset:duration") == initial


def test_a_recalibration_keeps_a_nodes_config(session_context, monkeypatch):
    session = session_context.model_copy(
        update={"node_config": NODE_CONFIG, "is_recalibration": True}
    )
    _run_node(session, monkeypatch)

    assert session.state.read("transmons", "q01", "reset:duration") == 90e-6
    assert not session.state.written_paths


def test_overrides_sit_over_the_values_until_cleared():
    state = DeviceState({"transmons": {"q00": {"reset": {"duration": 1.0}}}})
    state.add_overrides({"transmons": {"q00": {"reset:duration": 2.0}}})

    assert state.read("transmons", "q00", "reset:duration") == 2.0
    assert state.get_records()["transmons"]["q00"]["reset"]["duration"] == 1.0
    state.clear_overrides()
    assert state.read("transmons", "q00", "reset:duration") == 1.0


def test_only_writes_count_as_written():
    state = DeviceState()
    state.load({"transmons": {"q00": {"t1_time": 1.0}}})
    state.write(
        {
            "transmons": {"q00": {"rxy:amp180": 0.5}},
            "cs": {"q00": {"rabi": "calibrated"}},
        }
    )

    assert state.written_paths == {"rxy:amp180"}
    assert state.read("transmons", "q00", "rxy") == {"amp180": 0.5}
    assert state.read("transmons", "q00", "missing:path") is None


def _run_node(session, monkeypatch) -> dict[str, float]:
    """Inspects resonator spectroscopy, recording each qubit's reset duration while it runs."""
    durations = {}

    def calibrate(_spec, session, *_args):
        for qubit in session.qubits:
            durations[qubit] = session.state.read("transmons", qubit, "reset:duration")

    monkeypatch.setattr(run, "calibrate", calibrate)
    NodeManager(None, session).inspect_node(RESONATOR, ignore_spec=True)
    return durations
