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

import os

import pytest
import toml

from tergite_tuner.export import extract_bcc_params
from tergite_tuner.tests.utils.decorators import loaded_redis
from tergite_tuner.tests.utils.fixtures import get_fixture_path

_redis_backup_path = get_fixture_path("redis", "export_bcc_script.json")


# Expected per-element values derived from the redis backup at
# ``_redis_backup_path``. These are kept inline so the test does not
# rely on a checked-in TOML reference file.
_EXPECTED_QUBIT_Q11 = {
    "id": "q11",
    "frequency": pytest.approx(4741499559.458488),
    "pi_pulse_amplitude": pytest.approx(0.7308488204080522),
    "pi_pulse_duration": pytest.approx(4.4e-08),
    "pi_pulse_motzoi": pytest.approx(-0.05384615384615388),
    "pulse_type": "Gaussian",
    "pulse_sigma": pytest.approx(0.0),
    "t1_decoherence": pytest.approx(63.39282543781701),
    "t2_decoherence": pytest.approx(7.486213589808061),
}
_EXPECTED_QUBIT_Q12 = {
    "id": "q12",
    "frequency": pytest.approx(4266043761.8823304),
    "pi_pulse_amplitude": pytest.approx(0.3942183215348928),
    "pi_pulse_duration": pytest.approx(4.4e-08),
    "pi_pulse_motzoi": pytest.approx(0.02307692307692305),
    "pulse_type": "Gaussian",
    "pulse_sigma": pytest.approx(0.0),
    "t1_decoherence": pytest.approx(86.61716166660516),
    "t2_decoherence": pytest.approx(20.27724290001215),
}
_EXPECTED_RESONATOR_Q11 = {
    "id": "q11",
    "acq_delay": pytest.approx(2.4e-07),
    "acq_integration_time": pytest.approx(3.4e-06),
    "frequency": pytest.approx(6826375232.52066),
    "pulse_delay": pytest.approx(0.0),
    "pulse_duration": pytest.approx(3.8e-06),
    "pulse_type": "Square",
    "pulse_amplitude": pytest.approx(0.035539772727272725),
}
_EXPECTED_COUPLER_Q11_Q12 = {
    "id": "q11_q12",
    "frequency": pytest.approx(4176200000.0),
    "cz_pulse_amplitude": pytest.approx(0.245),
    "cz_pulse_dc_bias": pytest.approx(0.00095),
    "cz_pulse_duration_constant": pytest.approx(3.8e-07),
    "control_rz_lambda": pytest.approx(121.0),
    "target_rz_lambda": pytest.approx(134.0),
    "pulse_type": "wacqt_cz",
}
_EXPECTED_LDA_Q11 = {
    "coef_0": pytest.approx(66.43380014248888),
    "coef_1": pytest.approx(971.3756882612579),
    "intercept": pytest.approx(-9.025023646657276),
}


def _assert_seed_full(seed: dict) -> None:
    """Assert structural shape and values for the standard q11/q12 export."""
    cfg = seed["calibration_config"]

    # Static unit labels
    assert cfg["units"]["qubit"]["frequency"] == "Hz"
    assert cfg["units"]["readout_resonator"]["frequency"] == "Hz"
    assert cfg["units"]["coupler"]["control_rz_lambda"] == "deg"

    # Per-element parameter lists
    assert cfg["qubit"] == [_EXPECTED_QUBIT_Q11, _EXPECTED_QUBIT_Q12]
    assert cfg["readout_resonator"][0] == _EXPECTED_RESONATOR_Q11
    assert cfg["coupler"] == [_EXPECTED_COUPLER_Q11_Q12]
    assert cfg["discriminators"]["lda"]["q11"] == _EXPECTED_LDA_Q11


def test_export_bcc_script_dict(redis_connection):
    """``format='dict'`` returns the calibration seed payload directly."""
    with loaded_redis(redis_connection, _redis_backup_path):
        seed = extract_bcc_params(
            qubits=["q11", "q12"],
            couplers=["q11_q12"],
            format="dict",
        )

    assert isinstance(seed, dict)
    _assert_seed_full(seed)


def test_export_bcc_script_writes_toml(tmp_path, redis_connection):
    """``output=...`` writes the same payload to disk in TOML form."""
    output_path = os.path.join(tmp_path, "calibration_seed.toml")

    with loaded_redis(redis_connection, _redis_backup_path):
        extract_bcc_params(
            qubits=["q11", "q12"],
            couplers=["q11_q12"],
            format="dict",
            output=output_path,
        )

    with open(output_path, "r") as f:
        loaded = toml.load(f)

    _assert_seed_full(loaded)


def test_export_bcc_script_partial(redis_connection):
    """When no couplers are requested the coupler list is empty."""
    with loaded_redis(redis_connection, _redis_backup_path):
        seed = extract_bcc_params(qubits=["q11"], couplers=[], format="dict")

    assert seed["calibration_config"]["coupler"] == []
    assert len(seed["calibration_config"]["qubit"]) == 1
    assert seed["calibration_config"]["qubit"][0] == _EXPECTED_QUBIT_Q11
