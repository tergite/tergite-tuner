# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Export a session's calibrated parameter values, and as a BCC calibration seed."""

from __future__ import annotations

import ast
import re
from os import PathLike
from typing import (
    Annotated,
    Any,
    Literal,
    TypeVar,
    Unpack,
)

import numpy as np
import tomlkit
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from tergite_tuner.config.session import SessionContext, SessionOptions

_CalibValueType = TypeVar("_CalibValueType", int, float, str)
_NodeState = Literal["calibrated", "not_calibrated"]
_DOWNCONVERT_FREQUENCY = 4.4e9
_NUMPY_FLOAT_PATTERN = re.compile(r"np\.float\d*")
_SEED_UNITS = {
    "qubit": dict(
        frequency="Hz",
        t1_decoherence="us",
        t2_decoherence="us",
        anharmonicity="Hz",
        pi_pulse_amplitude="",
        pi_pulse_duration="s",
        pi_pulse_motzoi="",
        pulse_sigma="",
    ),
    "readout_resonator": dict(
        acq_delay="s",
        acq_integration_time="s",
        frequency="Hz",
        pulse_delay="s",
        pulse_duration="s",
        pulse_amplitude="",
        pulse_type="",
    ),
    "coupler": dict(
        frequency="Hz",
        cz_pulse_amplitude="",
        cz_pulse_dc_bias="",
        cz_pulse_duration_constant="s",
        control_rz_lambda="rad",
        target_rz_lambda="rad",
        pulse_type="",
    ),
}


def read_result(
    session: SessionContext, session_only: bool = True
) -> CalibrationResults:
    """The session's device state on its qubits and couplers.

    Args:
        session: the session to read.
        session_only: keep only the fields this session's nodes wrote: each written
            path's group (``rxy`` for ``rxy:amp180``), the path itself, or its ``_error``.

    Returns:
        The qubits' and couplers' calibration values.
    """
    should_keep_field = None
    if session_only:
        written_paths = session.state.written_paths

        def should_keep_field(field: str) -> bool:
            return any(
                field in (path.split(":")[0], path, f"{path}_error")
                for path in written_paths
            )

    records = session.state.get_records(
        session.qubits + session.couplers, should_keep_field
    )
    return CalibrationResults.model_validate(records)


def generate_calib_seed_file(
    path: str | PathLike[str] = "calibration.seed.toml",
    session: SessionContext | None = None,
    env_file: str | PathLike[str] | None = None,
    coupler_name_map: dict[str, str] | None = None,
    **session_options: Unpack[SessionOptions],
):
    """Writes the calibration seed tergite-backend reads, from the session's device state, as TOML to ``path``.

    Args:
        path: the file to write; defaults to ``calibration.seed.toml``.
        session: the session to read; built from ``env_file`` and ``session_options`` if not given,
            or with ``session_options`` set over its values.
        env_file: an optional ``.env`` file for that session.
        coupler_name_map: each coupler's name in the session mapped to its name in the backend;
            defaults to the same names.
        **session_options: any ``SessionContext`` field, most usefully ``qubits``,
            ``couplers`` and ``calibration``, overriding ``env_file`` and ``os.environ``.
    """
    if session is None:
        session = SessionContext.from_env(env_file, **session_options)
    elif session_options:
        session.update(**session_options)

    if coupler_name_map is None:
        coupler_name_map = {k: k for k in session.couplers}

    results = read_result(session, session_only=False)
    seed = {
        "calibration_config": {
            "units": _SEED_UNITS,
            "qubit": [
                _get_qubit_seed(q, item) for q, item in results.transmons.items()
            ],
            "coupler": [
                _get_coupler_seed(coupler_name_map[c], item)
                for c, item in results.couplers.items()
            ],
            "readout_resonator": [
                _get_resonator_seed(q, item) for q, item in results.transmons.items()
            ],
            "discriminators": {
                "lda": {q: _get_lda_seed(item) for q, item in results.transmons.items()}
            },
        }
    }
    with open(path, "w") as file:
        tomlkit.dump(seed, file)


class _ResultsModel(BaseModel):
    """Stored values, by name; a "nan" value is left out."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def convert_nans(cls, data: Any) -> Any:
        """Coverts all 'nan' values to Not set."""
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v != "nan"}
        return data


class CalibrationResults(_ResultsModel):
    """The device state's values and calibration statuses, by element."""

    transmons: dict[str, QubitResults] = {}
    couplers: dict[str, CouplerResults] = {}
    cs: dict[str, _CalibrationStatuses] = {}


class QubitResults(_ResultsModel):
    """A qubit's stored values."""

    clock_freqs: _QubitClockFreqs | None = None
    rxy: _QubitRxy | None = None
    t1_time: float | None = None
    t1_time_error: float | None = None
    t2_echo_time: float | None = None
    t2_echo_time_error: float | None = None
    t2_time: float | None = None
    t2_time_error: float | None = None
    lda_coef_0: float | None = None
    lda_coef_1: float | None = None
    lda_intercept: float | None = None
    measure: _QubitMeasure | None = None
    measure_1: _QubitMeasure | None = None
    measure_2: _QubitMeasure | None = None
    measure1: _QubitMeasure | None = None
    measure2: _QubitMeasure | None = None
    extended_clock_freqs: _QubitExtendedClockFreqs | None = None
    measure_2state_opt: _QubitMeasure | None = None
    measure_3state_opt: _QubitMeasure | None = None
    omega_20: float | None = None
    omega_20_error: float | None = None
    center_0: NumpyFloatTuple | None = Field(None, alias="center|0>")
    center_1: NumpyFloatTuple | None = Field(None, alias="center|1>")
    center_2: NumpyFloatTuple | None = Field(None, alias="center|2>")
    lda_coef_1_error: float | None = None
    lda_coef_0_error: float | None = None
    centroid_I: float | None = None
    centroid_Q: float | None = None
    centroid_Q_error: float | None = None
    spec: _QubitSpec | None = None
    resonator_minimum: float | None = None
    resonator_minimum_error: float | None = None
    resonator_minimum_1: float | None = None
    resonator_minimum_1_error: float | None = None
    r12: _QubitR12 | None = None
    inv_cm_opt_error: float | None = None
    fidelity_error: float | None = None
    lda_intercept_error: float | None = None
    omega_01: float | None = None
    omega_01_error: float | None = None
    omega_12: float | None = None
    omega_12_error: float | None = None
    purity_fidelity: float | None = None
    inv_cm_opt: float | None = None
    centroid_I_error: float | None = None
    attenuation: float | None = None
    leakage: float | None = None
    leakage_error: float | None = None
    Ql: float | None = None
    Ql_error: float | None = None
    Ql_1: float | None = None
    Ql_1_error: float | None = None
    VNA_f01_frequency: float | None = None
    VNA_f12_frequency: float | None = None
    fidelity: float | None = None
    reset: _Reset | None = None
    readout_matrix: (
        Annotated[list[list[float]], BeforeValidator(_parse_list_string)] | None
    ) = None


class CouplerResults(_ResultsModel):
    """A coupler's stored values."""

    cz_pulse_frequency: float | None = None
    cz_pulse_amplitude: float | None = None
    parking_current: float | None = None
    cz_pulse_duration: float | None = None
    cz_dynamic_control: float | None = None
    cz_dynamic_target: float | None = None
    target_local_phase: float | None = None
    qubit_crossing_points: NumberList | None = None
    cz_pulse_frequency_error: float | None = None
    cz_fidelity: float | None = None
    cz_dynamic_amplitude: float | None = None
    cz_working_durations_in_ns: NumberList | None = None
    cz_dynamic_control_error: float | None = None
    control_local_phase: float | None = None
    cz_working_frequencies_error: float | None = None
    spec: _CouplerSpec | None = None
    cz_working_frequencies: NumberList | None = None
    cz_pulse_duration_error: float | None = None
    cz_working_durations_in_ns_error: float | None = None
    reset: _Reset | None = None
    tqg_fidelity: float | None = None
    cz_dynamic_target_error: float | None = None
    attenuation: float | None = None


class _CalibrationStatuses(_ResultsModel):
    """Each node's calibration status for an element."""

    resonator_spectroscopy: _NodeState | None = None
    qubit_01_spectroscopy: _NodeState | None = None
    rabi_oscillations: _NodeState | None = None
    ramsey_correction: _NodeState | None = None
    motzoi_parameter: _NodeState | None = None
    n_rabi_oscillations: _NodeState | None = None
    resonator_spectroscopy_1: _NodeState | None = None
    qubit_12_spectroscopy: _NodeState | None = None
    rabi_oscillations_12: _NodeState | None = None
    ramsey_correction_12: _NodeState | None = None
    resonator_spectroscopy_2: _NodeState | None = None
    ro_frequency_three_state_optimization: _NodeState | None = None
    ro_amplitude_three_state_optimization: _NodeState | None = None
    qubit_bring_up_spectroscopy: _NodeState | None = None
    t1: _NodeState | None = None
    t2: _NodeState | None = None
    t2_echo: _NodeState | None = None
    ro_frequency_two_state_optimization: _NodeState | None = None
    ro_amplitude_two_state_optimization: _NodeState | None = None
    randomized_benchmarking: _NodeState | None = None
    purity_benchmarking: _NodeState | None = None
    punchout: _NodeState | None = None


class _QubitClockFreqs(_ResultsModel):
    """A qubit's ``clock_freqs``."""

    f01: float | None = None
    f01_error: float | None = None
    readout_error: float | None = None
    readout: float | None = None
    f12: float | None = None
    f12_error: float | None = None


class _QubitRxy(_ResultsModel):
    """A qubit's ``rxy``."""

    amp180: float | None = None
    amp180_error: float | None = None
    duration: float | None = None
    motzoi: float | None = None
    motzoi_error: float | None = None
    sigma: float = 0


class _QubitMeasure(_ResultsModel):
    """A qubit's ``measure*``."""

    acq_delay: float | None = None
    integration_time: float | None = None
    ro_pulse_delay: float = 0
    pulse_duration: float | None = None
    pulse_amp: float | None = None
    pulse_amp_error: float | None = None
    acq_threshold: float | None = None
    acq_threshold_error: float | None = None
    acq_rotation: float | None = None
    acq_rotation_error: float | None = None


class _QubitExtendedClockFreqs(_ResultsModel):
    """A qubit's ``extended_clock_freqs``."""

    readout_2state_opt: float | None = None
    readout_3state_opt: float | None = None
    readout_2_error: float | None = None
    readout_1_error: float | None = None
    readout_1: float | None = None
    readout_3state_opt_error: float | None = None
    readout_2: float | None = None
    readout_2state_opt_error: float | None = None


class _QubitSpec(_ResultsModel):
    """A qubit's ``spec``."""

    spec_ampl_12_optimal: float | None = None
    spec_ampl_optimal: float | None = None
    spec_ampl_optimal_error: float | None = None
    spec_amp: float | None = None
    spec_ampl_12_optimal_error: float | None = None
    spec_duration: float | None = None


class _QubitR12(_ResultsModel):
    """A qubit's ``r12``."""

    ef_amp180_error: float | None = None
    ef_motzoi: float | None = None
    ef_amp180: float | None = None
    ef_motzoi_error: float | None = None


class _CouplerSpec(_ResultsModel):
    """A coupler's ``spec``."""

    spec_amp: float | None = None
    spec_duration: float | None = None


class _Reset(_ResultsModel):
    """An element's ``reset``."""

    duration: float | None = None


def _get_qubit_seed(qubit: str, item: QubitResults) -> dict[str, Any]:
    """A qubit's seed entry from its calibrated values."""
    return dict(
        id=qubit,
        frequency=item.clock_freqs.f01,
        pi_pulse_amplitude=item.rxy.amp180,
        pi_pulse_duration=item.rxy.duration,
        pi_pulse_motzoi=item.rxy.motzoi,
        pulse_type="Gaussian",
        pulse_sigma=item.rxy.sigma or 0,  # might be None
        t1_decoherence=item.t1_time,
        t2_decoherence=item.t2_echo_time,
    )


def _get_coupler_seed(name: str, item: CouplerResults) -> dict[str, Any]:
    """A coupler's seed entry, under its name in the backend."""
    return dict(
        id=name,
        frequency=_DOWNCONVERT_FREQUENCY - item.cz_pulse_frequency,
        cz_pulse_amplitude=item.cz_pulse_amplitude,
        cz_pulse_dc_bias=item.parking_current or 0,  # might be None
        cz_pulse_duration_constant=item.cz_pulse_duration,
        control_rz_lambda=np.deg2rad(item.cz_dynamic_control),
        target_rz_lambda=np.deg2rad(item.cz_dynamic_target),
        pulse_type="wacqt_cz",
    )


def _get_resonator_seed(qubit: str, item: QubitResults) -> dict[str, Any]:
    """A qubit's readout resonator's seed entry."""
    return dict(
        id=qubit,
        acq_delay=item.measure.acq_delay,
        acq_integration_time=item.measure.integration_time,
        frequency=item.extended_clock_freqs.readout_2state_opt,
        pulse_delay=item.measure.ro_pulse_delay or 0,  # might be None
        pulse_duration=item.measure.pulse_duration,
        pulse_type="Square",
        pulse_amplitude=item.measure_2state_opt.pulse_amp,
    )


def _get_lda_seed(item: QubitResults) -> dict[str, Any]:
    """A qubit's linear discriminant's coefficients and intercept."""
    return dict(
        coef_0=item.lda_coef_0,
        coef_1=item.lda_coef_1,
        intercept=item.lda_intercept,
    )


def _validate_numpy_tuple(v: Any) -> Any:
    """Validates a field of tuples of numpy float64"""
    if isinstance(v, str):
        try:
            v = ast.literal_eval(_NUMPY_FLOAT_PATTERN.sub("", v))
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"Could not parse numpy tuple string: {e}")

    if isinstance(v, (list, tuple)):
        return tuple(np.float64(item) for item in v)
    return v


NumpyFloatTuple = Annotated[
    tuple[np.float64, np.float64], BeforeValidator(_validate_numpy_tuple)
]


def _parse_list_string(v: Any) -> Any:
    """Parses a list an analysis wrote as a string, as ``str(values)``."""
    if isinstance(v, str):
        return ast.literal_eval(_NUMPY_FLOAT_PATTERN.sub("", v))
    return v


NumberList = Annotated[list[float], BeforeValidator(_parse_list_string)]
