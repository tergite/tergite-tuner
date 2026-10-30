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
"""The entry points called the ways the README shows."""

import dataclasses
import re
import shutil

import pytest

from tergite_tuner import (
    CalibrationResults,
    NodeEnum,
    SessionContext,
    reanalyse,
    run_node,
    tune_device,
    tuner,
)
from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.config.types import SpiConfig
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.state import loaded_state
from tergite_tuner.utils.types.enums import MeasurementMode

STATE_FILE = get_fixture_path("states", "standard_state.json")
STANDARD_RUN_RESONATOR = get_fixture_path(
    "data",
    "16-51-33_standard_run_ro_amplitude_three_state_optimization-SUCCESS",
    "20250728-165136-525-9c2f16-resonator_spectroscopy",
    "dataset_resonator_spectroscopy.hdf5",
)
# the fixture spi_config.toml wires q06 to q25, not the session's coupler
SPI_CONFIG = SpiConfig.model_validate(
    {"q00_q01": {"spi_module_number": 1, "dac_name": "dac0", "edge_group": 1}}
)


@pytest.fixture(autouse=True)
def _work_in_tmp_path(tmp_path, monkeypatch):
    """The dummy cluster assembles in the working directory, which workers would share."""
    monkeypatch.chdir(tmp_path)


def test_tune_device_calibrates_up_to_the_target_node(session_context, tmp_path):
    session = _get_dummy_session(
        session_context, tmp_path, target_node=NodeEnum.RESONATOR_SPECTROSCOPY
    )
    with loaded_state(session, STATE_FILE):
        ExtendedTransmon.close_all()
        returned_session, results = tune_device(session=session, refresh_session=False)

    assert returned_session is session
    assert isinstance(results, CalibrationResults)
    assert list(tmp_path.glob("*-run/dataset_resonator_spectroscopy.hdf5"))


def test_a_runs_results_file_seeds_a_later_session(session_context, tmp_path):
    session = _get_dummy_session(session_context, tmp_path)
    with loaded_state(session, STATE_FILE):
        ExtendedTransmon.close_all()
        run_node(NodeEnum.RESONATOR_SPECTROSCOPY, session=session)
    [results_file] = tmp_path.glob("*-run/results.json")

    later = SessionContext(qubits=session.qubits, calibration=results_file)

    fields = DEFAULT_NODE_SPECS[NodeEnum.RESONATOR_SPECTROSCOPY].qois.values()
    for qubit in session.qubits:
        for field in fields:
            value = session.state.read("transmons", qubit, field)
            assert value is not None
            assert later.state.read("transmons", qubit, field) == pytest.approx(
                value, nan_ok=True
            )


def test_run_node_runs_only_that_node(session_context, tmp_path):
    session = _get_dummy_session(session_context, tmp_path)
    with loaded_state(session, STATE_FILE):
        ExtendedTransmon.close_all()
        _, results = run_node(
            NodeEnum.RESONATOR_SPECTROSCOPY, session=session, refresh_session=False
        )

    assert isinstance(results, CalibrationResults)
    assert [path.name for path in tmp_path.glob("*-run/dataset_*.hdf5")] == [
        "dataset_resonator_spectroscopy.hdf5"
    ]


def test_run_node_uses_a_custom_node_spec(session_context, tmp_path):
    analysed_qubits = []
    spec = DEFAULT_NODE_SPECS[NodeEnum.RESONATOR_SPECTROSCOPY]

    def analyse(s21, session):
        analysed_qubits.append(s21.attrs["qubit"])
        return spec.analyse(s21, session)

    custom_spec = dataclasses.replace(spec, analyse=analyse)
    session = _get_dummy_session(
        session_context,
        tmp_path,
        node_specs={NodeEnum.RESONATOR_SPECTROSCOPY: custom_spec},
    )
    with loaded_state(session, STATE_FILE):
        ExtendedTransmon.close_all()
        run_node(
            NodeEnum.RESONATOR_SPECTROSCOPY, session=session, refresh_session=False
        )

    assert analysed_qubits == sorted(session.qubits)


def test_run_node_sets_its_options_over_a_given_session(session_context, monkeypatch):
    qubits = []
    monkeypatch.setattr(
        tuner, "_tune", lambda session, **_kwargs: qubits.append(session.qubits)
    )

    returned, _ = run_node(NodeEnum.T1, session=session_context, qubits=["q01"])
    run_node(NodeEnum.T1, session=session_context)

    assert returned is session_context
    assert qubits == [["q01"], ["q01"]]


def test_reanalyse_analyses_a_recorded_dataset(session_context, tmp_path):
    shutil.copy(STANDARD_RUN_RESONATOR, tmp_path)
    session = _get_dummy_session(
        session_context, tmp_path, target_node=NodeEnum.RESONATOR_SPECTROSCOPY
    )
    with loaded_state(session, STATE_FILE):
        ExtendedTransmon.close_all()
        returned_session, results = reanalyse(session=session, refresh_session=False)

        statuses = [
            session.state.read("cs", q, "resonator_spectroscopy")
            for q in ("q06", "q07")
        ]

    assert returned_session.cluster_mode == MeasurementMode.re_analyse
    assert isinstance(results, CalibrationResults)
    assert statuses == ["calibrated", "calibrated"]


def _get_dummy_session(session: SessionContext, data_dir, **updates) -> SessionContext:
    return session.model_copy(
        update={
            "data_dir": data_dir,
            "ignore_spec": True,
            "is_recalibration": True,
            "spi_config": SPI_CONFIG,
            "user_samplespace": {},
            **updates,
        }
    )


def test_run_node_logs_how_long_each_phase_took(session_context, tmp_path, caplog):
    session = _get_dummy_session(session_context, tmp_path)
    with loaded_state(session, STATE_FILE), caplog.at_level("INFO"):
        ExtendedTransmon.close_all()
        run_node(
            NodeEnum.RESONATOR_SPECTROSCOPY, session=session, refresh_session=False
        )

    phases = [
        record.message.split(" in ")[0]
        for record in caplog.records
        if re.search(r" in [0-9.]+ s$", record.message)
    ]
    assert phases == [
        "Compiled resonator_spectroscopy",
        "Measured resonator_spectroscopy",
        "Analysed resonator_spectroscopy",
    ]
