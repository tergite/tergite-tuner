# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import json
from contextlib import suppress
from json import JSONDecodeError
from typing import Any, Dict, List, Mapping

import toml

from tergite_tuner import SessionContext
from tergite_tuner.export import (
    CalibrationResults,
    generate_calib_seed_file,
    read_result,
)
from tergite_tuner.tests.utils.fixtures import get_fixture_path, load_fixture
from tergite_tuner.tests.utils.redis import loaded_redis

_REDIS_DATA_FILE = get_fixture_path("redis", "export_bcc_script.json")
_REDIS_DATA = load_fixture("redis/export_bcc_script.json")
_CALIB_SEED = load_fixture("data/calib.seed.json")
_CALIB_CONTENT = _CALIB_SEED["calibration_config"]


def test_read_results_default(redis_connection):
    """Returns the calibration results saved in the session"""
    touched_fields = (
        # qubits/resonators
        "resonator_minimum" "spec",
        "r12",
        "extended_clock_freqs",
        "spec:spec_duration",
        # couplers
        "cz_dynamic_amplitude",
        "cz_working_durations_in_ns",
        "cz_dynamic_control_error",
        # cs (calibration supervisor)
        "resonator_spectroscopy_1",
        "qubit_12_spectroscopy",
    )

    expected_result = {
        "couplers": {
            "q11_q12": {
                "cz_dynamic_amplitude": 0.24,
                "cz_dynamic_control": 121.0,
                "cz_dynamic_control_error": 0.0,
                "cz_working_durations_in_ns": [
                    352.0,
                    352.0,
                    360.0,
                    360.0,
                    348.0,
                    340.0,
                    328.0,
                    324.0,
                    320.0,
                    304.0,
                ],
                "spec": {"spec_amp": 0.03, "spec_duration": 4e-06},
            }
        },
        "cs": {
            "q11": {
                "qubit_12_spectroscopy": "calibrated",
                "resonator_spectroscopy": "calibrated",
                "resonator_spectroscopy_1": "calibrated",
            },
            "q12": {
                "qubit_12_spectroscopy": "calibrated",
                "resonator_spectroscopy": "calibrated",
                "resonator_spectroscopy_1": "calibrated",
            },
        },
        "transmons": {
            "q11": {
                "clock_freqs": {
                    "f01": 4741499559.458488,
                    "f01_error": 0.0,
                    "f12": 4488401716.352375,
                    "f12_error": 0.0,
                    "readout": 6826375232.52066,
                    "readout_error": 0.0,
                },
                "extended_clock_freqs": {
                    "readout_1": 6826243053.574201,
                    "readout_1_error": 0.0,
                    "readout_2": 6826143734.200308,
                    "readout_2_error": 0.0,
                    "readout_2state_opt": 6826355555.555555,
                    "readout_2state_opt_error": 0.0,
                    "readout_3state_opt": 6826311111.111111,
                    "readout_3state_opt_error": 0.0,
                },
                "r12": {
                    "ef_amp180": 0.5633742718222708,
                    "ef_amp180_error": 0.0023647431005312867,
                    "ef_motzoi": 0.046153846153846184,
                    "ef_motzoi_error": 0.0,
                },
                "resonator_minimum": 6826355555.555555,
                "spec": {
                    "spec_amp": 0.03,
                    "spec_ampl_12_optimal": 0.01,
                    "spec_ampl_12_optimal_error": 0.0,
                    "spec_ampl_optimal": 0.008,
                    "spec_ampl_optimal_error": 0.0,
                    "spec_duration": 4e-06,
                },
            },
            "q12": {
                "clock_freqs": {
                    "f01": 4266043761.8823304,
                    "f01_error": 0.0,
                    "f12": 4110614017.9213386,
                    "f12_error": 0.0,
                    "readout": 6411557868.710736,
                    "readout_error": 0.0,
                },
                "extended_clock_freqs": {
                    "readout_1": 6411436935.474931,
                    "readout_1_error": 0.0,
                    "readout_2": 6411369478.180126,
                    "readout_2_error": 0.0,
                    "readout_2state_opt": 6411400000.0,
                    "readout_2state_opt_error": 0.0,
                    "readout_3state_opt": 6411444444.444445,
                    "readout_3state_opt_error": 0.0,
                },
                "r12": {
                    "ef_amp180": 0.587195516154055,
                    "ef_amp180_error": 0.006517486561764349,
                    "ef_motzoi": 0.3230769230769232,
                    "ef_motzoi_error": 0.0,
                },
                "resonator_minimum": 6411577777.777778,
                "spec": {
                    "spec_amp": 0.03,
                    "spec_ampl_12_optimal": 0.01,
                    "spec_ampl_12_optimal_error": 0.0,
                    "spec_ampl_optimal": 0.00625,
                    "spec_ampl_optimal_error": 0.0,
                    "spec_duration": 4e-06,
                },
            },
        },
    }
    with loaded_redis(redis_connection, _REDIS_DATA_FILE):
        session = SessionContext.from_env(qubits=["q11", "q12"], couplers=["q11_q12"])
        session._redis_fields_touched = {k: 1 for k in touched_fields}
        result = read_result(session)

    got = result.model_dump(exclude_none=True)
    assert got == expected_result


def test_read_results_session_only_false(redis_connection):
    """Returns all the calibration results in redis when session_only=False"""
    expected_result_dict = _redis_to_nested_dict(_REDIS_DATA)
    expected_result = CalibrationResults.model_validate(expected_result_dict)

    with loaded_redis(redis_connection, _REDIS_DATA_FILE):
        session = SessionContext.from_env(qubits=["q11", "q12"], couplers=["q11_q12"])
        result = read_result(session, session_only=False)

    assert result == expected_result


def test_generate_calib_seed_file_writes_toml(tmp_path, redis_connection):
    """``path=...`` writes the same payload to disk in TOML form."""
    output_path = tmp_path / "calibration_seed.toml"

    with loaded_redis(redis_connection, _REDIS_DATA_FILE):
        generate_calib_seed_file(
            path=output_path, couplers=["q11_q12"], qubits=["q11", "q12"]
        )

    with open(output_path, "r") as f:
        got = toml.load(f)

    assert got == _CALIB_SEED


def test_generate_calib_seed_file_partial(tmp_path, redis_connection):
    """When no couplers are requested the coupler list is empty."""
    output_path = tmp_path / "calibration_seed.toml"
    with loaded_redis(redis_connection, _REDIS_DATA_FILE):
        generate_calib_seed_file(path=output_path, couplers=[], qubits=["q12"])

    with open(output_path, "r") as f:
        got = toml.load(f)

    assert got == {
        "calibration_config": {
            **_CALIB_CONTENT,
            "coupler": [],
            "qubit": _CALIB_CONTENT["qubit"][1:],
            "readout_resonator": _CALIB_CONTENT["readout_resonator"][1:],
            "discriminators": {
                "lda": {"q12": _CALIB_CONTENT["discriminators"]["lda"]["q12"]}
            },
        }
    }


def test_generate_calib_seed_file_coupler_map(tmp_path, redis_connection):
    """When coupler_name_map is passed, coupler names are changed."""
    output_path = tmp_path / "calibration_seed.toml"
    with loaded_redis(redis_connection, _REDIS_DATA_FILE):
        generate_calib_seed_file(
            path=output_path,
            couplers=["q11_q12"],
            qubits=["q11", "q12"],
            coupler_name_map={"q11_q12": "u24"},
        )

    with open(output_path, "r") as f:
        seed = toml.load(f)

    expected = {
        **_CALIB_CONTENT,
        "coupler": [{**_CALIB_CONTENT["coupler"][0], "id": "u24"}],
    }

    assert seed["calibration_config"] == expected


def _redis_to_nested_dict(raw_data: Mapping[str, Any], level=0) -> Dict[str, Any]:
    """Converts the raw data in redis to a nested dict

    Keys that have ':' are converted into nested dicts

    Args:
        raw_data: the data that as got from redis in form {key: {type: ...: value: ...}}
        level: the level of the nested dict

    Returns:
        The dict nested
    """
    result = {}

    for key, value in raw_data.items():
        if level == 0:
            # redis data has format: {key: {type: ...: value: ...}}
            value = value["value"]

        # ignore 'nan'
        if value == "nan":
            continue

        if isinstance(value, Mapping):
            value = _redis_to_nested_dict(value, level + 1)
        elif isinstance(value, str):
            with suppress(JSONDecodeError):
                value = json.loads(value)

        path = key.split(":")
        _insert_nested_key(result, path, value)

    return result


def _insert_nested_key(data: Dict[str, Any], path: List[str], value: Any):
    """Inserts inplace a given value at the given nested path in the data object

    Args:
        data: the dictionary to insert into
        path: the path to the field, as a tuple of path segments.
        value: the value to be inserted.
    """
    inner_record = data
    for segment in path[:-1]:
        inner_record = inner_record.setdefault(segment, {})

    inner_record[path[-1]] = value
